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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sources/UniXNU/drivers/DarwinBoot/Test"))
import packed_ramdisk  # noqa: E402

from data_store import Store  # noqa: E402

PAGE = 4096


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    seed, overlay, output = (Path(p).resolve() for p in sys.argv[1:4])
    logical, extents = packed_ramdisk.regions(seed.read_bytes())
    store = Store(overlay)
    store.check(logical, extents)
    staged = output.with_suffix('.raw')
    with staged.open('wb') as handle:   # sparse, as stage-gpu-plugin.py writes it
        handle.truncate(logical)
        for offset, chunk in extents:
            handle.seek(offset)
            handle.write(chunk)
        changed = store.fold_into(handle)
    print(f'{overlay.name}: {changed} changed pages of {store.pages} ({changed * PAGE / 2**20:.1f} MiB) folded in')
    packed_ramdisk.pack(staged, output)   # at most 256 MiB of data: a store of a used Data volume needs stage-gpu-plugin.py --store
    staged.unlink()
    print(f'{output}: {output.stat().st_size} bytes, seed {packed_ramdisk.logical_hash(*packed_ramdisk.regions(output.read_bytes()))[:16]}')


if __name__ == '__main__':
    main()
