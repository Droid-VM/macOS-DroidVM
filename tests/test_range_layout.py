#!/usr/bin/env python3
"""Targeted negative/positive tests for the bounded Range, ZIP, UDIF and GPT readers."""
import http.server
import importlib.util
import io
import plistlib
import struct
import threading
import unittest
import uuid
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inputs = load('inputs', 'scripts/macos-inputs.py')
layout = load('layout', 'scripts/macos-disk-layout.py')


def build_gpt(total_sectors=256, corrupt=None):
    disk = bytearray(total_sectors * 512)
    stride, count = 128, 128
    entry = bytearray(stride)
    entry[:16] = uuid.uuid4().bytes_le
    entry[16:32] = uuid.uuid4().bytes_le
    struct.pack_into('<QQ', entry, 32, 40, 100)
    entries = bytes(entry) + bytes(stride * (count - 1))

    def header(lba, backup, entries_lba, entries_crc):
        h = bytearray(92)
        h[:8] = b'EFI PART'
        struct.pack_into('<IIII', h, 8, 0x10000, 92, 0, 0)
        struct.pack_into('<QQQQ', h, 24, lba, backup, 34, total_sectors - 34)
        h[56:72] = bytes(16)
        struct.pack_into('<QIII', h, 72, entries_lba, count, stride, entries_crc)
        struct.pack_into('<I', h, 16, zlib.crc32(h))
        return bytes(h)
    crc = zlib.crc32(entries) ^ (1 if corrupt == 'entries' else 0)
    disk[512:512 + 92] = header(1, total_sectors - 1, 2, crc)
    disk[1024:1024 + len(entries)] = entries
    return disk


def build_dmg(raw):
    sectors = len(raw) // 512
    table = bytearray(204 + 40)
    table[:4] = b'mish'
    struct.pack_into('>QQQ', table, 8, 0, sectors, 0)
    struct.pack_into('>I', table, 200, 1)
    struct.pack_into('>IIQQQQ', table, 204, 1, 0, 0, sectors, 0, len(raw))
    xml = plistlib.dumps({'resource-fork': {'blkx': [{'Data': bytes(table)}]}})
    footer = bytearray(512)
    footer[:4] = b'koly'
    struct.pack_into('>II', footer, 4, 4, 512)
    struct.pack_into('>QQ', footer, 24, 0, len(raw))
    struct.pack_into('>QQ', footer, 216, len(raw), len(xml))
    struct.pack_into('>Q', footer, 492, sectors)
    return bytes(raw) + xml + bytes(footer)


def build_zip(dmg):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_STORED) as archive:
        archive.writestr('os.dmg', dmg)
    return buffer.getvalue()


class Server:
    def __init__(self, body, etag='"a"'):
        outer = self
        self.body, self.etag, self.range_status = body, etag, 206

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.headers.get('If-Match') not in (None, outer.etag):
                    self.send_response(412)
                    self.end_headers()
                    return
                start, end = map(int, self.headers['Range'][6:].split('-'))
                data = outer.body[start:end + 1]
                self.send_response(outer.range_status)
                if outer.range_status == 206:
                    self.send_header('Content-Range', f'bytes {start}-{start + len(data) - 1}/{len(outer.body)}')
                if outer.etag:
                    self.send_header('ETag', outer.etag)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        self.httpd = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.httpd.server_port}/x'
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


class RangeTests(unittest.TestCase):
    def setUp(self):
        self.body = bytes(range(256)) * 4096
        self.server = Server(self.body)
        self.addCleanup(self.server.close)

    def test_positive_cross_chunk_read(self):
        remote = inputs.RemoteFile(self.server.url, len(self.body))
        remote.seek(256 * 1024 - 10)
        self.assertEqual(remote.read(20), self.body[256 * 1024 - 10:256 * 1024 + 10])

    def test_etag_change_rejected(self):
        remote = inputs.RemoteFile(self.server.url, len(self.body))
        remote.read(1)
        self.server.etag = '"b"'
        remote.seek(512 * 1024)
        with self.assertRaises(Exception):
            remote.read(1)

    def test_weak_or_missing_etag_rejected(self):
        for etag in ('W/"a"', None):
            self.server.etag = etag
            with self.assertRaisesRegex(ValueError, 'strong ETag'):
                inputs.RemoteFile(self.server.url, len(self.body)).read(1)

    def test_non_partial_response_rejected(self):
        self.server.range_status = 200
        with self.assertRaisesRegex(ValueError, 'exact requested range'):
            inputs.RemoteFile(self.server.url, len(self.body)).read(1)


class LayoutTests(unittest.TestCase):
    def open_disk(self, raw, extra=None):
        dmg = build_dmg(raw)
        data = build_zip(dmg)
        archive = zipfile.ZipFile(io.BytesIO(data))
        entry = archive.getinfo('os.dmg')
        return layout.Disk(io.BytesIO(data), entry, archive.start_dir, archive.infolist())

    def test_positive_gpt(self):
        disk = self.open_disk(build_gpt())
        result = layout.gpt(disk, 1)
        self.assertEqual(result['partitions'][0]['offset'], 40 * 512)

    def test_header_crc_corruption(self):
        raw = build_gpt()
        raw[512 + 40] ^= 1
        with self.assertRaisesRegex(ValueError, 'header CRC'):
            layout.gpt(self.open_disk(raw), 1)

    def test_entries_crc_corruption(self):
        with self.assertRaisesRegex(ValueError, 'entries CRC'):
            layout.gpt(self.open_disk(build_gpt(corrupt='entries')), 1)

    def test_partition_outside_usable_range(self):
        raw = build_gpt()
        entries = bytearray(raw[1024:1024 + 128 * 128])
        struct.pack_into('<QQ', entries, 32, 10, 100)
        raw[1024:1024 + len(entries)] = entries
        raw[512 + 88:512 + 92] = struct.pack('<I', zlib.crc32(entries))
        raw[512 + 16:512 + 20] = bytes(4)
        raw[512 + 16:512 + 20] = struct.pack('<I', zlib.crc32(bytes(raw[512:512 + 92])))
        with self.assertRaisesRegex(ValueError, 'outside usable'):
            layout.gpt(self.open_disk(raw), 1)

    def test_not_udif(self):
        dmg = bytearray(build_dmg(build_gpt()))
        dmg[-512:-508] = b'xxxx'
        data = build_zip(bytes(dmg))
        archive = zipfile.ZipFile(io.BytesIO(data))
        with self.assertRaisesRegex(ValueError, 'not UDIF'):
            layout.Disk(io.BytesIO(data), archive.getinfo('os.dmg'), archive.start_dir)

    def test_malformed_blkx_count(self):
        dmg = bytearray(build_dmg(build_gpt()))
        xml_start = len(build_gpt())
        xml = plistlib.loads(bytes(dmg[xml_start:-512]))
        table = bytearray(xml['resource-fork']['blkx'][0]['Data'])
        struct.pack_into('>I', table, 200, 5)
        xml['resource-fork']['blkx'][0]['Data'] = bytes(table)
        new_xml = plistlib.dumps(xml)
        footer = bytearray(dmg[-512:])
        struct.pack_into('>QQ', footer, 216, xml_start, len(new_xml))
        data = build_zip(bytes(dmg[:xml_start]) + new_xml + bytes(footer))
        archive = zipfile.ZipFile(io.BytesIO(data))
        with self.assertRaisesRegex(ValueError, 'run count'):
            layout.Disk(io.BytesIO(data), archive.getinfo('os.dmg'), archive.start_dir)

    def test_directory_overlap(self):
        data = build_zip(build_dmg(build_gpt()))
        archive = zipfile.ZipFile(io.BytesIO(data))
        with self.assertRaisesRegex(ValueError, 'overlaps ZIP directory'):
            layout.Disk(io.BytesIO(data), archive.getinfo('os.dmg'), 100)

    def test_member_overlap(self):
        data = build_zip(build_dmg(build_gpt()))
        archive = zipfile.ZipFile(io.BytesIO(data))
        entry = archive.getinfo('os.dmg')
        other = zipfile.ZipInfo('b')
        other.header_offset, other.compress_size = entry.header_offset + 100, 10
        with self.assertRaisesRegex(ValueError, 'overlaps another'):
            layout.Disk(io.BytesIO(data), entry, archive.start_dir, [entry, other])

    def test_read_out_of_bounds(self):
        disk = self.open_disk(build_gpt())
        with self.assertRaisesRegex(ValueError, 'out of bounds'):
            disk.read(disk.total - 4, 8)


if __name__ == '__main__':
    unittest.main()
