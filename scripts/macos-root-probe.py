#!/usr/bin/env python3
"""Write the macOS-root variant of UniXNU scripts/build-verified-root-probe.py.

    macos-root-probe.py SOURCE DESTINATION

The probe builder pins the 21H461 OS and SystemOS images that its policies must describe. For the macOS root (CI matrix
root=macos) the policies describe the 23G93 OS disk and the SystemOS disk of make-macos-systemos.sh instead (the pins of
out/owner/macos-root-pins.json, made by macos-root-pins.py from the locally built images), and its hash tables are placed after the kernel text. DESTINATION goes to the device repository's scripts/, which the unixnu tree copies over the
UniXNU one; the upstream file is left as is.
"""
from pathlib import Path
import importlib.util
import sys

spec = importlib.util.spec_from_file_location('pins', Path(__file__).with_name('macos-root-pins.py'))
pins_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pins_module)
PINS = pins_module.load()

REPLACEMENTS = [
    ("'e5634d04a8ac35f024845f583394e0a35deb26a04cb0c00286a8674e25a9a4f2'",
     repr(PINS['os']['image_sha256']), 1),
    ("'b4908cde41d23e6bc05e6af51a2c9eeb00cf0f863a6a18b1600c96a3fd70414f'",
     repr(PINS['systemos']['image_sha256']), 2),
    ("expected_count = 1483785 if", f"expected_count = {PINS['os']['blocks_verified']} if", 1),
    (" else 806400\n", f" else {PINS['systemos']['blocks_verified']}\n", 1),
    ("extra_meta['blocks_verified'] != 806400", f"extra_meta['blocks_verified'] != {PINS['systemos']['blocks_verified']}", 1),
    ("image_bytes=3303014400", f"image_bytes={PINS['systemos']['image_bytes']}", 1),
    # The macOS hash tables (143 MB against 73 MB) in __DATA_CONST push the late archives' code out of B/BL range
    # (+/-128 MB) of the prelinked kexts: keep them in __DATA, after the kernel text.
    (".section __DATA_CONST,__const\n", ".section __DATA,__data\n", 1),
]

source, destination = map(Path, sys.argv[1:3])
text = source.read_text()
for old, new, count in REPLACEMENTS:
    if text.count(old) != count:
        raise SystemExit(f'{source}: expected {count} of {old!r}, found {text.count(old)}')
    text = text.replace(old, new)
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(text)
print(f'{destination}: macOS root pins')
