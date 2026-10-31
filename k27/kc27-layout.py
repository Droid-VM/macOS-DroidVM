#!/usr/bin/env python3
"""Segment addresses of the source-built kernel inside the macOS 27 kernelcache (the kc-segaddrs.sh of kc265, redone for kc27).

    kc27-layout.py [KC27] [KERNEL.macho] [--write k27/segaddrs.sh]

Same scheme as out/x12377/kc-segaddrs.sh (docs/xnu-12377-port.md, "fileset KC 方案"): the kexts kept stay where they are, the kernel
takes Apple's kernel slots, and where ours is larger it grows into the space of dropped kexts: __TEXT from 0x4000 into __PRELINK_TEXT,
__TEXT_EXEC at Apple's start, __KLD/__LAST at Apple's (__LAST must stay inside the KC's __TEXT_EXEC), __LASTDATA_CONST inside the KC's
__DATA_CONST, __KLDDATA/__DATA/__BOOTDATA end where Apple's __BOOTDATA ends (they start earlier, in the tail of __PRELINK_INFO, which
kc-build prunes), __PRELINK_* empty markers after them (__PRELINK_DATA starts the kexts' __DATA), __LINKINFO at Apple's.
Every placement is checked against the segments of the kexts any configuration may keep (configs/kc-keep.txt and every native's
libraries, with their dependency closure); MARGIN of growth is required beyond the given kernel's sizes.
"""
import argparse
import json
import plistlib
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import fileset_kc  # noqa: E402

KB = 0xfffffff007004000
PAGE = 0x4000
MARGIN = 0x10000
GROWS = ('__TEXT', '__DATA_CONST', '__TEXT_EXEC', '__DATA', '__BOOTDATA')   # segments given MARGIN of room to grow
# kc27 keeps com.apple.kec.Libm and pthread right after Apple's kernel __TEXT (0x11c000), and our DEVELOPMENT kernel's __TEXT is
# 0x188000 (its __cstring alone +0x64000): __TEXT,__cstring is linked into __TEXT_EXEC instead (no kernel code looks it up by section;
# os_log formats stay in __TEXT,__os_log, which resolve_dso checks), where kc27 has room.
MOVE = '-Wl,-rename_section,__TEXT,__cstring,__TEXT_EXEC,__cstring'


def up(v, a=PAGE):
    return (v + a - 1) // a * a


def kernel_sizes(path):
    """Segment sizes of a kernel, as if __TEXT,__cstring were in __TEXT_EXEC (MOVE) when it is not yet."""
    data = Path(path).read_bytes()
    count, = struct.unpack_from('<I', data, 16)
    off, sizes, cstring = 32, {}, 0
    for _ in range(count):
        cmd, length = struct.unpack_from('<II', data, off)
        if cmd == 0x19:
            name = data[off + 8:off + 24].split(b'\0')[0].decode()
            sizes[name] = struct.unpack_from('<Q', data, off + 32)[0]
            for index in range(struct.unpack_from('<I', data, off + 64)[0]):
                at = off + 72 + index * 80
                if name == '__TEXT' and data[at:at + 16].split(b'\0')[0] == b'__cstring':
                    cstring = struct.unpack_from('<Q', data, at + 40)[0]
        off += length
    if cstring:
        sizes['__TEXT'] = up(sizes['__TEXT'] - cstring)
        sizes['__TEXT_EXEC'] = up(sizes['__TEXT_EXEC'] + cstring)
    return sizes


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('kc', nargs='?', default=str(ROOT / 'out/kc/kc27.bin'))
    p.add_argument('kernel', nargs='?', default=str(ROOT / 'out/x12377/kernel12377e-osx-kc.macho'))
    p.add_argument('--write')
    a = p.parse_args()
    kc = fileset_kc.Kernelcache(Path(a.kc).read_bytes())
    base = kc.base
    rel = lambda va: va - base  # noqa: E731
    top = {s['name']: (rel(s['va']), rel(s['va']) + s['size']) for s in kc.segments}
    apple = {s['name']: (rel(s['va']), rel(s['va']) + s['size']) for s in kc.macho('com.apple.kernel')['segments'] if s['size']}

    prelink = kc.segments[[s['name'] for s in kc.segments].index('__PRELINK_INFO')]['sections'][0]
    info = plistlib.loads(kc.data[prelink['fileoff']:prelink['fileoff'] + prelink['size']].split(b'\0')[0])['_PrelinkInfoDictionary']
    by_id = {e['CFBundleIdentifier']: e for e in info}
    roots = (ROOT / 'configs/kc-keep.txt').read_text().split()
    stand_ins = set()
    for spec in (ROOT / 'overlay/kext').glob('*.json'):
        j = json.loads(spec.read_text())
        roots += list(j.get('libraries', {}))
        stand_ins |= set(j.get('stands_in_for', []))
    keep, todo = set(), list(roots)
    while todo:
        n = todo.pop()
        if n in keep or n not in by_id or n in stand_ins:
            continue
        keep.add(n)
        todo += list(by_id[n].get('OSBundleLibraries', {}))
    keep &= set(kc.entries)
    used = sorted((rel(s['va']), rel(s['va']) + s['size'], n) for n in keep for s in kc.macho(n)['segments']
                  if s['size'] and s['name'] != '__LINKEDIT')
    print(f'{len(keep)} kexts may be kept')

    ours = kernel_sizes(a.kernel)
    need = {n: up(ours[n] + (MARGIN if n in GROWS else 0)) for n in ours}
    place = {}
    place['__TEXT'] = 0x4000
    place['__DATA_CONST'] = apple['__DATA_CONST'][0]
    place['__LASTDATA_CONST'] = apple['__LASTDATA_CONST'][0]
    place['__TEXT_EXEC'] = apple['__KLD'][0] - need['__TEXT_EXEC']   # ends where Apple's __KLD starts
    place['__KLD'] = apple['__KLD'][0]
    place['__LAST'] = apple['__LAST'][0]
    data = need['__KLDDATA'] + need['__DATA'] + need['__BOOTDATA']
    end = apple['__BOOTDATA'][1]
    place['__KLDDATA'] = end - data
    place['__DATA'] = place['__KLDDATA'] + need['__KLDDATA']
    place['__BOOTDATA'] = place['__DATA'] + need['__DATA']
    place['__PRELINK_TEXT'] = top['__PRELINK_INFO'][0]
    place['__LINKINFO'] = apple['__LINKINFO'][0]
    empties = ['__PRELINK_DATA', '__PRELINK_INFO', '__PLK_TEXT_EXEC', '__PLK_DATA_CONST', '__PLK_LLVM_COV', '__PLK_LINKEDIT']

    bad = False
    checks = [('__TEXT', top['__PRELINK_TEXT']), ('__DATA_CONST', top['__DATA_CONST']), ('__LASTDATA_CONST', top['__DATA_CONST']),
              ('__TEXT_EXEC', top['__TEXT_EXEC']), ('__KLD', top['__TEXT_EXEC']), ('__LAST', top['__TEXT_EXEC']),
              ('__KLDDATA', (top['__PRELINK_INFO'][0], top['__DATA'][1])), ('__DATA', (top['__PRELINK_INFO'][0], top['__DATA'][1])),
              ('__BOOTDATA', top['__DATA'])]
    spans = []
    for name, (lo, hi) in checks:
        s, e = place[name], place[name] + need[name]
        spans.append((s, e, name))
        hits = [n for u0, u1, n in used if u0 < e and s < u1]
        inside = lo <= s and e <= hi
        print(f'{name:18} {s:#10x}-{e:#10x} ours {ours.get(name, 0):#9x} {"ok" if inside and not hits else "CONFLICT"}'
              + (f' outside {lo:#x}-{hi:#x}' if not inside else '') + (f' kexts {sorted(set(hits))[:4]}' if hits else ''))
        bad |= bool(hits) or not inside
    spans.sort()
    for (s0, e0, n0), (s1, e1, n1) in zip(spans, spans[1:]):
        if s1 < e0:
            print(f'overlap {n0} / {n1}')
            bad = True
    if ours.get('__LINKINFO', 0) > apple['__LINKINFO'][1] - apple['__LINKINFO'][0]:
        print('__LINKINFO outgrows its slot')
        bad = True
    if place['__KLDDATA'] < top['__PRELINK_INFO'][0] + 0x100000:
        print('less than 1 MiB left for the pruned prelink info')
        bad = True
    o = up(place['__BOOTDATA'] + need['__BOOTDATA'])
    print(f'kc-build27: DATA_CONST_START={top["__DATA_CONST"][0]:#x} DATA_START={place["__KLDDATA"]:#x}; kext __DATA from {o + len(empties) * PAGE:#x}')
    if bad:
        raise SystemExit('layout does not fit')
    if a.write:
        lines = ['# -segaddr list for linking the kernel into the kc27 fileset KC (generated by k27/kc27-layout.py; offsets from the KC header page)',
                 f'KB={KB:#x}', f'echo -n "{MOVE} "', 'a() { printf -- "-Wl,-segaddr,%s,0x%x " "$1" $((KB + $2)); }', '{']
        lines.append(' '.join(f'a {n} {place[n]:#x};' for n in ('__TEXT', '__DATA_CONST', '__LASTDATA_CONST', '__TEXT_EXEC', '__KLD', '__LAST',
                                                                  '__KLDDATA', '__DATA', '__BOOTDATA', '__PRELINK_TEXT')))
        lines.append(f'o={o:#x}; for n in {" ".join(empties)}; do a $n $o; o=$((o+{PAGE:#x})); done')
        lines.append(f'a __LINKINFO {place["__LINKINFO"]:#x}')
        lines.append("} | sed 's/ $//'")
        Path(a.write).write_text('\n'.join(lines) + '\n')
        Path(a.write).with_suffix('.json').write_text(json.dumps({'DATA_CONST_START': top['__DATA_CONST'][0], 'DATA_START': place['__KLDDATA']}) + '\n')
        print('wrote', a.write)


main()
