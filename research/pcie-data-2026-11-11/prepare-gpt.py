#!/usr/bin/env python3
"""GPT wrapper for the existing empty-seed SHNGDATA container; no seed regeneration."""
import struct
import sys
import uuid
import zlib
from pathlib import Path

magic, version, page, logical, extents = struct.unpack('<8sIIQQ', Path(sys.argv[1]).read_bytes())
assert (magic, version, page, extents) == (b'DBRDISK1', 1, 4096, 0)
out = Path(sys.argv[2])
total = (logical + 2 * 1024 * 1024) // 512
entries = bytearray(128 * 128)
entries[:16] = uuid.UUID('69646961-6700-11AA-AA11-00306543ECAC').bytes_le
entries[16:32] = uuid.uuid4().bytes_le
struct.pack_into('<QQQ', entries, 32, 2048, 2048 + logical // 512 - 1, 0)
name = 'DroidVM Container'.encode('utf-16le')
entries[56:56 + len(name)] = name
guid = uuid.uuid4().bytes_le

def header(at, other, table):
    data = bytearray(512)
    struct.pack_into('<8sIIIIQQQQ16sQIII', data, 0, b'EFI PART', 0x10000, 92, 0, 0,
                     at, other, 34, total - 34, guid, table, 128, 128, zlib.crc32(entries))
    struct.pack_into('<I', data, 16, zlib.crc32(data[:92]))
    return data

prefix = bytearray(1024 * 1024)
prefix[446:462] = struct.pack('<B3sB3sII', 0, b'\0\2\0', 0xee, b'\xff' * 3, 1, min(total - 1, 0xffffffff))
prefix[510:512] = b'\x55\xaa'
prefix[512:1024] = header(1, total - 1, 2)
prefix[1024:1024 + len(entries)] = entries
suffix = bytearray(1024 * 1024)
suffix[-512 - len(entries):-512] = entries
suffix[-512:] = header(total - 1, 1, total - 33)
(out / 'data-gpt-prefix.bin').write_bytes(prefix)
(out / 'data-gpt-suffix.bin').write_bytes(suffix)
print('disk_bytes', total * 512, 'container_bytes', logical)
