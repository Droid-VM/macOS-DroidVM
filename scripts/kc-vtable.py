#!/usr/bin/env python3
"""Print the vtable of a class in a fileset kernelcache, slot by slot: the function each slot points to (named from the symbol tables
of every entry of the collection) and its PAC diversity (arm64e: the discriminator of the method's mangled name).

    kc-vtable.py KC CLASS [--base CLASS]      with --base, marks the slots CLASS overrides and stops at the base class's slot count

The slot count is the distance to the next symbol after __ZTV<CLASS>, minus the two header words and the padding (slots without a pointer).
"""
import argparse
import bisect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fileset_kc  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('kc', type=Path)
parser.add_argument('cls')
parser.add_argument('--base')
args = parser.parse_args()

kc = fileset_kc.Kernelcache(args.kc.read_bytes())
symbols, owner = [], {}
for entry in kc.entries:
    for name, kind, sect, desc, value in kc.symbols(kc.macho(entry)):
        if value and sect:
            symbols.append((value, name))
            owner[value] = entry
symbols.sort()
addresses = [a for a, _ in symbols]
by_name = {}
for value, name in symbols:
    by_name.setdefault(name, value)
sites = {site: (target, diversity) for site, raw, target, auth, diversity, addr_div, key in kc.chained_sites()}


def name_at(va):
    i = bisect.bisect_right(addresses, va) - 1
    if i < 0:
        return hex(va)
    base, name = symbols[i]
    return name if va == base else f'{name}+{va - base:#x}'


def vtable(cls):
    symbol = f'__ZTV{len(cls)}{cls}'
    if symbol not in by_name:
        sys.exit(f'no {symbol} in the collection')
    va = by_name[symbol]
    following = addresses[bisect.bisect_right(addresses, va)]
    count = (following - va) // 8 - 2
    while count and va + 16 + 8 * (count - 1) not in sites:   # padding up to the next symbol
        count -= 1
    return va, count, owner.get(va)


va, count, entry = vtable(args.cls)
base = None
if args.base:
    base_va, base_count, _ = vtable(args.base)
    base = [sites.get(base_va + 16 + 8 * slot, (None, None))[0] for slot in range(base_count)]
print(f'{args.cls}: {count} slots at {va:#x} ({entry})' + (f', base {args.base}: {len(base)} slots' if base else ''))
for slot in range(count):
    target, diversity = sites.get(va + 16 + 8 * slot, (None, None))
    mark = ''
    if base is not None:
        mark = '  ' if slot < len(base) and target == base[slot] else '* ' if slot < len(base) else '+ '
    print(f'{mark}{slot:4d} {diversity if diversity is not None else 0:#06x} {name_at(target) if target else "-"}')
