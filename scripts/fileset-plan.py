#!/usr/bin/env python3
"""Plan (read-only report) of borrowing kexts from an MH_FILESET kernelcache: what they bind to and what must be rewritten.

    fileset-plan.py KERNELCACHE.decompressed BUNDLE_ID [BUNDLE_ID ...] [--output FILE]
"""
import argparse
import bisect
import collections
import json
from pathlib import Path
import plistlib
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fileset_kc  # noqa: E402


def decode_branch(word, pc):
    if word & 0x7c000000 == 0x14000000:
        imm = word & 0x3ffffff
        if imm & 0x2000000:
            imm -= 1 << 26
        return pc + imm * 4, bool(word & 0x80000000)
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernelcache')
    parser.add_argument('bundles', nargs='+')
    parser.add_argument('--output')
    args = parser.parse_args()
    kc = fileset_kc.Kernelcache(Path(args.kernelcache).read_bytes())
    machos = {name: kc.macho(name) for name in kc.entries}
    # Owner ranges of every entry's non-LINKEDIT segments.
    ranges = []
    for name, macho in machos.items():
        for segment in macho['segments']:
            if segment['size'] and segment['name'] != '__LINKEDIT':
                ranges.append((segment['va'], segment['va'] + segment['size'], name))
    ranges.sort()
    starts = [r[0] for r in ranges]

    def owner(va):
        index = bisect.bisect_right(starts, va) - 1
        return ranges[index][2] if index >= 0 and va < ranges[index][1] else None

    # Address -> names per entry, from each entry's symbol table (defined symbols only).
    names_at = collections.defaultdict(dict)

    def symbol_names(entry):
        if entry not in names_at:
            table = {}
            for name, kind, sect, desc, value in kc.symbols(machos[entry]):
                if kind & 0x0e and not kind & 0xe0:
                    table.setdefault(value, name)
            names_at[entry] = table
        return names_at[entry]

    sites = collections.defaultdict(list)
    for site, value, target, auth, diversity, addr_div, key in kc.chained_sites():
        who = owner(site)
        if who:
            sites[who].append((site, target, auth))
    report = {}
    for bundle in args.bundles:
        macho = machos[bundle]
        result = {'pointer_sites': len(sites[bundle]), 'pointer_auth': sum(1 for s in sites[bundle] if s[2]), 'pointer_targets': collections.Counter(),
                  'pointer_unnamed': 0, 'pointer_names': collections.defaultdict(set)}
        for site, target, auth in sites[bundle]:
            to = owner(target)
            result['pointer_targets'][to or 'unowned'] += 1
            if to and to != bundle:
                name = symbol_names(to).get(target)
                if name is None:
                    result['pointer_unnamed'] += 1
                else:
                    result['pointer_names'][to].add(name)
        branches = collections.Counter()
        external_names = collections.defaultdict(set)
        unnamed = set()
        pauth_nonhint = collections.Counter()
        adrp_external = 0
        for segment in macho['segments']:
            if segment['name'] != '__TEXT_EXEC' or not segment['filesize']:
                continue
            blob = kc.data[segment['fileoff']:segment['fileoff'] + segment['filesize']]
            for at in range(0, len(blob) - 3, 4):
                word, = struct.unpack_from('<I', blob, at)
                pc = segment['va'] + at
                decoded = decode_branch(word, pc)
                if decoded:
                    to = owner(decoded[0])
                    if to != bundle:
                        branches['bl' if decoded[1] else 'b'] += 1
                        kind = to or 'unowned'
                        branches[kind] += 1
                        if to:
                            name = symbol_names(to).get(decoded[0])
                            (external_names[to].add(name) if name else unnamed.add(decoded[0]))
                if word & 0x9f000000 == 0x90000000:
                    imm = ((word >> 5) & 0x7ffff) << 2 | ((word >> 29) & 3)
                    if imm & (1 << 20):
                        imm -= 1 << 21
                    page = (pc & ~0xfff) + (imm << 12)
                    to = owner(page + 0x10)
                    if to and to != bundle and not any(s['va'] <= page < s['va'] + s['size'] for s in macho['segments'] if s['size']):
                        adrp_external += 1
                if word & 0xfffffc1f in (0xd65f0bff, 0xd61f0bff, 0xd63f0bff) or word & 0xfffffc00 in (0xd71f0800, 0xd73f0800, 0xd71f0c00, 0xd73f0c00) \
                        or word & 0xfffffbe0 in (0xdac11000, 0xdac10000):
                    pauth_nonhint[hex(word & 0xfffffc00)] += 1
        result.update(branches=dict(branches), branch_external_names={k: len(v) for k, v in external_names.items()},
                      branch_unnamed_targets=len(unnamed), adrp_external=adrp_external, pauth_nonhint=dict(pauth_nonhint))
        result['pointer_targets'] = dict(result['pointer_targets'])
        result['pointer_names'] = {k: sorted(v) for k, v in result['pointer_names'].items()}
        report[bundle] = result
    text = json.dumps(report, indent=2, default=list) + '\n'
    if args.output:
        Path(args.output).write_text(text)
    summary = {b: {k: (v if not isinstance(v, (dict, list)) else (len(v) if k.endswith('names') else v)) for k, v in r.items()} for b, r in report.items()}
    print(json.dumps(summary, indent=1, default=list))


if __name__ == '__main__':
    main()
