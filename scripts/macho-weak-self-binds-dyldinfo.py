#!/usr/bin/env python3
"""Bind a Mach-O image's weak flat-namespace imports to the image itself, for an image whose binds are dyld-info opcodes (what
Apple's ld-classic writes, arm64e's threaded binds included): macho-weak-self-binds-dyldinfo.py IMAGE

The board's scripts/macho-weak-self-binds.py (UniXNU 527b8b7) does this for chained fixups. Mesa takes the address of every Vulkan
entrypoint a driver might implement through weak declarations, and the ones Turnip does not implement (5633) are imports bound
through the flat namespace: dyld looked each up in every image of the process before settling on NULL, seconds of CPU in every
process that opened a Metal device. Bound to the image itself (BIND_SPECIAL_DYLIB_SELF) dyld looks in the image's own export
trie, which cannot hold them (they are hidden), and leaves each NULL as before.

Each BIND_OPCODE_SET_DYLIB_SPECIAL_IMM(FLAT_LOOKUP) of the bind table whose symbols (up to the next ordinal) are all weak imports
becomes SET_DYLIB_SPECIAL_IMM(SELF): one byte for one, in place. One that also covers a strong import is left, and said so.
Running it twice changes nothing. The linker's ad-hoc signature is kept valid: the page hashes of its code directories are
recomputed for the pages that changed (there is no codesign on this host), which changes the image's CDHash, so the trust cache
is made after this (stage-gpu-plugin.py).
"""
import hashlib
import struct
import sys

LC_CODE_SIGNATURE, LC_DYLD_INFO, LC_DYLD_INFO_ONLY = 0x1d, 0x22, 0x80000022
SET_DYLIB_SPECIAL_IMM, SET_SYMBOL = 0x30, 0x40
FLAT_LOOKUP_IMM = 0x0e   # -2 in the opcode's four-bit immediate
WEAK_IMPORT = 0x1


def uleb(data, at):
    value = shift = 0
    while True:
        byte = data[at]
        at += 1
        value |= (byte & 0x7f) << shift
        shift += 7
        if byte < 0x80:
            return value, at


def refresh_page_hashes(data, signature):
    """Recompute every code directory's page hashes that no longer match the image's pages; how many were stale."""
    offset, length = signature
    magic, _, blobs = struct.unpack_from('>III', data, offset)
    if magic != 0xfade0cc0:
        sys.exit('no embedded signature superblob')
    stale = 0
    for index in range(blobs):
        _, start = struct.unpack_from('>II', data, offset + 12 + 8 * index)
        cd = offset + start
        if struct.unpack_from('>I', data, cd)[0] != 0xfade0c02:
            continue
        hash_offset, _, _, code_slots, code_limit = struct.unpack_from('>IIIII', data, cd + 16)
        hash_size, hash_type, _, page_log = data[cd + 36], data[cd + 37], data[cd + 38], data[cd + 39]
        digest = {1: hashlib.sha1, 2: hashlib.sha256}[hash_type]
        page = 1 << page_log
        for slot in range(code_slots):
            content = bytes(data[slot * page:min((slot + 1) * page, code_limit)])
            at = cd + hash_offset + slot * hash_size
            value = digest(content).digest()[:hash_size]
            if data[at:at + hash_size] != value:
                data[at:at + hash_size] = value
                stale += 1
    return stale


def main(path):
    data = bytearray(open(path, 'rb').read())
    if struct.unpack_from('<I', data, 0)[0] != 0xFEEDFACF:
        sys.exit(f'{path}: not a thin 64-bit Mach-O image')
    ncmds = struct.unpack_from('<I', data, 16)[0]
    at, info, signature = 32, None, None
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', data, at)
        if cmd in (LC_DYLD_INFO, LC_DYLD_INFO_ONLY):
            info = struct.unpack_from('<10I', data, at + 8)
        elif cmd == LC_CODE_SIGNATURE:
            signature = struct.unpack_from('<II', data, at + 8)
        at += size
    if info is None:
        sys.exit(f'{path}: no LC_DYLD_INFO')
    start, size = info[2], info[3]   # the bind table (weak and lazy binds never use the flat ordinal here)
    end = start + size
    # Each flat-lookup ordinal opcode, with whether every symbol bound under it is a weak import.
    runs, current, i = [], None, start
    while i < end:
        op, imm = data[i] & 0xf0, data[i] & 0x0f
        i += 1
        if op in (0x10, 0x20, SET_DYLIB_SPECIAL_IMM):
            current = None
            if op == 0x20:
                _, i = uleb(data, i)
            elif op == SET_DYLIB_SPECIAL_IMM and imm == FLAT_LOOKUP_IMM:
                current = [i - 1, True, 0]
                runs.append(current)
        elif op == SET_SYMBOL:
            i = data.index(0, i) + 1
            if current:
                current[1] &= bool(imm & WEAK_IMPORT)
                current[2] += 1
        elif op in (0x60, 0x70, 0x80, 0xa0):   # SET_ADDEND_SLEB, SET_SEGMENT_AND_OFFSET_ULEB, ADD_ADDR_ULEB, DO_BIND_ADD_ADDR_ULEB
            _, i = uleb(data, i)
        elif op == 0xc0:                       # DO_BIND_ULEB_TIMES_SKIPPING_ULEB
            _, i = uleb(data, i)
            _, i = uleb(data, i)
        elif op == 0xd0 and imm == 0:          # THREADED SET_BIND_ORDINAL_TABLE_SIZE_ULEB
            _, i = uleb(data, i)
        # DONE, SET_TYPE_IMM, DO_BIND, DO_BIND_ADD_ADDR_IMM_SCALED, THREADED APPLY: no operands
    changed = symbols = mixed = 0
    for offset, weak_only, count in runs:
        if weak_only and count:
            data[offset] = SET_DYLIB_SPECIAL_IMM   # BIND_SPECIAL_DYLIB_SELF, immediate 0
            changed += 1
            symbols += count
        elif count:
            mixed += count
    stale = refresh_page_hashes(data, signature) if signature else 0
    open(path, 'wb').write(data)
    print(f'{path}: {symbols} weak flat imports bound to the image itself ({changed} ordinals); '
          f'{mixed} flat imports left (a strong import shares their ordinal); {stale} page hashes recomputed')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
