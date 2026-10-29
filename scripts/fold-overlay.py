#!/usr/bin/env python3
"""Fold a DroidVMDataStore overlay (SHNGDATA) into a DBRDISK1 seed, so the next boot starts where the last one ended.

  fold-overlay.py SEED.dbr OVERLAY.img OUTPUT.dbr

The seed is the immutable base NativeRamBlock boots from; the overlay holds the pages a running system changed, keyed by the
seed's SHA-256 (sources/UniXNU/drivers/NativeRamBlock/PersistOverlay.h). Applying it here turns a first boot's work (APFS
metadata, font and LaunchServices caches, shader caches: ~676 MB of writes) into part of the seed, so the boot that follows
does not repeat it. The output carries a new SHA-256, so a store built against the old seed is stale and starts empty: that is
why the overlay has to be applied here rather than left beside the new seed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "out/x12377/un/drivers/DarwinBoot/Test"))
import packed_ramdisk

PAGE = 4096


def unpack(seed):
    """The seed's raw bytes: the packed format is a header and a list of (offset, bytes) extents, holes stay zero."""
    blob = seed.read_bytes()
    logical, extents = packed_ramdisk.regions(blob)
    base = bytearray(logical)
    for offset, chunk in extents:
        base[offset:offset + len(chunk)] = chunk
    return base


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    seed, overlay, output = (Path(p).resolve() for p in sys.argv[1:4])
    base = unpack(seed)
    blob = overlay.read_bytes()
    # the store's block 0 is its own label; the overlay starts at block 1
    if blob[:16] != b'DroidVMDataStore':
        sys.exit(f'{overlay}: not a DroidVMDataStore image')
    blob = blob[PAGE:]

    if blob[:8] != b'SHNGDATA':
        sys.exit(f'{overlay}: block 1 is not a SHNGDATA overlay')
    version = int.from_bytes(blob[8:12], 'little')
    header = int.from_bytes(blob[12:16], 'little')
    pages = int.from_bytes(blob[16:24], 'little')
    digest = blob[24:56]
    if version != 1 or header != 64:
        sys.exit(f'{overlay}: version {version} header {header}')

    import hashlib
    base_digest = hashlib.sha256(base).digest()
    if digest != base_digest:
        sys.exit(f'{overlay}: made against seed {digest.hex()[:16]}, this seed is {base_digest.hex()[:16]}')

    bitmap_blocks = (pages + 8 * PAGE - 1) // (8 * PAGE)
    changed = 0
    for index in range(pages):
        byte = blob[PAGE + index // 8]
        if not (byte >> (index % 8)) & 1:
            continue
        at = (1 + bitmap_blocks + index) * PAGE
        if at + PAGE > len(blob):
            sys.exit(f'{overlay}: page {index} past the end of the file')
        if index * PAGE + PAGE > len(base):
            sys.exit(f'{overlay}: page {index} past the end of the seed ({len(base)} bytes)')
        base[index * PAGE:(index + 1) * PAGE] = blob[at:at + PAGE]
        changed += 1

    print(f'{overlay.name}: {changed} changed pages of {pages} ({changed * PAGE / 2**20:.1f} MiB) folded in')
    staged = output.with_suffix('.raw')
    staged.write_bytes(base)
    packed_ramdisk.pack(staged, output)
    staged.unlink()
    new_digest = hashlib.sha256(base).hexdigest()
    print(f'{output}: {output.stat().st_size} bytes, seed sha256 {new_digest[:16]}')


if __name__ == '__main__':
    main()
