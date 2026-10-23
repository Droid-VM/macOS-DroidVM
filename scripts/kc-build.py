#!/usr/bin/env python3
"""Build an MH_FILESET kernel collection from a source-built arm64e xnu-12377 kernel and kexts borrowed from a macOS 26.5 kernelcache.

    kc-build.py KC265 KERNEL.macho OUTPUT [--keep BUNDLE_ID ...] [--check]

The kernel must be linked with out/x12377/kc-segaddrs.sh (XNU_KC=1 build-full.sh): its segments sit in the holes of KC265 and its
pointers are arm64e threaded rebases, which are re-encoded here as the collection's format-8 chained fixups (xnu's fileset path in
arm_init.c only runs kernel_collection_slide, never rebase_threaded_starts). Kept kexts stay exactly where they are in KC265 (their
segments refer to each other through PC-relative code with no relocation records left); everything else is dropped. The whole
collection moves from the macOS link address to the kernel's (VM_KERNEL_LINK_ADDRESS): chained targets are base-relative, so only the
load commands, symbol values and prelink-info addresses change. The file is a flat image: file offset = vmaddr - collection base.
See docs/xnu-12377-port.md ("fileset KC 方案").
"""
import argparse
import hmac
import json
import plistlib
import uuid
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fileset_kc  # noqa: E402
import kc_native  # noqa: E402
import kc_reloc  # noqa: E402

PAGE = 0x4000
NEW_BASE = 0xfffffff007004000        # VM_KERNEL_LINK_ADDRESS of the iOS-layout kernel (makedefs/MakeInc.def ARM64_LINK_ADDR)
MH_DYLIB_IN_CACHE = 0x80000000
LC_SEGMENT_64, LC_SYMTAB, LC_DYSYMTAB, LC_UNIXTHREAD, LC_SPLIT_INFO, LC_FUNCTION_STARTS = 0x19, 2, 0xb, 5, 0x1e, 0x26
LC_FILESET_ENTRY, LC_CHAINED_FIXUPS = 0x80000035, 0x80000034

# Top-level segments that move from where KC265 has them (offsets from the collection base) to make room for the larger kernel.
DATA_CONST_START = 0x810000
DATA_START = 0x3814000


def up(value, align=PAGE):
    return (value + align - 1) // align * align


def cstr(raw):
    return raw.split(b'\0')[0].decode()


class Macho:
    """Segments, load commands and symbol table of the source-built kernel (a plain MH_EXECUTE file)."""

    def __init__(self, data):
        self.data = data
        magic, cpu, sub, kind, count, size, flags, _ = struct.unpack_from('<8I', data, 0)
        if (magic, cpu, kind) != (0xfeedfacf, 0x100000c, 2):
            raise SystemExit('kernel is not an arm64 MH_EXECUTE')
        self.flags, self.subtype = flags, sub
        self.commands = []
        offset = 32
        for _ in range(count):
            cmd, length = struct.unpack_from('<II', data, offset)
            self.commands.append((cmd, bytes(data[offset:offset + length])))
            offset += length
        self.segments = []
        for cmd, raw in self.commands:
            if cmd == LC_SEGMENT_64:
                name, va, size_, fileoff, filesize, maxprot, initprot, nsects, flags_ = struct.unpack_from('<16s4Q4I', raw, 8)
                sections = []
                for index in range(nsects):
                    sname, sseg, sva, ssize, soff, salign, sreloff, snreloc, sflags = struct.unpack_from('<16s16s2Q7I', raw, 72 + index * 80)[:9]
                    sections.append({'name': cstr(sname), 'segment': cstr(sseg), 'va': sva, 'size': ssize, 'fileoff': soff, 'flags': sflags})
                self.segments.append({'name': cstr(name), 'va': va, 'size': size_, 'fileoff': fileoff, 'filesize': filesize, 'sections': sections})
            elif cmd == LC_SYMTAB:
                self.symtab = struct.unpack_from('<4I', raw, 8)

    def segment(self, name):
        return next(s for s in self.segments if s['name'] == name)

    def section(self, segment, name):
        return next(s for s in self.segment(segment)['sections'] if s['name'] == name)

    def command(self, cmd):
        return next(raw for c, raw in self.commands if c == cmd)


def read_threaded_chains(kernel, image, flat):
    """Decode the kernel's threaded rebases. Returns [(site_va, target_va, auth, diversity, addr_div, key)] and zeroes nothing."""
    text = kernel.segment('__TEXT')['va']
    starts = kernel.section('__TEXT', '__thread_starts')
    words = struct.unpack_from(f'<{starts["size"] // 4}I', kernel.data, starts['fileoff'])
    step = 8 if words[0] & 1 else 4
    sites = []
    for first in words[1:]:
        if first == 0xffffffff:
            break
        va = text + first
        while True:
            value, = struct.unpack_from('<Q', image, flat(va))
            if value >> 62 & 1:
                raise SystemExit(f'threaded bind at {va:#x}: not supported')
            if value >> 63:
                target = text + (value & 0xffffffff)
                sites.append((va, target, True, value >> 32 & 0xffff, bool(value >> 48 & 1), value >> 49 & 3))
            else:
                top8, bottom43 = value & 0x0007f80000000000, value & 0x000007ffffffffff
                signed = bottom43 - (1 << 43) if bottom43 >> 42 & 1 else bottom43
                full = (top8 << 13) | (signed & 0x00ffffffffffffff)
                if full >> 56 != 0xff:
                    raise SystemExit(f'plain pointer at {va:#x} is {full:#x}: top-byte flags cannot be expressed in a format-8 chain')
                sites.append((va, full, False, 0, False, 0))
            delta = (value & 0x3ff8000000000000) >> 51
            if not delta:
                break
            va += delta * step
    return sites


def dependency_closure(info, roots):
    by_id = {e['CFBundleIdentifier']: e for e in info}
    keep, todo = set(), list(roots)
    while todo:
        name = todo.pop()
        if name in keep or name not in by_id:
            continue
        keep.add(name)
        todo.extend(by_id[name].get('OSBundleLibraries', {}))
    return keep


def build(args):
    kc = fileset_kc.Kernelcache(Path(args.kc).read_bytes())
    old_base = kc.base
    shift = NEW_BASE - old_base
    kernel = Macho(Path(args.kernel).read_bytes())
    image = bytearray(kc.data)
    old_off = lambda va: va - old_base            # noqa: E731  flat offset of an old address
    new_off = lambda va: va - NEW_BASE            # noqa: E731  flat offset of an address in the new collection

    prelink = next(s for s in kc.segments if s['name'] == '__PRELINK_INFO')
    section = prelink['sections'][0]
    plist = plistlib.loads(bytes(image[section['fileoff']:section['fileoff'] + section['size']]).split(b'\0')[0])
    plist_entries_original = [dict(e) for e in plist['_PrelinkInfoDictionary']]
    natives = [json.loads(Path(p).read_text()) for p in args.native]
    roots = list(args.keep) + [lib for spec in natives for lib in spec['libraries']]
    keep = dependency_closure(plist['_PrelinkInfoDictionary'], roots) & set(kc.entries)
    print(f'keeping {len(keep)} kexts: {sorted(keep)}')

    # 1. Clear every segment of the old kernel and of the dropped kexts (everything but their shared LINKEDIT).
    for name in kc.entries:
        if name in keep:
            continue
        for segment in kc.macho(name)['segments']:
            if segment['name'] != '__LINKEDIT' and segment['name'] != '__LINKINFO' and segment['size']:
                at = old_off(segment['va'])
                image[at:at + segment['size']] = bytes(segment['size'])
    link_info = kernel.segment('__LINKINFO')
    old_link_info = kc.macho('com.apple.kernel')['segments']
    old_link_info = next(s for s in old_link_info if s['name'] == '__LINKINFO')
    if link_info['size'] > old_link_info['size']:
        raise SystemExit('kernel __LINKINFO outgrew its slot')
    at = old_off(old_link_info['va'])
    image[at:at + old_link_info['size']] = bytes(old_link_info['size'])
    image[old_off(prelink['va']):old_off(prelink['va']) + prelink['size']] = bytes(prelink['size'])

    # 2. Place the kernel's segments. They are linked at their final addresses (kc-segaddrs.sh), so this is a copy.
    placed = []
    for segment in kernel.segments:
        if segment['name'] in ('__LINKEDIT',) or not segment['size']:
            continue
        at = new_off(segment['va'])
        if at < 0 or at + segment['size'] > len(image):
            raise SystemExit(f'{segment["name"]} {segment["va"]:#x} lies outside the collection')
        if segment['name'] == '__LINKINFO':
            at = old_off(old_link_info['va'])
            segment = dict(segment, va=NEW_BASE + at)
        image[at:at + segment['size']] = bytes(segment['size'])
        image[at:at + segment['filesize']] = kernel.data[segment['fileoff']:segment['fileoff'] + segment['filesize']]
        placed.append(segment)
    kernel_sites = read_threaded_chains(kernel, image, new_off)
    print(f'kernel: {len(kernel_sites)} threaded pointers ({sum(1 for s in kernel_sites if s[2])} signed)')

    # 3. Kept kexts: rebind what they reference in Apple's kernel to the source-built one, then carry their chained pointers over.
    old_kernel = kc.macho('com.apple.kernel')
    old_symbols = [(value, name) for name, kind, sect, desc, value in kc.symbols(old_kernel) if kind & 0x0e == 0x0e and not kind & 0xe0]
    new_symbols = {}
    symoff, nsyms, stroff, strsize = kernel.symtab
    strings = kernel.data[stroff:stroff + strsize]
    for index in range(nsyms):
        strx, kind, sect, desc, value = struct.unpack_from('<IBBHQ', kernel.data, symoff + index * 16)
        if kind & 0x0e == 0x0e and not kind & 0xe0:
            new_symbols.setdefault(strings[strx:strings.index(b'\0', strx)].decode(errors='replace'), []).append(value)
    remap = kc_reloc.Remap([(s['va'], s['va'] + s['size']) for s in old_kernel['segments'] if s['size'] and s['name'] not in ('__LINKEDIT', '__LINKINFO')],
                           old_symbols, new_symbols)
    report = {'branch': 0, 'skipped': []}
    for name in sorted(keep):
        text = next(s for s in kc.macho(name)['segments'] if s['name'] == '__TEXT_EXEC')
        at = old_off(text['va'])
        words = list(struct.unpack_from(f'<{text["size"] // 4}I', image, at))
        try:
            changes = kc_reloc.relocate_text(words, text['va'], shift, remap, report)
        except kc_reloc.Unresolvable as problem:
            raise SystemExit(f'{name}: {problem}')
        for index, word in changes.items():
            struct.pack_into('<I', image, at + index * 4, word)
        print(f'{name}: {len(changes)} branches retargeted')
        seal_fips(kc, image, name, old_off)
    skipped = report.pop('skipped')
    print('relocation:', report, dict(remap.stats), f'{len(skipped)} words that look like branches/adrp into the kernel are data:', [(hex(a), kind) for a, kind, _ in skipped][:12])
    for (symbol, delta), uses in sorted(remap.interior.items()):
        print(f'  interior reference {symbol}+{delta:#x} x{uses}')

    # Chained pointers of the kept kexts (targets are base-relative, so unchanged by the uniform shift unless they point into the old kernel).
    kext_sites = []
    ranges = []
    for name in keep:
        for segment in kc.macho(name)['segments']:
            if segment['size'] and segment['name'] != '__LINKEDIT':
                ranges.append((segment['va'], segment['va'] + segment['size'], name))
    ranges.sort()

    def owner(va):
        for low, high, name in ranges:
            if low <= va < high:
                return name
        return None

    for site, value, target, auth, diversity, addr_div, key in kc.chained_sites():
        if owner(site):
            kext_sites.append((site + shift, remap.map(target) if remap.in_old_kernel(target) else target + shift, auth, diversity, addr_div, key))
    kept_old_sites = {s[0]: s[1] for s in kext_sites}
    print(f'kexts: {len(kext_sites)} chained pointers')

    # Kexts of our own (drivers that derive from classes of the collection's kexts): link, place, describe.
    native_entries, native_commands = [], []
    if natives:
        exported = {}
        for name in sorted(keep):
            for symbol, kind, sect, desc, value in kc.symbols(kc.macho(name)):
                if kind & 0x0f == 0x0f and not kind & 0xe0:
                    exported.setdefault(symbol, []).append(value + shift)

        def resolve(symbol):
            found = new_symbols.get(symbol, [])
            if len(found) == 1:
                return found[0]
            found = exported.get(symbol, [])
            return found[0] if len(found) == 1 else None

        used = [(new_off(s['va']), new_off(s['va']) + s['size']) for s in placed]
        for name in keep:
            for segment in kc.macho(name)['segments']:
                if segment['size'] and segment['name'] != '__LINKEDIT':
                    used.append((old_off(segment['va']), old_off(segment['va']) + segment['size']))
        kernel_exec = new_off(kernel.segment('__TEXT_EXEC')['va'])
        regions = {'__TEXT': (0x4000, seg_end_of(kc, '__PRELINK_TEXT', old_off)), '__TEXT_EXEC': (seg_start_of(kc, '__TEXT_EXEC', old_off), kernel_exec),
                   '__DATA_CONST': (new_off(kernel.segment('__LASTDATA_CONST')['va']) + kernel.segment('__LASTDATA_CONST')['size'], seg_end_of(kc, '__DATA_CONST', old_off)),
                   '__DATA': (new_off(kernel.segment('__PRELINK_DATA')['va']), seg_end_of(kc, '__DATA', old_off))}

        def allocate(segment, size, align):
            low, high = regions[segment]
            cursor = low
            for start, end in sorted(used):
                if end <= cursor:
                    continue
                if start >= cursor + size:
                    break
                cursor = (max(cursor, end) + align - 1) // align * align
            if cursor + size > high:
                raise SystemExit(f'no room for a {size:#x}-byte native kext {segment}')
            used.append((cursor, cursor + size))
            return NEW_BASE + cursor

        for spec in natives:
            objects = json.loads(Path(spec['objects']).read_text())
            try:
                linked = kc_native.link(objects, resolve, allocate, 0x800, 0xd0, spec['start'], spec['stop'])
            except kc_native.LinkError as problem:
                raise SystemExit(f'{spec["bundle"]}: {problem}')
            segs = linked['segments']
            for seg in segs.values():
                at = new_off(seg['va'])
                image[at:at + len(seg['data'])] = seg['data']
            text_va, data_va = segs['__TEXT']['va'], segs['__DATA']['va']
            info = struct.pack('<QiI', 0, 1, 0xffffffff) + spec['bundle'].encode().ljust(64, b'\0') + spec.get('version', '1.0.0').encode().ljust(64, b'\0')
            info += struct.pack('<iQQQQ', -1, 0, text_va, segs['__TEXT']['data'].__len__(), 0) + bytes(16)
            image[new_off(data_va):new_off(data_va) + len(info)] = info
            for offset, symbol in ((180, spec['start']), (188, spec['stop'])):
                linked['sites'].append((data_va + offset, linked['symbols'][symbol], True, 0xe4fe, False, 0))
            if spec.get('vtable'):
                check_vtable(kc, linked, kept_old_sites, spec['vtable'], shift, old_off)
            kext_sites.extend(linked['sites'])
            native_commands.append((text_va, segs, spec))
            native_entries.append({
                'CFBundleIdentifier': spec['bundle'], 'CFBundleName': spec['name'], 'CFBundleVersion': spec.get('version', '1.0.0'),
                'CFBundleShortVersionString': spec.get('version', '1.0.0'), 'CFBundlePackageType': 'KEXT', 'CFBundleExecutable': spec['name'],
                'CFBundleInfoDictionaryVersion': '6.0', 'OSBundleCompatibleVersion': '1.0.0', 'OSBundleRequired': 'Root',
                'OSBundleLibraries': spec['libraries'], 'IOKitPersonalities': spec['personalities'],
                'OSBundleUUID': uuid.uuid5(uuid.NAMESPACE_URL, spec['bundle']).bytes,
                '_PrelinkBundlePath': f'/System/Library/Extensions/{spec["name"]}.kext', '_PrelinkExecutableRelativePath': f'Contents/MacOS/{spec["name"]}',
                '_PrelinkExecutableLoadAddr': to_signed(text_va), '_PrelinkExecutableSourceAddr': to_signed(text_va),
                '_PrelinkExecutableSize': len(segs['__TEXT']['data']), '_PrelinkKmodInfo': to_signed(data_va)})
            print(f'{spec["bundle"]}: linked, header at {text_va:#x}, {len(linked["sites"])} pointers')

    # 4. Chains: every pointer of the collection is a format-8 chained rebase, encoded per page.
    sites = {}
    for va, target, auth, diversity, addr_div, key in kernel_sites + kext_sites:
        if not 0 <= target - NEW_BASE < 1 << 30:
            raise SystemExit(f'pointer at {va:#x} targets {target:#x}, outside the 1 GiB collection window')
        sites[va] = (target - NEW_BASE, auth, diversity, addr_div, key)

    data_const_start, data_start = DATA_CONST_START, DATA_START
    seg_end = {s['name']: old_off(s['va']) + s['size'] for s in kc.segments}
    top = [
        ('__TEXT', 0, 0x4000), ('__PRELINK_TEXT', 0x4000, seg_end['__PRELINK_TEXT'] - 0x4000),
        ('__DATA_CONST', data_const_start, seg_end['__DATA_CONST'] - data_const_start),
        ('__TEXT_EXEC', old_off(next(s for s in kc.segments if s['name'] == '__TEXT_EXEC')['va']),
         next(s for s in kc.segments if s['name'] == '__TEXT_EXEC')['size']),
    ]
    info_start = old_off(prelink['va'])
    # PRELINK_INFO: the pruned plist, then DATA (kernel __KLDDATA/__DATA/__BOOTDATA first), then LINKEDIT.
    keep_ids = keep | {'com.apple.kernel'}
    resources = {e['CFBundleIdentifier'] for e in plist['_PrelinkInfoDictionary'] if e.get('OSKernelResource')}
    entries = []
    for entry in plist['_PrelinkInfoDictionary']:
        name = entry['CFBundleIdentifier']
        if name in keep:
            for key in ('_PrelinkExecutableLoadAddr', '_PrelinkExecutableSourceAddr', '_PrelinkKmodInfo'):
                if key in entry:
                    entry[key] += shift
            entries.append(entry)
        elif entry.get('OSKernelResource'):
            entries.append(entry)        # the kernel's pseudo-extensions (com.apple.kpi.*), which kexts list as libraries
        elif '_PrelinkExecutableLoadAddr' not in entry and set(entry.get('OSBundleLibraries', {})) <= (keep | resources):
            entries.append(entry)        # personality-only bundles whose libraries survive
    entries.extend(native_entries)
    plist['_PrelinkInfoDictionary'] = entries
    blob = plistlib.dumps(plist, fmt=plistlib.FMT_XML) + b'\0'
    info_size = up(len(blob))
    if info_start + info_size > data_start:
        raise SystemExit('pruned prelink info does not fit before __DATA')
    image[info_start:info_start + len(blob)] = blob
    data_end = seg_end['__DATA']
    top += [('__PRELINK_INFO', info_start, info_size), ('__DATA', data_start, data_end - data_start)]

    # 5. LINKEDIT: KC265's, then the kernel's symbol table and string table, then the chained fixups blob.
    linkedit_old = next(s for s in kc.segments if s['name'] == '__LINKEDIT')
    linkedit_start = old_off(linkedit_old['va'])
    kernel_linkedit = kc.macho('com.apple.kernel')['segments']
    shared_start = old_off(next(s for s in kernel_linkedit if s['name'] == '__LINKEDIT')['va'])
    end = len(image)
    symoff, nsyms, stroff, strsize = kernel.symtab
    image.extend(bytes(up(end, 16) - end))
    new_symoff = len(image)
    image.extend(kernel.data[symoff:symoff + nsyms * 16])
    new_stroff = len(image)
    image.extend(kernel.data[stroff:stroff + strsize])
    image.extend(bytes(up(len(image), 8) - len(image)))
    # chained fixups blob
    order = ['__TEXT', '__PRELINK_TEXT', '__DATA_CONST', '__TEXT_EXEC', '__PRELINK_INFO', '__DATA', '__LINKEDIT']
    layout = {name: (start, size) for name, start, size in top}
    per_seg = {}
    for va, (target, auth, diversity, addr_div, key) in sites.items():
        flat = new_off(va)
        for name in ('__DATA_CONST', '__DATA'):
            start, size = layout[name]
            if start <= flat < start + size:
                per_seg.setdefault(name, {})[flat] = (target, auth, diversity, addr_div, key)
                break
        else:
            raise SystemExit(f'pointer at {va:#x} is outside __DATA_CONST/__DATA')
    starts_blobs = {}
    for name, found in per_seg.items():
        start, size = layout[name]
        pages = size // PAGE
        page_starts = [0xffff] * pages
        chains = {}
        for flat in sorted(found):
            chains.setdefault((flat - start) // PAGE, []).append(flat)
        for page, flats in chains.items():
            page_starts[page] = (flats[0] - start) % PAGE
            for index, flat in enumerate(flats):
                target, auth, diversity, addr_div, key = found[flat]
                step = 0
                if index + 1 < len(flats):
                    delta = flats[index + 1] - flat
                    if delta % 4 or delta // 4 > 0xfff:
                        raise SystemExit(f'chain step {delta:#x} at {flat:#x} does not fit')
                    step = delta // 4
                value = target | (step << 51)
                if auth:
                    value |= diversity << 32 | int(addr_div) << 48 | key << 49 | 1 << 63
                struct.pack_into('<Q', image, flat, value)
        starts_blobs[name] = struct.pack('<IHHQIH', 22 + 2 * pages, PAGE, 8, start, 0, pages) + struct.pack(f'<{pages}H', *page_starts)
    offsets, body = [], b''
    base_offset = 4 + 4 * len(order)
    for name in order:
        if name in starts_blobs:
            offsets.append(base_offset + len(body))
            body += starts_blobs[name] + bytes(up(len(starts_blobs[name]), 8) - len(starts_blobs[name]))
        else:
            offsets.append(0)
    starts_in_image = struct.pack('<I', len(order)) + struct.pack(f'<{len(order)}I', *offsets) + body
    fixups = struct.pack('<7I', 0, 28, 28 + len(starts_in_image), 28 + len(starts_in_image), 0, 1, 0) + starts_in_image + bytes(8)
    fixups += bytes(up(len(fixups), 8) - len(fixups))
    new_fixups = len(image)
    image.extend(fixups)
    image.extend(bytes(up(len(image)) - len(image)))
    linkedit_end = len(image)

    # 6. Load commands: collection header, kernel entry, kept kexts.
    kernel_text_flat = new_off(kernel.segment('__TEXT')['va'])
    header = build_kernel_header(kernel, placed, shared_start, linkedit_end, new_symoff, nsyms, new_stroff, strsize)
    if len(header) > kernel.segment('__TEXT')['sections'][0]['fileoff']:
        raise SystemExit('kernel header outgrew the space before its first section')
    image[kernel_text_flat:kernel_text_flat + len(header)] = header
    image[kernel_text_flat + len(header):kernel_text_flat + kernel.segment('__TEXT')['sections'][0]['fileoff']] = bytes(
        kernel.segment('__TEXT')['sections'][0]['fileoff'] - len(header))
    kmod_info = {e['CFBundleIdentifier']: e['_PrelinkKmodInfo'] for e in plist_entries_original if '_PrelinkKmodInfo' in e}
    for text_va, segs, spec in native_commands:
        header = kext_header(segs, uuid.uuid5(uuid.NAMESPACE_URL, spec['bundle']).bytes, shared_start, linkedit_end)
        if len(header) > 0x800:
            raise SystemExit('native kext header outgrew its reserve')
        image[new_off(text_va):new_off(text_va) + len(header)] = header
    for name in keep:
        shift_entry(kc, image, name, old_off, shift, shared_start, linkedit_end)
        # kmod_info_t is packed: address sits at +156 and is the one raw (unchained) absolute address a kext carries; OSKext adds the slide to it
        at = old_off(kmod_info[name] & (2 ** 64 - 1)) + 156
        address, = struct.unpack_from('<Q', image, at)
        if address != kc.entries[name]['va']:
            raise SystemExit(f'{name}: kmod_info.address {address:#x} is not the header address')
        struct.pack_into('<Q', image, at, address + shift)

    commands = []
    for cmd, raw in parse_commands(kc.data):
        if cmd == LC_SEGMENT_64:
            name = cstr(raw[8:24])
            if name == '__LINKEDIT':
                raw = segment_command(name, NEW_BASE + linkedit_start, linkedit_end - linkedit_start, linkedit_start, linkedit_end - linkedit_start, raw)
            else:
                start, size = layout[name]
                raw = segment_command(name, NEW_BASE + start, size, start, size, raw)
                raw = patch_sections(raw, lambda sec: dict(sec, addr=sec['addr'] + shift, size=info_size if name == '__PRELINK_INFO' else sec['size']))
        elif cmd == LC_FILESET_ENTRY:
            entry = cstr(raw[struct.unpack_from('<I', raw, 24)[0]:])
            if entry == 'com.apple.kernel':
                raw = fileset_entry(entry, kernel.segment('__TEXT')['va'], kernel_text_flat)
            elif entry in keep:
                va, = struct.unpack_from('<Q', raw, 8)
                raw = fileset_entry(entry, va + shift, old_off(va))
            else:
                continue
        elif cmd == LC_UNIXTHREAD:
            raw = kernel.command(LC_UNIXTHREAD)
        elif cmd == LC_CHAINED_FIXUPS:
            raw = struct.pack('<IIII', LC_CHAINED_FIXUPS, 16, new_fixups, len(fixups))
        commands.append(raw)
    for text_va, segs, spec in native_commands:
        commands.append(fileset_entry(spec['bundle'], text_va, new_off(text_va)))
    blob_cmds = b''.join(commands)
    head = struct.pack('<8I', 0xfeedfacf, 0x100000c, kc.subtype, 12, len(commands), len(blob_cmds), struct.unpack_from('<I', kc.data, 24)[0], 0)
    if 32 + len(blob_cmds) > 0x4000:
        raise SystemExit('collection header does not fit its page')
    image[0:0x4000] = head + blob_cmds + bytes(0x4000 - 32 - len(blob_cmds))
    Path(args.output).write_bytes(image)
    print(f'wrote {args.output}: {len(image):#x} bytes, base {NEW_BASE:#x}, {len(sites)} chained pointers')


def check_vtable(kc, linked, kept_sites, spec, shift, old_off):
    """A driver class derived from a class of a kext must have the slots of that class where the kext expects them: every slot the driver
    does not override must hold exactly what the base class has there. Prints the mismatching slots."""
    base_symbol = '__ZTV' + str(len(spec['base'])) + spec['base']
    own_symbol = '__ZTV' + str(len(spec['class'])) + spec['class']
    base_va = None
    for name, kind, sect, desc, value in kc.symbols(kc.macho(spec['base_kext'])):
        if name == base_symbol:
            base_va = value + shift
    if base_va is None or own_symbol not in linked['symbols']:
        raise SystemExit(f'vtable check: cannot find {base_symbol} / {own_symbol}')
    own_va = linked['symbols'][own_symbol]
    own_sites = {s[0]: s[1] for s in linked['sites']}
    text = linked['segments']['__TEXT_EXEC']
    in_driver = lambda va: text['va'] <= va < text['va'] + len(text['data'])   # noqa: E731  its own functions, also the local ones
    bad = 0
    for slot in range(spec['slots']):
        if slot in spec.get('ignore_slots', ()):
            continue
        theirs = kept_sites.get(base_va + 16 + slot * 8)
        ours = own_sites.get(own_va + 16 + slot * 8)
        if ours is None or ours == theirs:
            if ours is None:
                print(f'  vtable slot {slot}: not filled in the driver\'s vtable')
                bad += 1
            continue
        if not in_driver(ours):
            print(f'  vtable slot {slot}: driver {ours:#x} is neither the base class\'s {theirs and hex(theirs)} nor one of its own functions')
            bad += 1
    print(f'vtable check {spec["class"]} vs {spec["base"]}: {bad} problem slots')


def seg_start_of(kc, name, old_off):
    return old_off(next(s for s in kc.segments if s['name'] == name)['va'])


def seg_end_of(kc, name, old_off):
    segment = next(s for s in kc.segments if s['name'] == name)
    return old_off(segment['va']) + segment['size']


def to_signed(value):
    return value - (1 << 64) if value >> 63 else value


def kext_header(segs, uuid_bytes, shared_start, linkedit_end):
    """Mach-O header of a kext we linked: MH_KEXT_BUNDLE with its four segments, the collection's shared LINKEDIT and no symbols."""
    prot = {'__TEXT': 1, '__TEXT_EXEC': 5, '__DATA': 3, '__DATA_CONST': 3}
    commands = []
    for name in ('__TEXT', '__TEXT_EXEC', '__DATA', '__DATA_CONST'):
        seg = segs[name]
        sections = b''
        for sect, va, size, flags in seg['sections']:
            zerofill = flags & 0xff in (1, 0xc, 0x12)
            sections += struct.pack('<16s16s2Q8I', sect.encode(), name.encode(), va, size, 0 if zerofill else va - NEW_BASE, 4, 0, 0, flags, 0, 0, 0)
        size = len(seg['data'])
        commands.append(struct.pack('<II16s4Q4I', LC_SEGMENT_64, 72 + len(sections), name.encode(), seg['va'], size, seg['va'] - NEW_BASE, size,
                                    prot[name], prot[name], len(seg['sections']), 0) + sections)
    commands.append(struct.pack('<II16s4Q4I', LC_SEGMENT_64, 72, b'__LINKEDIT', NEW_BASE + shared_start, linkedit_end - shared_start, shared_start,
                                linkedit_end - shared_start, 1, 1, 0, 0))
    commands.append(struct.pack('<IIIIII', LC_SYMTAB, 24, shared_start, 0, shared_start, 0))
    commands.append(struct.pack('<II16s', 0x1b, 24, uuid_bytes))
    body = b''.join(commands)
    return struct.pack('<8I', 0xfeedfacf, 0x100000c, 0xc0000002, 11, len(commands), len(body), 0x80000085, 0) + body


def seal_fips(kc, image, name, old_off):
    """corecrypto's POST checks HMAC-SHA256 (one zero byte as key) of the kext's __TEXT_EXEC,__text against __TEXT,__fips_hmacs, which
    the collection builder fills in after layout (fipspost_get_hmac.c, hmacfiletool). The retargeted branches change those bytes."""
    segments = {s['name']: s for s in kc.macho(name)['segments']}
    holder = next((x for x in segments['__TEXT']['sections'] if x['name'] == '__fips_hmacs'), None)
    if holder is None:
        return
    text = next(x for x in segments['__TEXT_EXEC']['sections'] if x['name'] == '__text')
    at = old_off(text['va'])
    mac = hmac.digest(b'\0', bytes(image[at:at + text['size']]), 'sha256')
    image[old_off(holder['va']):old_off(holder['va']) + 32] = mac
    print(f'{name}: __fips_hmacs sealed over {text["size"]:#x} bytes of __text')


def parse_commands(data):
    count, size = struct.unpack_from('<II', data, 16)
    offset = 32
    for _ in range(count):
        cmd, length = struct.unpack_from('<II', data, offset)
        yield cmd, bytes(data[offset:offset + length])
        offset += length


def parse_sections(raw):
    nsects, = struct.unpack_from('<I', raw, 64)
    out = []
    for index in range(nsects):
        sname, sseg, addr, size, offset, align, reloff, nreloc, flags, r1, r2, r3 = struct.unpack_from('<16s16s2Q8I', raw, 72 + index * 80)
        out.append({'name': sname, 'segment': sseg, 'addr': addr, 'size': size, 'offset': offset, 'align': align, 'flags': flags})
    return out


def segment_command(name, vmaddr, vmsize, fileoff, filesize, raw):
    """Copy of the segment command RAW with new extents (sections are kept as they are)."""
    out = bytearray(raw)
    struct.pack_into('<4Q', out, 24, vmaddr, vmsize, fileoff, filesize)
    return bytes(out)


def patch_sections(raw, change):
    out = bytearray(raw)
    for index, section in enumerate(parse_sections(raw)):
        new = change(section)
        struct.pack_into('<QQ', out, 72 + index * 80 + 32, new['addr'], new['size'])
    return bytes(out)


def fileset_entry(name, vmaddr, fileoff):
    body = struct.pack('<QQI4x', vmaddr, fileoff, 32) + name.encode() + b'\0'
    length = up(8 + len(body), 8)
    return struct.pack('<II', LC_FILESET_ENTRY, length) + body + bytes(length - 8 - len(body))


def build_kernel_header(kernel, placed, shared_start, linkedit_end, symoff, nsyms, stroff, strsize):
    commands = []
    placed_by_name = {s['name']: s for s in placed}
    for cmd, raw in kernel.commands:
        if cmd == LC_SEGMENT_64:
            name = cstr(raw[8:24])
            out = bytearray(raw)
            va, size = struct.unpack_from('<2Q', out, 24)
            if name == '__LINKEDIT':
                start = shared_start
                struct.pack_into('<4Q', out, 24, NEW_BASE + start, linkedit_end - start, start, linkedit_end - start)
            else:
                if name == '__LINKINFO':
                    va = placed_by_name[name]['va']
                    struct.pack_into('<Q', out, 24, va)
                struct.pack_into('<2Q', out, 40, va - NEW_BASE, size)           # flat file offset, filesize = vmsize
                for index, section in enumerate(parse_sections(raw)):
                    at = 72 + index * 80
                    flags = section['flags'] & 0xff
                    sva = section['addr']
                    if name == '__LINKINFO':
                        sva = va + (section['addr'] - struct.unpack_from('<Q', raw, 24)[0])
                        struct.pack_into('<Q', out, at + 32, sva)
                    zerofill = flags in (1, 0xc, 0x12)
                    struct.pack_into('<I', out, at + 48, 0 if zerofill else sva - NEW_BASE)
                    struct.pack_into('<II', out, at + 56, 0, 0)                  # no relocations
            commands.append(bytes(out))
        elif cmd == LC_SYMTAB:
            commands.append(struct.pack('<IIIIII', LC_SYMTAB, 24, symoff, nsyms, stroff, strsize))
        elif cmd == LC_DYSYMTAB:
            out = bytearray(raw)
            out[32:80] = bytes(48)   # toc, modtab, extref, indirect and relocation tables are not carried over
            commands.append(bytes(out))
        elif cmd in (LC_SPLIT_INFO, LC_FUNCTION_STARTS):
            continue
        else:
            commands.append(raw)
    body = b''.join(commands)
    return struct.pack('<8I', 0xfeedfacf, 0x100000c, kernel.subtype, 2, len(commands), len(body), kernel.flags | MH_DYLIB_IN_CACHE, 0) + body


def shift_entry(kc, image, name, old_off, shift, shared_start, linkedit_end):
    """Move a kept kext's Mach-O header (segment/section addresses, LINKEDIT extent) and its defined symbol values by SHIFT."""
    entry = kc.entries[name]
    at = old_off(entry['va'])
    count, size = struct.unpack_from('<II', image, at + 16)
    offset = at + 32
    symtab = None
    for _ in range(count):
        cmd, length = struct.unpack_from('<II', image, offset)
        if cmd == LC_SEGMENT_64:
            vmaddr, = struct.unpack_from('<Q', image, offset + 24)
            if cstr(image[offset + 8:offset + 24]) == '__LINKEDIT':
                struct.pack_into('<QQQQ', image, offset + 24, NEW_BASE + shared_start, linkedit_end - shared_start, shared_start, linkedit_end - shared_start)
            else:
                struct.pack_into('<Q', image, offset + 24, vmaddr + shift)
                for index in range(struct.unpack_from('<I', image, offset + 64)[0]):
                    sat = offset + 72 + index * 80 + 32
                    struct.pack_into('<Q', image, sat, struct.unpack_from('<Q', image, sat)[0] + shift)
        elif cmd == LC_SYMTAB:
            symtab = struct.unpack_from('<4I', image, offset + 8)
        offset += length
    if symtab:
        symoff, nsyms, stroff, strsize = symtab
        for index in range(nsyms):
            sat = symoff + index * 16
            strx, kind, sect, desc, value = struct.unpack_from('<IBBHQ', image, sat)
            if not kind & 0xe0 and kind & 0x0e == 0x0e:
                struct.pack_into('<Q', image, sat + 8, value + shift)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kc')
    parser.add_argument('kernel')
    parser.add_argument('output')
    parser.add_argument('--keep', nargs='*', default=[])
    parser.add_argument('--native', nargs='*', default=[], help='JSON descriptions of drivers to link in as kexts of their own (see docs)')
    build(parser.parse_args())


main()
