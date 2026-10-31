#!/usr/bin/env python3
"""Symbolize k27 kernel addresses: the kernel's (out/rig/kc-k27.nm) or a kc27 kext's symbol + offset.

    k27/sym.py ADDRESS...          or      k27/sym.py < dmesg      (rewrites the hex words of "k27-stall:" lines)

KC addresses are kc27's plus SHIFT (scripts/kc-build.py moves the collection from 0xfffffe0007004000 to 0xfffffff007004000).
"""
import bisect
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import fileset_kc  # noqa: E402

SHIFT = 0xfffffff007004000 - 0xfffffe0007004000
table = []
for line in (ROOT / 'out/rig/kc-k27.nm').read_text().splitlines():
    parts = line.split()
    if len(parts) == 3 and parts[1] in 'tTsS':
        table.append((int(parts[0], 16), 'kernel:' + parts[2]))
kc = fileset_kc.Kernelcache((ROOT / 'out/kc/kc27.bin').read_bytes())
# only the kexts the last k27 KC kept: the space of the others holds our kernel and the native kexts now
log = (ROOT / 'out/k27/kc-build.log').read_text()
kept = set(re.findall(r"'([\w.]+)'", log[log.index('keeping'):].splitlines()[0]))
for name, address in json.loads((ROOT / 'out/k27/kc-k27.natives.json').read_text()).items():
    table.append((address, 'native:' + name))
for entry in kc.entries:
    if entry == 'com.apple.kernel' or entry not in kept:
        continue
    short = entry.split('.')[-1]
    for name, kind, sect, desc, value in kc.symbols(kc.macho(entry)):
        if value and kind & 0x0e == 0x0e:
            table.append((value + SHIFT, f'{short}:{name}'))
table.sort()
starts = [t[0] for t in table]


def name(address):
    i = bisect.bisect_right(starts, address) - 1
    if i < 0 or address - starts[i] > 0x20000:
        return hex(address)
    return f'{table[i][1]}+{address - starts[i]:#x}'


if len(sys.argv) > 1:
    for a in sys.argv[1:]:
        print(a, name(int(a, 16)))
else:
    for line in sys.stdin:
        if 'k27-stall: tid' not in line:
            continue
        head, _, frames = line.partition(':  ') if ':  ' in line else line.rpartition(':')
        print(line.split(':')[0] + ':' + line.split(':')[1].split('task')[0])
        for word in re.findall(r'\b[0-9a-f]{16}\b', line.split('event')[-1]):
            print('    ', name(int(word, 16)))
