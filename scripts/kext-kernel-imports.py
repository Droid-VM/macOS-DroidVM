#!/usr/bin/env python3
"""Which kernel symbols do the kexts of an MH_FILESET kernelcache bind to, and does a source-built kernel define them?

    kext-kernel-imports.py KERNELCACHE KERNEL.macho [--bundles ID ...] [--output FILE]

Counts direct b/bl targets and chained data pointers that land in the cache's com.apple.kernel entry, resolves each to
the entry's symbol, and reports the names KERNEL.macho does not define (the symbols a binary relocator would have to
find another home for, or the kernel build is missing).
"""
import argparse
import bisect
import collections
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fileset_kc  # noqa: E402


def decode_branch(word, pc):
    if word & 0x7c000000 == 0x14000000:
        imm = word & 0x3ffffff
        if imm & 0x2000000:
            imm -= 1 << 26
        return pc + imm * 4
    return None


def our_symbols(path):
    data = path.read_bytes()
    magic, cpu, sub, kind, count, size = struct.unpack_from('<6I', data)
    off = 32
    for _ in range(count):
        cmd, length = struct.unpack_from('<II', data, off)
        if cmd == 2:
            symoff, nsyms, stroff, strsize = struct.unpack_from('<4I', data, off + 8)
            strings = data[stroff:stroff + strsize]
            names = set()
            for i in range(nsyms):
                strx, kind_, sect, desc, value = struct.unpack_from('<IBBHQ', data, symoff + i * 16)
                if kind_ & 0x0e == 0x0e:
                    names.add(strings[strings.find(b'\0', strx) and strx:strings.find(b'\0', strx)].decode(errors='replace'))
            return names
        off += length


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernelcache')
    parser.add_argument('kernel')
    parser.add_argument('--bundles', nargs='*')
    parser.add_argument('--output')
    args = parser.parse_args()
    kc = fileset_kc.Kernelcache(Path(args.kernelcache).read_bytes())
    kernel = kc.macho('com.apple.kernel')
    kernel_ranges = [(s['va'], s['va'] + s['size']) for s in kernel['segments'] if s['size'] and s['name'] != '__LINKEDIT']
    names_at = {}
    for name, kind, sect, desc, value in kc.symbols(kernel):
        if kind & 0x0e == 0x0e and value:
            names_at.setdefault(value, name)
    ours = our_symbols(Path(args.kernel))

    def in_kernel(va):
        return any(lo <= va < hi for lo, hi in kernel_ranges)

    owners = []
    for name in kc.entries:
        for segment in kc.macho(name)['segments']:
            if segment['size'] and segment['name'] != '__LINKEDIT':
                owners.append((segment['va'], segment['va'] + segment['size'], name))
    owners.sort()
    starts = [o[0] for o in owners]

    def owner(va):
        i = bisect.bisect_right(starts, va) - 1
        return owners[i][2] if i >= 0 and va < owners[i][1] else None

    wanted = set(args.bundles) if args.bundles else {n for n in kc.entries if n != 'com.apple.kernel'}
    users = collections.defaultdict(set)
    unnamed = collections.Counter()
    for bundle in sorted(wanted):
        macho = kc.macho(bundle)
        for segment in macho['segments']:
            if segment['name'] != '__TEXT_EXEC' or not segment['filesize']:
                continue
            blob = kc.data[segment['fileoff']:segment['fileoff'] + segment['filesize']]
            for at in range(0, len(blob) - 3, 4):
                word, = struct.unpack_from('<I', blob, at)
                if word & 0x7c000000 != 0x14000000:
                    continue
                target = decode_branch(word, segment['va'] + at)
                if in_kernel(target):
                    name = names_at.get(target)
                    if name:
                        users[name].add(bundle)
                    else:
                        unnamed[bundle] += 1
    for site, value, target, *_ in kc.chained_sites():
        who = owner(site)
        if who in wanted and in_kernel(target):
            name = names_at.get(target)
            if name:
                users[name].add(who)
            else:
                unnamed[who] += 1
    missing = {n: sorted(b) for n, b in users.items() if n not in ours}
    report = {'bound_names': len(users), 'missing_in_ours': len(missing), 'unnamed_targets': sum(unnamed.values()),
              'missing': {n: b[:4] for n, b in sorted(missing.items())}}
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != 'missing'}))
    for n, b in list(sorted(missing.items()))[:60]:
        print(' ', n, b[:3])


main()
