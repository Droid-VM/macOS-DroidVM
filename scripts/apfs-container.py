#!/usr/bin/env python3
"""Resolve the APFS container volumes of the IPSW OS image by bounded ranges (read-only).

Walks NXSB checkpoint -> container omap B-tree -> APSB; every object checksum is verified.
Does not verify file-system trees, the sealed-volume hash or Apple signatures.
"""
import argparse
import importlib.util
import json
import struct
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inputs = load('inputs', 'scripts/macos-inputs.py')
layout = load('layout', 'scripts/macos-disk-layout.py')
require = layout.require
ROLES = {0: 'none', 1: 'System', 2: 'User', 4: 'Recovery', 8: 'VM', 16: 'Preboot', 32: 'Installer',
         64: 'Data', 128: 'Baseband', 192: 'Update', 256: 'xART', 320: 'Hardware', 384: 'Backup',
         448: 'Sidecar', 512: 'Reserved', 576: 'Enterprise', 704: 'Prelogin'}
OBJ_TYPE_MASK = 0xffff
NXSB, APSB, OMAP, BTREE_ROOT, BTREE_NODE = 1, 0xd, 0xb, 2, 3


def fletcher64(data):
    lo = hi = 0
    for (word,) in struct.iter_unpack('<I', data):
        lo = (lo + word) % 0xFFFFFFFF
        hi = (hi + lo) % 0xFFFFFFFF
    c0 = 0xFFFFFFFF - ((lo + hi) % 0xFFFFFFFF)
    c1 = 0xFFFFFFFF - ((lo + c0) % 0xFFFFFFFF)
    return struct.pack('<II', c0, c1)


class Container:
    def __init__(self, disk, base, size):
        self.disk, self.base, self.size = disk, base, size
        first = disk.read(base, 4096)
        require(first[32:36] == b'NXSB', 'no container superblock at partition start')
        self.bs = struct.unpack_from('<I', first, 36)[0]
        require(self.bs in (4096, 8192, 16384, 32768, 65536), 'unsupported APFS block size')
        self.cache = {}

    def block(self, number, kind=None):
        require(0 <= number * self.bs and (number + 1) * self.bs <= self.size, 'APFS block outside partition')
        if number not in self.cache:
            data = self.disk.read(self.base + number * self.bs, self.bs)
            require(fletcher64(data[8:]) == data[:8], f'APFS checksum mismatch at block {number}')
            self.cache[number] = data
        data = self.cache[number]
        if kind is not None:
            require(struct.unpack_from('<I', data, 24)[0] & OBJ_TYPE_MASK == kind, f'unexpected object type at {number}')
        return data

    def latest_superblock(self):
        block0 = self.block(0, NXSB)
        count = struct.unpack_from('<Q', block0, 40)[0]
        require(count * self.bs <= self.size, 'container larger than partition')
        desc_blocks, = struct.unpack_from('<I', block0, 104)
        desc_base, = struct.unpack_from('<q', block0, 112)
        require(desc_base > 0 and desc_blocks < 1 << 20 and desc_base + desc_blocks <= count,
                'checkpoint descriptor area unsupported or out of range')
        best = (struct.unpack_from('<Q', block0, 16)[0], 0, block0)
        for index in range(desc_blocks):
            data = self.disk.read(self.base + (desc_base + index) * self.bs, self.bs)
            if data[32:36] == b'NXSB' and fletcher64(data[8:]) == data[:8]:
                xid = struct.unpack_from('<Q', data, 16)[0]
                if xid > best[0]:
                    best = (xid, index + 1, data)
        return best

    def omap_lookup(self, omap_block, oid, max_xid):
        omap = self.block(omap_block, OMAP)
        tree = struct.unpack_from('<Q', omap, 48)[0]
        return self.tree_lookup(tree, oid, max_xid, 0)

    def tree_lookup(self, block, oid, max_xid, depth):
        require(depth < 8, 'omap tree too deep')
        node = self.block(block)
        require(struct.unpack_from('<I', node, 24)[0] & OBJ_TYPE_MASK in (BTREE_ROOT, BTREE_NODE), 'not a B-tree node')
        flags, level, nkeys, toc_off, toc_len = struct.unpack_from('<HHIHH', node, 32)
        require(flags & 4, 'omap node must use fixed key/value sizes')
        root = bool(flags & 1)
        keys = 56 + toc_off + toc_len
        values_end = self.bs - (40 if root else 0)
        best = None
        for index in range(nkeys):
            k, v = struct.unpack_from('<HH', node, 56 + toc_off + 4 * index)
            require(keys + k + 16 <= self.bs and 16 <= v <= values_end, 'omap entry out of node')
            key_oid, key_xid = struct.unpack_from('<QQ', node, keys + k)
            if level:
                if key_oid <= oid and (best is None or key_oid >= best[0]):
                    best = (key_oid, struct.unpack_from('<Q', node, values_end - v)[0])
            elif key_oid == oid and key_xid <= max_xid and (best is None or key_xid > best[0]):
                paddr, = struct.unpack_from('<Q', node, values_end - v + 8)
                best = (key_xid, paddr)
        if level:
            return None if best is None else self.tree_lookup(best[1], oid, max_xid, depth + 1)
        return None if best is None else best[1]

    def volumes(self):
        xid, desc_index, sb = self.latest_superblock()
        count = struct.unpack_from('<Q', sb, 40)[0]
        omap_oid = struct.unpack_from('<Q', sb, 160)[0]
        max_fs = struct.unpack_from('<I', sb, 180)[0]
        require(max_fs <= 100, 'invalid max_file_systems')
        info = dict(block_size=self.bs, block_count=count, xid=xid, descriptor_index=desc_index,
                    container_uuid=str(uuid.UUID(bytes=sb[72:88])).upper(), volumes=[])
        for slot in range(max_fs):
            oid, = struct.unpack_from('<Q', sb, 184 + 8 * slot)
            if not oid:
                continue
            paddr = self.omap_lookup(omap_oid, oid, xid)
            require(paddr is not None, f'volume oid {oid:#x} missing from omap')
            vol = self.block(paddr, APSB)
            require(vol[32:36] == b'APSB', 'bad volume magic')
            role = struct.unpack_from('<H', vol, 964)[0]
            info['volumes'].append(dict(
                slot=slot, oid=oid, block=paddr, xid=struct.unpack_from('<Q', vol, 16)[0], role=ROLES.get(role, role),
                uuid=str(uuid.UUID(bytes=vol[240:256])).upper(),
                group=str(uuid.UUID(bytes=vol[1008:1024])).upper(),
                name=vol[704:960].split(b'\0')[0].decode(errors='replace')))
        return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default='configs/macos-23G93.json')
    parser.add_argument('--layout', default='out/macos-disk-layout.json')
    parser.add_argument('--output', default='out/macos-apfs-container.json')
    args = parser.parse_args()
    profile = json.loads(inputs.local_path(args.profile).read_text())
    gpt = json.loads(inputs.local_path(args.layout).read_text())
    output = inputs.local_path(args.output)
    require(not output.exists(), f'refusing to overwrite {output}')
    parts = [p for p in gpt['gpt']['partitions'] if p['type'].upper() == '7C3457EF-0000-11AA-AA11-00306543ECAC']
    require(len(parts) == 1, 'expected exactly one APFS GPT partition')
    spec = profile['ipsw']
    component = profile['identity']['components']['OS']
    with inputs.RemoteFile(spec['url'], spec['filesize']) as remote, zipfile.ZipFile(remote) as archive:
        entry = archive.getinfo(component['path'])
        disk = layout.Disk(remote, entry, archive.start_dir, archive.infolist())
        require(remote.etag == gpt['etag'], 'remote ETag differs from the recorded layout')
        report = Container(disk, parts[0]['offset'], parts[0]['size']).volumes()
        report.update(partition=parts[0], downloaded_bytes=remote.downloaded,
                      fs_trees_verified=False, sealed_hash_verified=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as handle:
        handle.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
