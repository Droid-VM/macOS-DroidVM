#!/usr/bin/env python3
"""Grow the Data volume's disk and its APFS container in place, keeping what the guest wrote.

  grow-data-store.py fold  OLD_SEED STORE RAW         the seed with the store's overlay folded in, as a raw image the new size
                                                      (RAW's size: truncate it first), then the APFS container in it grown to fill it
  grow-data-store.py store NEW_SEED STORE RAW OUTPUT  OUTPUT: a store for NEW_SEED holding every page of RAW that differs from it

NEW_SEED is OLD_SEED with only its logical size raised (`seed`), so the pages the seed gives are the same and the overlay keeps
what it held; only its header (page count, seed identity) and the place of each page (behind a larger bitmap) change
(sources/UniXNU/drivers/NativeRamBlock/PersistOverlay.h). Check RAW with apfsck between the two steps.

  grow-data-store.py seed  OLD_SEED NEW_SEED BYTES    NEW_SEED: OLD_SEED with logical size BYTES

The container grows the way Apple's resize leaves a whole-disk container: the superblock's block count and volume limit, the
space manager's device counts and main free-queue node limit, and new chunks (no bitmap: all free) appended to the chunk-info
block. Only a growth that still fits the existing chunk-info blocks is handled.
"""
import mmap
import os
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sources/UniXNU/drivers/DarwinBoot/Test'))
import packed_ramdisk  # noqa: E402

from data_store import Store  # noqa: E402

PAGE = 4096
NXSB, SPACEMAN, CIB, CHECKPOINT_MAP = 0x1, 0x5, 0x7, 0xc


def fletcher64(data):
    lo = hi = 0
    for (word,) in struct.iter_unpack('<I', data):
        lo = (lo + word) % 0xFFFFFFFF
        hi = (hi + lo) % 0xFFFFFFFF
    c0 = 0xFFFFFFFF - ((lo + hi) % 0xFFFFFFFF)
    c1 = 0xFFFFFFFF - ((lo + c0) % 0xFFFFFFFF)
    return struct.pack('<II', c0, c1)


def main_fq_node_limit(blocks):
    """apfsprogs lib/parameters.c"""
    if blocks < 0x40000:
        limit = 1 + (blocks - 1) // 4544
    elif blocks < 0x100000:
        limit = 116 + (blocks - 261281) // 2272
    else:
        limit = 512
    return 3 if limit == 2 else limit


def max_volumes(size):
    """apfsprogs mkapfs/super.c get_max_volumes: one volume per 512 MiB, rounded up, at most 100."""
    volumes = (size + 512 * 1024 * 1024 - 1) // (512 * 1024 * 1024)
    return min(max(volumes, 1), 100)


class Image:
    def __init__(self, path):
        self.handle = open(path, 'r+b')
        self.map = mmap.mmap(self.handle.fileno(), 0)
        self.changed = set()

    def block(self, number, kind=None):
        data = bytearray(self.map[number * PAGE:(number + 1) * PAGE])
        if fletcher64(data[8:]) != data[:8]:
            raise SystemExit(f'checksum mismatch at block {number}')
        if kind is not None and struct.unpack_from('<I', data, 24)[0] & 0xffff != kind:
            raise SystemExit(f'block {number}: not object type {kind:#x}')
        return data

    def put(self, number, data):
        data[:8] = fletcher64(bytes(data[8:]))
        self.map[number * PAGE:(number + 1) * PAGE] = bytes(data)
        self.changed.add(number)


def grow_container(image, blocks):
    block0 = image.block(0, NXSB)
    desc_blocks, = struct.unpack_from('<I', block0, 104)
    desc_base, = struct.unpack_from('<q', block0, 112)
    latest = None
    for index in range(desc_blocks):
        data = bytearray(image.map[(desc_base + index) * PAGE:(desc_base + index + 1) * PAGE])
        if data[32:36] == b'NXSB' and fletcher64(data[8:]) == data[:8]:
            xid, = struct.unpack_from('<Q', data, 16)
            if latest is None or xid > latest[0]:
                latest = (xid, desc_base + index, data)
    xid, sb_block, sb = latest
    old_blocks, = struct.unpack_from('<Q', sb, 40)
    if blocks <= old_blocks:
        raise SystemExit(f'the container already has {old_blocks} blocks')
    # the space manager: an ephemeral object, found through this checkpoint's maps
    desc_index, desc_len = struct.unpack_from('<II', sb, 136)
    spaceman_oid, = struct.unpack_from('<Q', sb, 152)
    maps = {}   # ephemeral oid -> (block, size)
    for k in range(desc_len):
        cpm = image.block(desc_base + (desc_index + k) % desc_blocks)
        if struct.unpack_from('<I', cpm, 24)[0] & 0xffff != CHECKPOINT_MAP:
            continue
        count, = struct.unpack_from('<I', cpm, 36)
        for e in range(count):
            _, _, size, _, _, oid, paddr = struct.unpack_from('<IIIIQQQ', cpm, 40 + 40 * e)
            maps[oid] = (paddr, size)
    spaceman_block, size = maps.get(spaceman_oid, (None, 0))
    if spaceman_block is None or size != PAGE:
        raise SystemExit(f'space manager: {spaceman_block} of {size} bytes: unsupported')
    sm = image.block(spaceman_block, SPACEMAN)
    block_size, per_chunk, per_cib = struct.unpack_from('<III', sm, 32)
    dev_blocks, dev_chunks, cib_count, cab_count, dev_free, addr_offset = struct.unpack_from('<QQIIQI', sm, 48)
    if block_size != PAGE or dev_blocks != old_blocks or cab_count or old_blocks % per_chunk:
        raise SystemExit(f'space manager layout unsupported: bs {block_size} blocks {dev_blocks} cabs {cab_count}')
    chunks = (blocks + per_chunk - 1) // per_chunk
    if (chunks + per_cib - 1) // per_cib != cib_count:
        raise SystemExit(f'{chunks} chunks need another chunk-info block')
    cib_block, = struct.unpack_from('<Q', sm, addr_offset + 8 * (cib_count - 1))
    cib = image.block(cib_block, CIB)
    cib_xid, = struct.unpack_from('<Q', cib, 16)
    infos, = struct.unpack_from('<I', cib, 36)
    added = 0
    for chunk in range(dev_chunks, chunks):
        count = min(per_chunk, blocks - chunk * per_chunk)
        struct.pack_into('<QQIIQ', cib, 40 + 32 * infos, cib_xid, chunk * per_chunk, count, count, 0)
        infos += 1
        added += count
    struct.pack_into('<I', cib, 36, infos)
    struct.pack_into('<QQ', sm, 48, blocks, chunks)
    struct.pack_into('<Q', sm, 48 + 24, dev_free + added)
    struct.pack_into('<H', sm, 200 + 40 + 24, main_fq_node_limit(blocks))   # sm_fq[SFQ_MAIN].sfq_tree_node_limit
    cib_block = grow_internal_pool(image, sm, cib, cib_block, maps, dev_chunks, chunks + cib_count)
    for number, data in ((sb_block, sb), (0, block0)):
        struct.pack_into('<Q', data, 40, blocks)
        struct.pack_into('<I', data, 180, max_volumes(blocks * PAGE))
        image.put(number, data)
    image.put(spaceman_block, sm)
    image.put(cib_block, cib)
    print(f'container xid {xid}: {old_blocks} -> {blocks} blocks, {dev_chunks} -> {chunks} chunks, +{added} free, '
          f'max volumes {max_volumes(blocks * PAGE)}, changed blocks {sorted(image.changed)}')
    return image.changed


def bit(data, index, value=None):
    if value is None:
        return data[index // 8] >> (index % 8) & 1
    if value:
        data[index // 8] |= 1 << (index % 8)
    else:
        data[index // 8] &= ~(1 << (index % 8)) & 0xff


def grow_internal_pool(image, sm, cib, cib_block, maps, first_new_chunk, entries):
    """The internal pool (chunk bitmaps, chunk-info blocks) is sized 3 blocks per chunk and chunk-info block (apfsprogs mkapfs,
    checked by apfsck), and is contiguous: the one the container was made with is boxed in by data, so it moves to the start of
    the first new chunk, whole (every block at the same offset: live ones, and those the internal-pool free queue still holds),
    and grows there. Its references (the chunk-info block's address and object id, every chunk's bitmap address, the free
    queue's keys) shift by the same distance; the old place goes back to its chunk. Returns the chunk-info block's new address."""
    per_chunk, = struct.unpack_from('<I', sm, 36)
    old_count, = struct.unpack_from('<Q', sm, 152)
    bm_size, bm_blocks, bm_base, old_base = struct.unpack_from('<IIQQ', sm, 160)
    need = 3 * entries
    if old_count >= need:
        return cib_block
    if bm_size != 1 or need > 8 * PAGE or need >= per_chunk:
        raise SystemExit(f'internal pool of {need} blocks: unsupported')
    new_base = first_new_chunk * per_chunk
    shift = new_base - old_base
    moved = lambda addr: addr + shift if old_base <= addr < old_base + old_count else addr   # noqa: E731
    # the internal-pool free queue: a single fixed-size leaf of (xid, paddr) keys
    fq_oid, = struct.unpack_from('<Q', sm, 200 + 8)
    fq_block, fq_size = maps[fq_oid]
    node = image.block(fq_block)
    flags, level, nkeys = struct.unpack_from('<HHI', node, 32)
    toc_off, toc_len = struct.unpack_from('<HH', node, 40)
    if fq_size != PAGE or flags & 7 != 7 or level:
        raise SystemExit(f'internal-pool free queue node flags {flags:#x} level {level}: unsupported')
    keys = 56 + toc_off + toc_len
    for index in range(nkeys):
        k, _ = struct.unpack_from('<HH', node, 56 + toc_off + 4 * index)
        xid, paddr = struct.unpack_from('<QQ', node, keys + k)
        struct.pack_into('<Q', node, keys + k + 8, moved(paddr))
    image.put(fq_block, node)
    # the pool itself, then what points into it
    for offset in range(old_count):
        image.map[(new_base + offset) * PAGE:(new_base + offset + 1) * PAGE] = image.map[(old_base + offset) * PAGE:(old_base + offset + 1) * PAGE]
        image.changed.add(new_base + offset)
    new_cib = moved(cib_block)
    struct.pack_into('<Q', cib, 8, new_cib)
    addr_offset, = struct.unpack_from('<I', sm, 48 + 32)
    cib_count, = struct.unpack_from('<I', sm, 48 + 16)
    for i in range(cib_count):
        address, = struct.unpack_from('<Q', sm, addr_offset + 8 * i)
        struct.pack_into('<Q', sm, addr_offset + 8 * i, moved(address))
    infos, = struct.unpack_from('<I', cib, 36)
    for i in range(infos):
        at = 40 + 32 * i
        struct.pack_into('<Q', cib, at + 24, moved(struct.unpack_from('<Q', cib, at + 24)[0]))
    # the current internal-pool bitmap: the new chunk's bitmap takes the first block past the copied pool
    bm_index, = struct.unpack_from('<H', sm, struct.unpack_from('<I', sm, 328)[0])
    pool_bitmap = bytearray(image.map[(bm_base + bm_index) * PAGE:(bm_base + bm_index + 1) * PAGE])
    chunk_bitmap = new_base + old_count
    bit(pool_bitmap, old_count, 1)
    image.map[(bm_base + bm_index) * PAGE:(bm_base + bm_index + 1) * PAGE] = bytes(pool_bitmap)
    image.changed.add(bm_base + bm_index)
    # main bitmaps: the old place is free in its chunk, the new pool used in the first new chunk
    cib_xid, = struct.unpack_from('<Q', cib, 16)
    old_chunk, new_chunk = old_base // per_chunk, first_new_chunk
    if (old_base + old_count - 1) // per_chunk != old_chunk:
        raise SystemExit('the old internal pool spans chunks: unsupported')
    at = 40 + 32 * old_chunk
    _, _, _, free, bitmap_addr = struct.unpack_from('<QQIIQ', cib, at)
    data = bytearray(image.map[bitmap_addr * PAGE:(bitmap_addr + 1) * PAGE])
    for b in range(old_base, old_base + old_count):
        if not bit(data, b - old_chunk * per_chunk):
            raise SystemExit(f'block {b} of the internal pool is free in its chunk')
        bit(data, b - old_chunk * per_chunk, 0)
    image.map[bitmap_addr * PAGE:(bitmap_addr + 1) * PAGE] = bytes(data)
    image.changed.add(bitmap_addr)
    struct.pack_into('<Q', cib, at, cib_xid)
    struct.pack_into('<I', cib, at + 20, free + old_count)
    data = bytearray(PAGE)
    for b in range(need):
        bit(data, b, 1)
    image.map[chunk_bitmap * PAGE:(chunk_bitmap + 1) * PAGE] = bytes(data)
    image.changed.add(chunk_bitmap)
    at = 40 + 32 * new_chunk
    _, _, count, free, _ = struct.unpack_from('<QQIIQ', cib, at)
    struct.pack_into('<QQIIQ', cib, at, cib_xid, new_chunk * per_chunk, count, free - need, chunk_bitmap)
    dev_free, = struct.unpack_from('<Q', sm, 48 + 24)
    struct.pack_into('<Q', sm, 48 + 24, dev_free + old_count - need)
    struct.pack_into('<Q', sm, 152, need)
    struct.pack_into('<Q', sm, 176, new_base)
    print(f'internal pool: {old_count} blocks at {old_base} -> {need} at {new_base}, chunk-info block {cib_block} -> {new_cib}, '
          f'{nkeys} free-queue keys moved')
    return new_cib


def seed_regions(path):
    return packed_ramdisk.regions(Path(path).read_bytes())


def fold(old_seed, store_path, raw):
    logical, extents = seed_regions(old_seed)
    store = Store(store_path)
    store.check(logical, extents)
    image = Image(raw)
    if len(image.map) <= logical or len(image.map) % PAGE:
        raise SystemExit(f'{raw} must be truncated to the new size, above {logical}')
    for offset, data in extents:
        image.map[offset:offset + len(data)] = data
    count = store.fold_into(image.handle)
    image.handle.flush()
    image.map = mmap.mmap(image.handle.fileno(), 0)
    print(f'folded {count} overlay pages over the seed')
    changed = grow_container(image, len(image.map) // PAGE)
    Path(str(raw) + '.changed').write_text(' '.join(map(str, sorted(changed))) + '\n')
    image.map.flush()


def header(pages, digest, generation):
    block = bytearray(PAGE)
    block[:8] = b'SHNGDATA'
    struct.pack_into('<IIQ', block, 8, 1, 64, pages)
    block[24:56] = bytes.fromhex(digest)
    struct.pack_into('<I', block, 56, generation)
    struct.pack_into('<I', block, 60, zlib.crc32(bytes(block[:60])))
    return bytes(block)


def make_store(new_seed, store_path, raw, output):
    logical, extents = seed_regions(new_seed)
    digest = packed_ramdisk.logical_hash(logical, extents)
    old = Store(store_path)
    generation, = struct.unpack_from('<I', old.map, PAGE + 56)
    pages = logical // PAGE
    with open(raw, 'rb') as handle:
        image = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
    if len(image) != logical:
        raise SystemExit(f'{raw} is {len(image)} bytes, the new seed {logical}')
    with open(output, 'xb') as handle:
        handle.truncate(len(old.map))
        handle.write(old.map[:PAGE])
        handle.write(header(pages, digest, generation))
    new = Store(output, writable=True)
    window = 1 + 1 + new.bitmap_blocks + pages
    if window > len(old.map) // PAGE:
        raise SystemExit(f'{pages} pages need {window} store blocks, the store has {len(old.map) // PAGE}')
    indexes = set(old.present())
    indexes.update(int(n) for n in Path(str(raw) + '.changed').read_text().split())
    seed = {}
    for offset, data in extents:
        for at in range(0, len(data), PAGE):
            seed[(offset + at) // PAGE] = data[at:at + PAGE]
    zero = bytes(PAGE)
    written = 0
    for index in sorted(indexes):
        data = image[index * PAGE:(index + 1) * PAGE]
        if data != seed.get(index, zero) or old.has(index):
            new.put(index, data)
            written += 1
    new.close()
    print(f'{output}: {pages} pages for seed {digest[:16]}, generation {generation}, {written} overlay pages')


def make_seed(old_seed, new_seed, size):
    blob = bytearray(Path(old_seed).read_bytes())
    logical, extents = packed_ramdisk.regions(bytes(blob))
    if size % PAGE or size <= logical:
        raise SystemExit(f'the new size must be page-aligned and above {logical}')
    struct.pack_into('<Q', blob, 16, size)
    packed_ramdisk.regions(bytes(blob))
    with open(new_seed, 'xb') as handle:
        handle.write(blob)
    print(f'{new_seed}: {logical} -> {size} bytes, identity {packed_ramdisk.logical_hash(size, extents)[:16]}')


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == 'seed':
        make_seed(sys.argv[2], sys.argv[3], int(sys.argv[4], 0))
    elif len(sys.argv) == 5 and sys.argv[1] == 'fold':
        fold(*sys.argv[2:5])
    elif len(sys.argv) == 6 and sys.argv[1] == 'store':
        make_store(*sys.argv[2:6])
    else:
        sys.exit(__doc__)
