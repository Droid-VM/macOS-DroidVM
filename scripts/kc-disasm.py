#!/usr/bin/env python3
"""Disassemble code of a kext (or any address) in a fileset kernelcache, naming branch targets from the entries' symbol tables.

    kc-disasm.py KC ADDRESS|SYMBOL [COUNT]

Annotations: b/bl targets; adrp+add/ldr: the C string or the symbol there, or the target of the chained pointer a GOT load reads;
blraa/braa through a vtable: the slot (offset / 8) and the methods whose PAC string discriminator is the call's diversity
(scripts/ptrauth_disc.py: the introducing declaration of the slot).
"""
import bisect
import re
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fileset_kc  # noqa: E402
from ptrauth_disc import discriminator  # noqa: E402

kc = fileset_kc.Kernelcache(Path(sys.argv[1]).read_bytes())
count = int(sys.argv[3]) if len(sys.argv) > 3 else 40
names, by_name = [], {}
for entry in kc.entries:
    for name, kind, sect, desc, value in kc.symbols(kc.macho(entry)):
        if value and sect:
            names.append((value, f'{entry.split(".")[-1]}:{name}'))
            by_name.setdefault(name, value)
names.sort()
keys = [n[0] for n in names]
va = int(sys.argv[2], 16) if sys.argv[2].startswith('0x') else by_name[sys.argv[2]]
pointers = {site: target for site, raw, target, *_ in kc.chained_sites()}
methods = {}


def method_names(diversity):
    if not methods:
        for _, name in names:
            symbol = name.split(':', 1)[1]
            if symbol.startswith('__ZN'):
                methods.setdefault(discriminator(symbol[1:]), set()).add(symbol)
    found = sorted(methods.get(diversity, ()))
    return found[:3] + (['...'] if len(found) > 3 else [])


def label(address):
    i = bisect.bisect_right(keys, address) - 1
    return f'{names[i][1]}+{address - names[i][0]:#x}' if i >= 0 else '?'


def describe(address):
    """A C string at ADDRESS, else what a pointer there targets, else the symbol."""
    try:
        at = kc.file_offset(address)
    except Exception:
        return label(address)
    raw = kc.data[at:at + 96]
    end = raw.find(b'\0')
    if end >= 3 and all(32 <= c < 127 or c in (9, 10) for c in raw[:end]):
        return repr(raw[:end].decode())
    if address in pointers:
        return f'&-> {label(pointers[address])}'
    return label(address)


raw = kc.data[va - kc.base:va - kc.base + count * 4]
listing = subprocess.run(['llvm-mc', '--disassemble', '--show-encoding', '--triple=arm64e-apple-darwin', '-mattr=+v8.5a,+pauth'],
                         input=' '.join(f'0x{b:02x}' for b in raw), capture_output=True, text=True).stdout
decoded = {}
for line in listing.splitlines():
    m = re.match(r'\s*(.*?)\s*; encoding: \[(0x..),(0x..),(0x..),(0x..)\]', line)
    if m:
        decoded.setdefault(bytes(int(b, 16) for b in m.groups()[1:]), []).append(m.group(1))
seen = {}
print(f'{va:#x} {label(va)}')
pages, offset, diversity = {}, None, None
for i in range(count):
    word_bytes = raw[i * 4:i * 4 + 4]
    word, = struct.unpack('<I', word_bytes)
    texts = decoded.get(word_bytes, [])
    n = seen.get(word_bytes, 0)
    seen[word_bytes] = n + 1
    line = texts[min(n, len(texts) - 1)] if texts else f'.word {word:#x}'
    pc = va + i * 4
    note = ''
    if word & 0x7c000000 == 0x14000000:
        imm = word & 0x3ffffff
        imm -= (1 << 26) if imm >> 25 else 0
        note = label(pc + imm * 4)
    elif word & 0x9f000000 == 0x90000000:   # adrp
        imm = (word >> 5 & 0x7ffff) << 2 | word >> 29 & 3
        imm -= (1 << 21) if imm >> 20 else 0
        pages[word & 31] = (pc & ~0xfff) + (imm << 12)
    elif word & 0xffc00000 == 0x91000000 and (word >> 5 & 31) in pages:   # add xd, xn, #imm (adrp pair)
        note = describe(pages[word >> 5 & 31] + (word >> 10 & 0xfff))
    elif word & 0xffc00000 == 0xf9400000:   # ldr xt, [xn, #imm]
        base = word >> 5 & 31
        if base in pages:
            note = describe(pages[base] + (word >> 10 & 0xfff) * 8)
        elif base == 16 and word >> 10 & 0xfff:
            offset = (word >> 10 & 0xfff) * 8   # ldr x8, [x16] after mov x17, #off / add x16, x16, x17 keeps that offset
    elif m := re.match(r'mov\s+x17, #(\d+)', line):
        offset = int(m.group(1))
    elif m := re.match(r'movk\s+x1[67], #(\d+), lsl #48', line):
        diversity = int(m.group(1))
    elif re.match(r'b(l)?ra[ab]\s', line) and diversity is not None:
        note = (f'slot {offset // 8} ' if offset is not None else '') + ' '.join(method_names(diversity))
        offset = diversity = None
    print(f'{pc:#x}  {line}' + (f'   ; {note}' if note else ''))
