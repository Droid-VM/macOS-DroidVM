#!/usr/bin/env python3
"""Lay the locally built owner policies out as the verified-root-inputs directory owner-policy-dirs.py reads.

    macos-policy-inputs.py [--output out/owner/inputs]

Writes os.manifest.bin, systemos.manifest.bin, trusted-key.bin, os.samples.bin and inputs.json (the layout of
make-virt-root.py, without its CI-key encryption) from out/owner/{os,systemos}-23G93 and macos-root-pins.json.
"""
import argparse
import os
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
TAG = os.environ.get('MACOS_TAG', '23G93')   # artifacts/TAG and out/owner/{os,systemos}-TAG (macOS 27.0.1: MACOS_TAG=27.0.1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='out/owner/inputs')
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        raise SystemExit(f'refusing {output}')
    pins = json.loads((ROOT / 'out/owner/macos-root-pins.json').read_text())
    records = {}
    for name in ('os', 'systemos'):
        directory = ROOT / 'out/owner' / f'{name}-{TAG}'
        record = json.loads((directory / 'manifest.json').read_text())
        pin = pins[name]
        for key, field in (('image_sha256', 'image_sha256'), ('block_count', 'blocks_verified'),
                           ('image_bytes', 'image_bytes'), ('trusted_key_sha256', 'trusted_key_sha256'),
                           ('volume_uuid', 'volume_uuid')):
            if record[key] != pin[field]:
                raise SystemExit(f'{name}: {key} differs from macos-root-pins.json')
        if len((directory / 'manifest.bin').read_bytes()[:544]) != 544:
            raise SystemExit(f'{name}: truncated manifest')
        records[name] = record
    output.mkdir(parents=True)
    for name in ('os', 'systemos'):
        shutil.copyfile(ROOT / 'out/owner' / f'{name}-{TAG}' / 'manifest.bin', output / f'{name}.manifest.bin')
    shutil.copyfile(ROOT / f'out/owner/os-{TAG}/trusted-key.bin', output / 'trusted-key.bin')
    record = records['os']
    count, size = record['block_count'], record['image_bytes']
    indices = [0, 1, count // 2, count - 1]
    lengths = [4096, 4096, 4096, size - (count - 1) * 4096]
    image = ROOT / f'artifacts/{TAG}/os.raw'
    with image.open('rb') as stream, (output / 'os.samples.bin').open('wb') as samples:
        for index, length in zip(indices, lengths):
            stream.seek(index * 4096)
            data = stream.read(length)
            if len(data) != length:
                raise SystemExit('short OS sample read')
            samples.write(data.ljust(4096, b'\0'))
    record.update(sample_indices=indices, sample_lengths=lengths)
    (output / 'inputs.json').write_text(json.dumps(records, indent=2) + '\n')
    print(f'{output.relative_to(ROOT)}: samples {indices} lengths {lengths}')


if __name__ == '__main__':
    main()
