#!/usr/bin/env python3
"""Add volumes to an existing APFS container, offline, the way diskutil apfs addVolume leaves it (docs/k27-apfs-addvolume-plan.md).

  apfs-add-volumes.py info CONTAINER
  apfs-add-volumes.py add CONTAINER [--grow-to BYTES] [--group-with INDEX] VOLUME...

CONTAINER is a raw APFS container (a file, or a block device such as a dm snapshot of one). VOLUME is NAME:ROLE[:OPTION,...] with ROLE
one of the diskutil letters below and OPTIONs `sensitive` (case-sensitive; the default is case-insensitive, as macOS's volumes) and
`uuid=UUID`. --group-with INDEX puts the Data volume (role D) in a volume group with the volume at INDEX of the container (macOS's
System volume): both get the group's UUID (the Data volume's own UUID, as diskutil gives it) and APFS_FEATURE_VOLGRP_SYSTEM_INO_SPACE.

Nothing is written by hand: each volume is made empty by apfsprogs' mkapfs in a scratch container and its objects (the volume
superblock, its object map and the object map's tree, the file-system tree, the extent-reference and snapshot-metadata trees) are
moved into blocks the space manager gives out here, with their addresses, object ids and transaction ids rewritten. The container's
object map gets the new superblocks, its superblock their slots. Changes are made in place in the latest checkpoint (the container
is not mounted): blocks are taken from the chunk bitmaps (never from chunks without one, which grow-data-store.py leaves all free),
and a change the layout does not allow (a container object map of more than one node) stops before anything is written.
"""
import argparse
import importlib.util
import struct
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('grow_data_store', ROOT / 'scripts/grow-data-store.py')
grow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grow)
PAGE, Image, Checkpoint, bit = grow.PAGE, grow.Image, grow.Checkpoint, grow.bit
MKAPFS = ROOT / 'sources/apfsprogs/mkapfs/mkapfs'

OBJECT_TYPE_BTREE, OBJECT_TYPE_BTREE_NODE, OBJECT_TYPE_OMAP, OBJECT_TYPE_FS = 0x2, 0x3, 0xb, 0xd
OBJ_PHYSICAL, OBJ_VIRTUAL = 0x40000000, 0x00000000
BTNODE_ROOT, BTNODE_LEAF, BTNODE_FIXED_KV_SIZE = 1, 2, 4
APFS_FEATURE_VOLGRP_SYSTEM_INO_SPACE = 0x10
# apfs_superblock_t offsets (Apple File System Reference)
APSB_FS_INDEX, APSB_FEATURES, APSB_INCOMPAT, APSB_ALLOC = 36, 40, 56, 88
APSB_OMAP, APSB_ROOT_TREE, APSB_EXTENTREF, APSB_SNAP_META = 128, 136, 144, 152
APSB_UUID, APSB_NAME, APSB_ROLE, APSB_GROUP = 240, 704, 964, 1008
APSB_UNSUPPORTED = {976: 'er_state_oid', 1000: 'snap_meta_ext_oid', 1024: 'integrity_meta_oid', 1032: 'fext_tree_oid', 1048: 'pfkur_tree_oid'}
NX_NEXT_OID, NX_SPACEMAN, NX_OMAP, NX_MAX_FS, NX_FS_OID = 88, 152, 160, 180, 184
# diskutil apfs addVolume -role letters -> apfs_superblock_t.apfs_role (the roles past Data are N << 6: Update 3, xART 4, Hardware 5,
# Backup 6, Enterprise 9)
ROLES = {'S': 0x1, 'U': 0x2, 'R': 0x4, 'V': 0x8, 'B': 0x10, 'I': 0x20, 'D': 0x40, 'E': 0xc0, 'X': 0x100, 'H': 0x140, 'T': 0x180,
         'Y': 0x240}
ROLE_NAMES = {v: k for k, v in ROLES.items()}


def u64(data, offset):
    return struct.unpack_from('<Q', data, offset)[0]


class Container:
    """The latest checkpoint of IMAGE's container, its space manager, chunk-info blocks and object map (a single root leaf)."""

    def __init__(self, image):
        self.image = image
        self.cp = Checkpoint(image)
        self.sb = self.cp.sb
        spaceman_block, size = self.cp.maps[u64(self.sb, NX_SPACEMAN)]
        if size != PAGE:
            raise SystemExit(f'space manager of {size} bytes: unsupported')
        self.spaceman_block = spaceman_block
        self.sm = image.block(spaceman_block, 0x5)
        cib_count, cab_count = struct.unpack_from('<II', self.sm, 64)
        if cab_count:
            raise SystemExit('chunk-address blocks: unsupported')
        addr_offset, = struct.unpack_from('<I', self.sm, 80)
        self.cibs = [[block, image.block(block, 0x7)] for block in struct.unpack_from(f'<{cib_count}Q', self.sm, addr_offset)]
        self.omap_block = u64(self.sb, NX_OMAP)
        self.omap = image.block(self.omap_block, OBJECT_TYPE_OMAP)
        if struct.unpack_from('<I', self.omap, 36)[0] or u64(self.omap, 56):
            raise SystemExit('container object map with snapshots: unsupported')
        self.leaf_block = u64(self.omap, 48)
        self.leaf = image.block(self.leaf_block)
        flags, level = struct.unpack_from('<HH', self.leaf, 32)
        if flags & 7 != 7 or level:
            raise SystemExit(f'container object map tree node flags {flags:#x} level {level}: only a single root leaf is supported')

    @property
    def xid(self):
        return self.cp.xid

    def omap_entries(self):
        """[(oid, xid, flags, size, paddr)] of the container object map, in key order."""
        return leaf_entries(self.leaf)

    def volumes(self):
        """[(index in nx_fs_oid, oid, block, superblock)] of the volumes, at their latest object-map version."""
        latest = {}
        for oid, xid, flags, size, paddr in self.omap_entries():
            if xid <= self.xid and (oid not in latest or xid > latest[oid][0]):
                latest[oid] = (xid, paddr)
        result = []
        for index, oid in enumerate(struct.unpack_from(f'<{struct.unpack_from("<I", self.sb, NX_MAX_FS)[0]}Q', self.sb, NX_FS_OID)):
            if oid:
                block = latest[oid][1]
                result.append((index, oid, block, self.image.block(block, OBJECT_TYPE_FS)))
        return result

    def allocate(self, count):
        """COUNT free blocks from the chunk bitmaps (marked used, the chunks' and the device's free counts lowered)."""
        # found first, then marked: a shortage stops with nothing changed
        found = []   # (chunk-info block, entry offset, free, bitmap block, bitmap, [bit])
        total = 0
        for _, cib in self.cibs:
            for i in range(struct.unpack_from('<I', cib, 36)[0]):
                at = 40 + 32 * i
                xid, addr, blocks, free, bitmap = struct.unpack_from('<QQIIQ', cib, at)
                if total == count or not free or not bitmap:
                    continue
                data = bytearray(self.image.map[bitmap * PAGE:(bitmap + 1) * PAGE])
                bits = [b for b in range(blocks) if not bit(data, b)][:count - total]
                if bits:
                    found.append((cib, at, addr, free, bitmap, data, bits))
                    total += len(bits)
        if total != count:
            raise SystemExit(f'only {total} free blocks in chunks with a bitmap, {count} wanted')
        taken = []
        for cib, at, addr, free, bitmap, data, bits in found:
            for b in bits:
                bit(data, b, 1)
                taken.append(addr + b)
            self.image.map[bitmap * PAGE:(bitmap + 1) * PAGE] = bytes(data)
            self.image.changed.add(bitmap)
            struct.pack_into('<I', cib, at + 20, free - len(bits))
        struct.pack_into('<Q', self.sm, 72, u64(self.sm, 72) - count)
        return taken

    def free_slots(self):
        slots = struct.unpack_from('<I', self.sb, NX_MAX_FS)[0]
        return sum(1 for index in range(slots) if not u64(self.sb, NX_FS_OID + 8 * index))

    def next_oid(self):
        oid = u64(self.sb, NX_NEXT_OID)
        struct.pack_into('<Q', self.sb, NX_NEXT_OID, oid + 1)
        return oid

    def add_volume_slot(self, oid):
        slots = struct.unpack_from('<I', self.sb, NX_MAX_FS)[0]
        for index in range(slots):
            if not u64(self.sb, NX_FS_OID + 8 * index):
                struct.pack_into('<Q', self.sb, NX_FS_OID + 8 * index, oid)
                return index
        raise SystemExit(f'the container holds at most {slots} volumes')

    def map_object(self, oid, paddr):
        entries = self.omap_entries() + [(oid, self.xid, 0, PAGE, paddr)]
        write_leaf(self.leaf, sorted(entries))

    def commit(self):
        """Write every changed object of the checkpoint (the bitmaps are already in place)."""
        image = self.image
        for block, cib in self.cibs:
            image.put(block, cib)
        image.put(self.spaceman_block, self.sm)
        image.put(self.leaf_block, self.leaf)
        self.cp.put_superblock(image)


def leaf_entries(node):
    """[(oid, xid, flags, size, paddr)] of an object-map root leaf (fixed-size 16-byte keys and values)."""
    nkeys, = struct.unpack_from('<I', node, 36)
    toc_off, toc_len = struct.unpack_from('<HH', node, 40)
    keys = 56 + toc_off + toc_len
    values_end = PAGE - 40   # a root node ends with its btree_info
    result = []
    for index in range(nkeys):
        k, v = struct.unpack_from('<HH', node, 56 + toc_off + 4 * index)
        oid, xid = struct.unpack_from('<QQ', node, keys + k)
        flags, size, paddr = struct.unpack_from('<IIQ', node, values_end - v)
        result.append((oid, xid, flags, size, paddr))
    return result


def write_leaf(node, entries):
    """Lay ENTRIES out anew in the object-map root leaf NODE: keys from the start of the key area, values from the end of the value
    area, both in key order, the free space between them (mkapfs's layout); the table of contents keeps its reserved length."""
    toc_off, toc_len = struct.unpack_from('<HH', node, 40)
    if 4 * len(entries) > toc_len:
        raise SystemExit(f'{len(entries)} object-map entries do not fit the node\'s table of contents ({toc_len} bytes)')
    keys = 56 + toc_off + toc_len
    values_end = PAGE - 40
    space = values_end - keys
    if 32 * len(entries) > space:
        raise SystemExit(f'{len(entries)} object-map entries do not fit one node')
    node[56:values_end] = bytes(values_end - 56)
    for index, (oid, xid, flags, size, paddr) in enumerate(entries):
        struct.pack_into('<HH', node, 56 + toc_off + 4 * index, 16 * index, 16 * (index + 1))
        struct.pack_into('<QQ', node, keys + 16 * index, oid, xid)
        struct.pack_into('<IIQ', node, values_end - 16 * (index + 1), flags, size, paddr)
    struct.pack_into('<I', node, 36, len(entries))
    struct.pack_into('<HH', node, 44, 16 * len(entries), space - 32 * len(entries))   # btn_free_space
    struct.pack_into('<HHHH', node, 48, 0xffff, 0, 0xffff, 0)                        # no key or value free lists (BTOFF_INVALID)
    struct.pack_into('<Q', node, PAGE - 40 + 24, len(entries))                        # btree_info: bt_key_count


def empty_volume(name, sensitive, volume_uuid):
    """The objects of an empty volume made by mkapfs: [(kind, block data)] with kind 'apsb', 'omap', 'omap-tree', 'fs-tree',
    'extentref', 'snap-meta', and the fs tree's virtual oid."""
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / 'volume.img'
        with open(path, 'wb') as handle:
            handle.truncate(64 << 20)
        # mkapfs gives the root directory its own euid and egid: run as root of a user namespace, so it is root:wheel as on a Mac
        subprocess.run(['unshare', '-r', str(MKAPFS), *(['-s'] if sensitive else []), '-L', name, '-u', volume_uuid, str(path)], check=True,
                       stdout=subprocess.DEVNULL)
        source = Container(Image(path))
        (_, _, apsb_block, apsb), = source.volumes()
        for offset, field in APSB_UNSUPPORTED.items():
            if u64(apsb, offset):
                raise SystemExit(f'mkapfs made a volume with {field}: unsupported')
        image = source.image
        omap = image.block(u64(apsb, APSB_OMAP), OBJECT_TYPE_OMAP)
        if u64(omap, 56):
            raise SystemExit('mkapfs made a volume object map with a snapshot tree: unsupported')
        omap_tree = image.block(u64(omap, 48))
        objects = {'apsb': apsb, 'omap': omap, 'omap-tree': omap_tree,
                   'extentref': image.block(u64(apsb, APSB_EXTENTREF)), 'snap-meta': image.block(u64(apsb, APSB_SNAP_META))}
        (fs_oid, _, _, _, fs_block), = leaf_entries(omap_tree)
        if fs_oid != u64(apsb, APSB_ROOT_TREE):
            raise SystemExit('mkapfs volume: the object map does not hold the root tree')
        objects['fs-tree'] = image.block(fs_block)
        for kind in ('omap-tree', 'fs-tree', 'extentref', 'snap-meta'):
            flags, level = struct.unpack_from('<HH', objects[kind], 32)
            if not flags & BTNODE_ROOT or not flags & BTNODE_LEAF or level:
                raise SystemExit(f'mkapfs volume: {kind} is not a single root leaf')
        image.handle.close()
        return objects


def add_volume(target, name, role, sensitive, volume_uuid, group=None):
    objects = empty_volume(name, sensitive, volume_uuid)
    blocks = dict(zip(objects, target.allocate(len(objects))))
    xid = target.xid
    apsb_oid, fs_oid = target.next_oid(), target.next_oid()
    for kind, data in objects.items():
        # physical objects are named by their address, virtual ones by their new oid; every object is of this transaction
        oid = {'apsb': apsb_oid, 'fs-tree': fs_oid}.get(kind, blocks[kind])
        struct.pack_into('<QQ', data, 8, oid, xid)
    apsb = objects['apsb']
    struct.pack_into('<Q', apsb, APSB_OMAP, blocks['omap'])
    struct.pack_into('<Q', apsb, APSB_ROOT_TREE, fs_oid)
    struct.pack_into('<Q', apsb, APSB_EXTENTREF, blocks['extentref'])
    struct.pack_into('<Q', apsb, APSB_SNAP_META, blocks['snap-meta'])
    struct.pack_into('<H', apsb, APSB_ROLE, role)
    if group:
        struct.pack_into('<Q', apsb, APSB_FEATURES, u64(apsb, APSB_FEATURES) | APFS_FEATURE_VOLGRP_SYSTEM_INO_SPACE)
        apsb[APSB_GROUP:APSB_GROUP + 16] = group.bytes
    struct.pack_into('<Q', objects['omap'], 48, blocks['omap-tree'])
    write_leaf(objects['omap-tree'], [(fs_oid, xid, 0, PAGE, blocks['fs-tree'])])
    index = target.add_volume_slot(apsb_oid)
    struct.pack_into('<I', apsb, APSB_FS_INDEX, index)
    for kind, data in objects.items():
        target.image.put(blocks[kind], data)
    target.map_object(apsb_oid, blocks['apsb'])
    print(f'volume {index} {name!r} role {ROLE_NAMES.get(role, hex(role))} uuid {volume_uuid} oid {apsb_oid:#x}: blocks '
          + ', '.join(f'{kind} {block}' for kind, block in blocks.items()))
    return index


def role_volumes(image):
    """role -> (index, UUID text) of each volume of the container in IMAGE (the index is the Linux driver's vol=)."""
    result = {}
    for index, _, _, apsb in Container(image).volumes():
        role, = struct.unpack_from('<H', apsb, APSB_ROLE)
        result.setdefault(role, (index, str(uuid.UUID(bytes=bytes(apsb[APSB_UUID:APSB_UUID + 16]))).upper()))
    return result


def info(args):
    container = Container(Image(args.container))
    sb, sm = container.sb, container.sm
    print(f'container xid {container.xid} blocks {u64(sb, 40)} free {u64(sm, 72)} next_oid {u64(sb, NX_NEXT_OID):#x} '
          f'object map entries {len(container.omap_entries())}')
    for index, oid, block, apsb in container.volumes():
        name = bytes(apsb[APSB_NAME:APSB_NAME + 256]).split(b'\0')[0].decode()
        role, = struct.unpack_from('<H', apsb, APSB_ROLE)
        print(f'  {index}: {name!r} role {ROLE_NAMES.get(role, hex(role))} oid {oid:#x} block {block} '
              f'uuid {uuid.UUID(bytes=bytes(apsb[APSB_UUID:APSB_UUID + 16]))} group {uuid.UUID(bytes=bytes(apsb[APSB_GROUP:APSB_GROUP + 16]))} '
              f'features {u64(apsb, APSB_FEATURES):#x} incompat {u64(apsb, APSB_INCOMPAT):#x} alloc {u64(apsb, APSB_ALLOC)}')


def add(args):
    specs = []
    for text in args.volume:
        name, role, *options = text.split(':')
        options = ','.join(options).split(',') if options else []
        if role not in ROLES:
            raise SystemExit(f'{text}: role {role} is none of {"".join(ROLES)}')
        volume_uuid = next((o[5:] for o in options if o.startswith('uuid=')), None) or str(uuid.uuid4()).upper()
        specs.append((name, ROLES[role], 'sensitive' in options, volume_uuid))
    add_volumes(Image(args.container), specs, args.grow_to, args.group_with)


def add_volumes(image, specs, grow_to=None, group_with=None):
    """SPECS: (name, role, case-sensitive, UUID text) of each volume to add to the container in IMAGE."""
    # everything that can refuse is checked before the first write: the volume slots (as many as the grown container allows), the
    # blocks (allocate), the volume group's member
    container = Container(image)
    slots = container.free_slots() + (grow.max_volumes(grow_to) - struct.unpack_from('<I', container.sb, NX_MAX_FS)[0]
                                       if grow_to else 0)
    if slots < len(specs):
        raise SystemExit(f'room for {slots} more volumes, {len(specs)} wanted')
    if group_with is not None and not [v for v in container.volumes() if v[0] == group_with]:
        raise SystemExit(f'no volume {group_with}')
    if grow_to:
        grow.grow_container(image, grow_to // PAGE)
        container = Container(image)
    group = None
    if group_with is not None:
        data = [s for s in specs if s[1] == ROLES['D']]
        if len(data) != 1:
            raise SystemExit('--group-with needs exactly one Data volume (role D)')
        group = uuid.UUID(data[0][3])
        member = [v for v in container.volumes() if v[0] == group_with]
        if not member:
            raise SystemExit(f'no volume {group_with}')
        _, _, block, apsb = member[0]
        struct.pack_into('<Q', apsb, APSB_FEATURES, u64(apsb, APSB_FEATURES) | APFS_FEATURE_VOLGRP_SYSTEM_INO_SPACE)
        apsb[APSB_GROUP:APSB_GROUP + 16] = group.bytes
        image.put(block, apsb)   # in place: the same object at the same transaction
    for name, role, sensitive, volume_uuid in specs:
        add_volume(container, name, role, sensitive, volume_uuid, group if role == ROLES['D'] else None)
    container.commit()
    image.map.flush()
    print(f'{len(specs)} volumes added, {len(image.changed)} blocks written')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('info')
    p.add_argument('container')
    p.set_defaults(func=info)
    p = sub.add_parser('add')
    p.add_argument('container')
    p.add_argument('--grow-to', type=int)
    p.add_argument('--group-with', type=int)
    p.add_argument('volume', nargs='+')
    p.set_defaults(func=add)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
