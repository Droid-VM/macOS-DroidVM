"""The phone's Data store (DroidVMDataStore, crosvm --virtio-mmio-block): block 0 is its label ("DroidVMDataStore"), the window after
it NativeRamBlock's SHNGDATA overlay over the Data seed (sources/UniXNU/drivers/NativeRamBlock/PersistOverlay.h): a header with the
seed's identity, a presence bitmap with one bit per page of the disk, then page i at a fixed block. Used by fold-overlay.py (the
overlay into a new seed) and stage-gpu-plugin.py --store (a change to the Data volume written back into the overlay, the seed kept)."""
import mmap
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sources/UniXNU/drivers/DarwinBoot/Test'))
import packed_ramdisk  # noqa: E402

PAGE = 4096


class Store:
    def __init__(self, path, writable=False):
        self.path = Path(path)
        with self.path.open('r+b' if writable else 'rb') as handle:   # mapped: the file is 17 GiB, mostly holes
            self.map = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_WRITE if writable else mmap.ACCESS_READ)
        if self.map[:16] != b'DroidVMDataStore':
            raise SystemExit(f'{path}: not a DroidVMDataStore image')
        header = self.map[PAGE:2 * PAGE]
        if header[:8] != b'SHNGDATA':
            raise SystemExit(f'{path}: block 1 is not a SHNGDATA overlay')
        if int.from_bytes(header[8:12], 'little') != 1 or int.from_bytes(header[12:16], 'little') != 64:
            raise SystemExit(f'{path}: overlay version or header size unknown')
        self.pages = int.from_bytes(header[16:24], 'little')
        self.digest = bytes(header[24:56]).hex()
        self.bitmap_blocks = (self.pages + 8 * PAGE - 1) // (8 * PAGE)
        self.changed = set()   # store blocks written by put()

    def check(self, logical, extents):
        """The overlay must have been made against this seed (its page count and identity)."""
        identity = packed_ramdisk.logical_hash(logical, extents)
        if self.pages != logical // PAGE or self.digest != identity:
            raise SystemExit(f'{self.path}: made against seed {self.digest[:16]}, this seed is {identity[:16]}')

    def has(self, index):
        return self.map[2 * PAGE + index // 8] >> (index % 8) & 1

    def page(self, index):
        at = (2 + self.bitmap_blocks + index) * PAGE
        return self.map[at:at + PAGE]

    def present(self):
        bitmap = self.map[2 * PAGE:(2 + self.bitmap_blocks) * PAGE]
        for byte_index, byte in enumerate(bitmap):
            if byte:
                for bit in range(8):
                    if byte >> bit & 1 and byte_index * 8 + bit < self.pages:
                        yield byte_index * 8 + bit

    def put(self, index, data):
        """Page `index` and its bit, as NativeRamBlock writes them (the page, then the bitmap block)."""
        block = 2 + self.bitmap_blocks + index
        self.map[block * PAGE:(block + 1) * PAGE] = data
        self.map[2 * PAGE + index // 8] |= 1 << (index % 8)
        self.changed.update((block, 2 + index // (8 * PAGE)))

    def fold_into(self, handle):
        """Write every page of the overlay into a raw image of the seed (an open file)."""
        count = 0
        for index in self.present():
            handle.seek(index * PAGE)
            handle.write(self.page(index))
            count += 1
        return count

    def refresh(self, raw, extents):
        """Put every page of the raw image (the seed with this overlay folded in, then changed) that differs from what the seed and
        the overlay give into the overlay. Only the image's data regions are read: a page outside them is a hole the seed, the
        overlay and the change never wrote."""
        seed = {}
        for offset, data in extents:
            for at in range(0, len(data), PAGE):
                seed[(offset + at) // PAGE] = memoryview(data)[at:at + PAGE]
        zero = bytes(PAGE)
        with open(raw, 'rb') as handle:
            # all ranges first: data_ranges moves the file's offset under the buffered reader's
            for start, end in list(packed_ramdisk.data_ranges(handle, self.pages * PAGE)):
                handle.seek(start - start % PAGE)
                for index in range(start // PAGE, (end + PAGE - 1) // PAGE):
                    data = handle.read(PAGE)
                    before = self.page(index) if self.has(index) else seed.get(index, zero)
                    if data != before:
                        self.put(index, data)

    def runs(self):
        """The written store blocks as (first, count) runs."""
        blocks = sorted(self.changed)
        runs = []
        for block in blocks:
            if runs and runs[-1][0] + runs[-1][1] == block:
                runs[-1][1] += 1
            else:
                runs.append([block, 1])
        return runs

    def close(self):
        self.map.flush()
        self.map.close()
