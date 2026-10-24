#!/usr/bin/env python3
"""Find the code of a dyld shared cache subcache that loads an address (adrp + add/ldr pairs): dsc-xref.py SUBCACHE ADDRESS [LOW HIGH]

Scans the instruction words of the subcache's mappings (or LOW..HIGH, e.g. one image's __TEXT from the .map file) and prints the
pc of every adrp whose page, plus the following add/ldr's offset, gives ADDRESS."""
import struct
import sys

data = open(sys.argv[1], 'rb').read()
target = int(sys.argv[2], 16)
mo, mc = struct.unpack_from('<II', data, 0x10)
maps = [struct.unpack_from('<QQQII', data, mo + i * 32) for i in range(mc)]
low, high = (int(sys.argv[3], 16), int(sys.argv[4], 16)) if len(sys.argv) > 4 else (0, 1 << 64)
for address, size, fileoff, _, _ in maps:
    start, end = max(address, low), min(address + size, high)
    for pc in range(start & ~3, end - 4, 4):
        word, = struct.unpack_from('<I', data, fileoff + pc - address)
        if word & 0x9f000000 != 0x90000000:
            continue
        imm = (word >> 5 & 0x7ffff) << 2 | word >> 29 & 3
        imm -= (1 << 21) if imm >> 20 else 0
        page = (pc & ~0xfff) + (imm << 12)
        if page != target & ~0xfff:
            continue
        reg = word & 31
        for k in range(1, 8):
            nxt, = struct.unpack_from('<I', data, fileoff + pc - address + 4 * k)
            if nxt & 0xffc00000 == 0x91000000 and nxt >> 5 & 31 == reg and page + (nxt >> 10 & 0xfff) == target:
                print(f'{pc:#x} add'); break
            if nxt & 0xffc00000 == 0xf9400000 and nxt >> 5 & 31 == reg and page + (nxt >> 10 & 0xfff) * 8 == target:
                print(f'{pc:#x} ldr'); break
