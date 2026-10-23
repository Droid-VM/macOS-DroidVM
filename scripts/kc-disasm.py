#!/usr/bin/env python3
"""Disassemble code of a kext (or any address) in a fileset kernelcache, naming branch targets from the entries' symbol tables.

    kc-disasm.py KC ADDRESS [COUNT]
"""
import bisect
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fileset_kc  # noqa: E402

kc = fileset_kc.Kernelcache(Path(sys.argv[1]).read_bytes())
va = int(sys.argv[2], 16)
count = int(sys.argv[3]) if len(sys.argv) > 3 else 40
names = []
for entry in kc.entries:
    for name, kind, sect, desc, value in kc.symbols(kc.macho(entry)):
        if kind & 0x0e == 0x0e and not kind & 0xe0:
            names.append((value, f'{entry.split(".")[-1]}:{name}'))
names.sort()
keys = [n[0] for n in names]


def label(address):
    i = bisect.bisect_right(keys, address) - 1
    return f'{names[i][1]}+{address - names[i][0]:#x}' if i >= 0 else '?'


raw = kc.data[va - kc.base:va - kc.base + count * 4]
print(f'{va:#x} {label(va)}')
for i in range(count):
    word, = struct.unpack_from('<I', raw, i * 4)
    text = subprocess.run(['llvm-mc', '--disassemble', '--triple=arm64e-apple-darwin', '-mattr=+v8.5a,+pauth'], input=' '.join(f'0x{b:02x}' for b in raw[i * 4:i * 4 + 4]),
                          capture_output=True, text=True).stdout.strip().splitlines()
    line = text[-1].strip() if text else f'.word {word:#x}'
    pc = va + i * 4
    if word & 0x7c000000 == 0x14000000:
        imm = word & 0x3ffffff
        imm -= (1 << 26) if imm >> 25 else 0
        line += f'   ; -> {label(pc + imm * 4)}'
    print(f'{pc:#x}  {line}')
