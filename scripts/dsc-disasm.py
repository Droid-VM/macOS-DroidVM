#!/usr/bin/env python3
"""Disassemble code in a dyld shared cache subcache: dsc-disasm.py SUBCACHE MAPFILE ADDRESS COUNT

Annotations: adrp+add/ldr: the C string there (when in this subcache); b/bl: the image (from the cache's .map file) the target lies
in, and for a stub (adrp x16 / ldr x16 / braa) the image of the pointer's target when the GOT is in this subcache."""
import bisect
import re
import struct
import subprocess
import sys

data = open(sys.argv[1], 'rb').read()
mo, mc = struct.unpack_from('<II', data, 0x10)
maps = [struct.unpack_from('<QQQII', data, mo + i * 32) for i in range(mc)]
images, current = [], None
for line in open(sys.argv[2]):
    if line.startswith('/'):
        current = line.strip().split('/')[-1]
    m = re.match(r'\s+(__\w+) (0x[0-9A-F]+) -> (0x[0-9A-F]+)', line)
    if m and current:
        images.append((int(m.group(2), 16), int(m.group(3), 16), current, m.group(1)))
images.sort()
starts = [i[0] for i in images]
va, count = int(sys.argv[3], 16), int(sys.argv[4])


def off(address):
    for a, size, fileoff, _, _ in maps:
        if a <= address < a + size:
            return fileoff + address - a
    return None


def image(address):
    i = bisect.bisect_right(starts, address) - 1
    return f'{images[i][2]}:{images[i][3]}+{address - images[i][0]:#x}' if i >= 0 and address < images[i][1] else hex(address)


def describe(address):
    o = off(address)
    if o is None:
        return image(address)
    raw = data[o:o + 120]
    end = raw.find(b'\0')
    if end >= 2 and all(32 <= c < 127 or c in (9, 10) for c in raw[:end]):
        return repr(raw[:end].decode())
    return image(address)


raw = data[off(va):off(va) + count * 4]
listing = subprocess.run(['llvm-mc', '--disassemble', '--show-encoding', '--triple=arm64e-apple-darwin', '-mattr=+v8.5a,+pauth'],
                         input=' '.join(f'0x{b:02x}' for b in raw), capture_output=True, text=True).stdout
decoded = {}
for line in listing.splitlines():
    m = re.match(r'\s*(.*?)\s*; encoding: \[(0x..),(0x..),(0x..),(0x..)\]', line)
    if m:
        decoded.setdefault(bytes(int(b, 16) for b in m.groups()[1:]), []).append(m.group(1))
seen, pages = {}, {}
for i in range(count):
    wb = raw[i * 4:i * 4 + 4]
    word, = struct.unpack('<I', wb)
    texts = decoded.get(wb, [])
    n = seen.get(wb, 0)
    seen[wb] = n + 1
    line = texts[min(n, len(texts) - 1)] if texts else f'.word {word:#x}'
    pc = va + i * 4
    note = ''
    if word & 0x7c000000 == 0x14000000:
        imm = word & 0x3ffffff
        imm -= (1 << 26) if imm >> 25 else 0
        target = pc + imm * 4
        note = image(target)
        o = off(target)
        if o is not None:   # a stub: adrp x16, page; ldr x16, [x16, #off]; braa / br
            w0, w1 = struct.unpack_from('<II', data, o)
            if w0 & 0x9f00001f == 0x90000010 and w1 & 0xffc003ff == 0xf9400210:
                imm = (w0 >> 5 & 0x7ffff) << 2 | w0 >> 29 & 3
                imm -= (1 << 21) if imm >> 20 else 0
                got = (target & ~0xfff) + (imm << 12) + (w1 >> 10 & 0xfff) * 8
                go = off(got)
                note += f' -> stub via {got:#x}' + (f' -> {image(struct.unpack_from("<Q", data, go)[0] & 0xfffffffff)}' if go is not None else '')
    elif word & 0x9f000000 == 0x90000000:
        imm = (word >> 5 & 0x7ffff) << 2 | word >> 29 & 3
        imm -= (1 << 21) if imm >> 20 else 0
        pages[word & 31] = (pc & ~0xfff) + (imm << 12)
    elif word & 0xffc00000 == 0x91000000 and (word >> 5 & 31) in pages:
        note = describe(pages[word >> 5 & 31] + (word >> 10 & 0xfff))
    elif word & 0xffc00000 == 0xf9400000 and (word >> 5 & 31) in pages:
        note = describe(pages[word >> 5 & 31] + (word >> 10 & 0xfff) * 8)
    m = re.match(r'^\w+\s+[xw](\d+),', line)
    if m and not word & 0x9f000000 == 0x90000000:
        pages.pop(int(m.group(1)), None)
    print(f'{pc:#x}  {line}' + (f'   ; {note}' if note else ''))
