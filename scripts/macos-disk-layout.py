#!/usr/bin/env python3
"""Inspect a stored IPSW OS member by bounded ranges; no full image authentication."""
import argparse
import base64
import ctypes
import hashlib
import importlib.util
import json
import plistlib
import shutil
import struct
import uuid
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('inputs', ROOT / 'scripts/macos-inputs.py')
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)
LIMIT = 32 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Disk:
    def __init__(self, remote, entry, directory_offset, others=()):
        self.remote = remote
        self.size = entry.file_size
        remote.seek(entry.header_offset)
        header = remote.read(30)
        require(header[:4] == b'PK\x03\x04', 'invalid ZIP local header')
        flags, method = struct.unpack_from('<HH', header, 6)
        require(flags == entry.flag_bits and method == entry.compress_type == 0 and not flags & 1,
                'requires unencrypted stored member with matching local header')
        require(entry.compress_size == entry.file_size, 'stored size mismatch')
        name_len, extra_len = struct.unpack_from('<HH', header, 26)
        name = remote.read(name_len).decode('utf-8' if flags & 0x800 else 'cp437')
        require(name == entry.filename, 'local ZIP name mismatch')
        self.offset = entry.header_offset + 30 + name_len + extra_len
        require(self.offset + self.size <= directory_offset, 'member overlaps ZIP directory')
        for other in others:
            if other.header_offset != entry.header_offset:
                require(other.header_offset >= self.offset + self.size or
                        other.header_offset + 30 + other.compress_size <= entry.header_offset,
                        'member overlaps another ZIP member')
        footer = self.member(self.size - 512, 512)
        require(footer[:4] == b'koly', 'not UDIF')
        require(struct.unpack_from('>II', footer, 4) == (4, 512), 'unsupported UDIF version/header')
        data_offset, data_length = struct.unpack_from('>QQ', footer, 24)
        xml_offset, xml_length = struct.unpack_from('>QQ', footer, 216)
        require(data_offset + data_length <= self.size - 512, 'data fork out of bounds')
        require(xml_length <= LIMIT and xml_offset + xml_length <= self.size - 512, 'XML out of bounds')
        self.total = struct.unpack_from('>Q', footer, 492)[0] * 512
        require(0 < self.total <= 1024**4, 'unexpected logical disk size')
        xml = self.member(xml_offset, xml_length)
        self.xml_hash = hashlib.sha256(xml).hexdigest()
        self.runs = []
        for item in plistlib.loads(xml)['resource-fork']['blkx']:
            table = item['Data']
            if isinstance(table, str):
                table = base64.b64decode(table, validate=True)
            require(len(table) >= 204 and table[:4] == b'mish', 'invalid blkx')
            first, sectors, table_data = struct.unpack_from('>QQQ', table, 8)
            count = struct.unpack_from('>I', table, 200)[0]
            require(204 + 40 * count == len(table), 'invalid blkx run count')
            require((first + sectors) * 512 <= self.total, 'blkx exceeds disk')
            for index in range(count):
                kind, _, sector, length, offset, size = struct.unpack_from('>IIQQQQ', table, 204 + 40 * index)
                if kind in (0x7ffffffe, 0xffffffff):
                    continue
                require(sector + length <= sectors, 'run exceeds blkx sectors')
                require(table_data + offset + size <= data_length, 'run exceeds data fork')
                if length:
                    self.runs.append(((first + sector) * 512, length * 512, kind,
                                      data_offset + table_data + offset, size))
        self.runs.sort()
        end = 0
        for start, size, *_ in self.runs:
            require(start >= end, 'overlapping logical UDIF runs')
            end = start + size
        self.library = None

    def member(self, offset, size):
        require(0 <= size <= LIMIT and 0 <= offset <= self.size - size, 'member read out of bounds')
        self.remote.seek(self.offset + offset)
        data = self.remote.read(size)
        require(len(data) == size, 'short member read')
        return data

    def read(self, offset, size):
        require(0 <= size <= LIMIT and 0 <= offset <= self.total - size, 'disk read out of bounds')
        result = bytearray()
        end = offset + size
        for start, length, kind, packed_at, packed_size in self.runs:
            if start + length <= offset or start >= end:
                continue
            require(start <= offset, 'unmapped logical disk bytes')
            take = min(start + length, end) - offset
            if kind in (0, 2):
                data = bytes(take)
            elif kind == 1:
                require(packed_size == length, 'raw run size mismatch')
                data = self.member(packed_at + offset - start, take)
            else:
                require(length <= LIMIT, 'compressed run too large for bounded inspection')
                packed = self.member(packed_at, packed_size)
                if kind == 0x80000007:
                    if self.library is None:
                        self.library = ctypes.CDLL(str(ROOT / 'out/linux/liblzfse.so'))
                        fn = self.library.lzfse_decode_buffer
                        fn.restype = ctypes.c_size_t
                        fn.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
                    output = ctypes.create_string_buffer(length)
                    done = self.library.lzfse_decode_buffer(output, length, packed, len(packed), None)
                    require(done == length, 'LZFSE size mismatch')
                    unpacked = output.raw
                elif kind == 0x80000005:
                    decoder = zlib.decompressobj()
                    unpacked = decoder.decompress(packed, length + 1)
                    require(decoder.eof and not decoder.unused_data, 'invalid zlib stream')
                else:
                    raise ValueError(f'unsupported metadata chunk {kind:#x}')
                require(len(unpacked) == length, 'decoded run size mismatch')
                data = unpacked[offset - start:offset - start + take]
            result.extend(data)
            offset += take
        require(offset == end, 'unmapped logical disk bytes')
        return bytes(result)


def gpt(disk, lba):
    header = disk.read(lba * 512, 512)
    require(header[:8] == b'EFI PART', 'missing GPT signature')
    revision, size, checksum, reserved = struct.unpack_from('<IIII', header, 8)
    require(revision == 0x10000 and 92 <= size <= 512 and reserved == 0, 'invalid GPT header')
    checked = bytearray(header[:size])
    checked[16:20] = bytes(4)
    require(zlib.crc32(checked) == checksum, 'GPT header CRC mismatch')
    current, backup, first, last = struct.unpack_from('<QQQQ', header, 24)
    require(current == lba and backup < disk.total // 512 and first <= last < disk.total // 512,
            'GPT geometry out of bounds')
    entries_lba, count, stride, crc = struct.unpack_from('<QIII', header, 72)
    require(128 <= stride <= 4096 and stride % 128 == 0 and 0 < count * stride <= LIMIT, 'invalid GPT entries size')
    require(2 <= entries_lba and (entries_lba + (count * stride + 511) // 512 <= first or entries_lba > last)
            and entries_lba + (count * stride + 511) // 512 <= disk.total // 512, 'GPT entries overlap usable LBAs')
    entries = disk.read(entries_lba * 512, count * stride)
    require(zlib.crc32(entries) == crc, 'GPT entries CRC mismatch')
    parts = []
    for index in range(count):
        entry = entries[index * stride:(index + 1) * stride]
        if entry[:16] == bytes(16):
            continue
        low, high = struct.unpack_from('<QQ', entry, 32)
        require(first <= low <= high <= last, 'partition outside usable LBAs')
        parts.append(dict(index=index + 1, type=str(uuid.UUID(bytes_le=entry[:16])),
                          partition_uuid=str(uuid.UUID(bytes_le=entry[16:32])),
                          offset=low * 512, size=(high - low + 1) * 512,
                          name=entry[56:128].decode('utf-16le').rstrip('\0')))
    ordered = sorted(parts, key=lambda p: p['offset'])
    for left, right in zip(ordered, ordered[1:]):
        require(left['offset'] + left['size'] <= right['offset'], 'overlapping partitions')
    return dict(current=current, backup=backup, first=first, last=last,
                disk_uuid=str(uuid.UUID(bytes_le=header[56:72])), entries_sha256=hashlib.sha256(entries).hexdigest(),
                partitions=parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default='configs/macos-23G93.json')
    parser.add_argument('--output', default='out/macos-disk-layout.json')
    args = parser.parse_args()
    profile = json.loads(inputs.local_path(args.profile).read_text())
    output = inputs.local_path(args.output)
    require(not output.exists(), f'refusing to overwrite {output}')
    archive_spec = profile['ipsw']
    component = profile['identity']['components']['OS']
    with inputs.RemoteFile(archive_spec['url'], archive_spec['filesize']) as remote, zipfile.ZipFile(remote) as archive:
        entry = archive.getinfo(component['path'])
        require((entry.file_size, entry.compress_size, entry.compress_type) ==
                (component['size'], component['compressed_size'], component['zip_method']), 'component metadata changed')
        disk = Disk(remote, entry, archive.start_dir, archive.infolist())
        primary = gpt(disk, 1)
        require(primary['backup'] == disk.total // 512 - 1, 'unexpected backup GPT location')
        backup = gpt(disk, primary['backup'])
        require(backup['backup'] == 1 and all(primary[k] == backup[k] for k in
                ('first', 'last', 'disk_uuid', 'entries_sha256', 'partitions')), 'GPT copies disagree')
        free = shutil.disk_usage(ROOT).free
        system_size = profile['identity']['components']['Cryptex1,SystemOS']['size']
        report = dict(member=entry.filename, member_offset=disk.offset, etag=remote.etag,
                      dmg_bytes=disk.size, raw_bytes=disk.total, udif_runs=len(disk.runs),
                      udif_xml_sha256=disk.xml_hash, gpt=primary, downloaded_bytes=remote.downloaded,
                      whole_member_crc_verified=False, whole_ipsw_sha256_verified=False,
                      apple_signature_verified=False, apfs_volumes_verified=False,
                      budget=dict(free_bytes=free, os_dmg_plus_raw_plus_system_dmg=disk.size + disk.total + system_size,
                                  streamed_os_raw_plus_system_dmg=disk.total + system_size,
                                  excludes=['SystemOS expansion/rebuild', 'Data seed/store', 'owner metadata', 'working reserve']))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as handle:
        handle.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
