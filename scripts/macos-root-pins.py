#!/usr/bin/env python3
"""Collect the locally generated OS/SystemOS owner policies into the pins file the macOS probe builders read.

    macos-root-pins.py [--os out/owner/os-23G93] [--systemos out/owner/systemos-23G93] [--output out/owner/macos-root-pins.json]

The pins describe the images this project built itself (verification.json from local-root-policy.py), replacing the
hardcoded digests of the upstream author's converted disks.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = 'out/owner/macos-root-pins.json'


def load(path=None):
    """Return {'os': {...}, 'systemos': {...}} from the pins file; stop if it is missing."""
    path = ROOT / (path or DEFAULT)
    if not path.is_file():
        raise SystemExit(f'{path} missing: run scripts/macos-root-pins.py after local-root-policy.py')
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--os', default='out/owner/os-23G93')
    parser.add_argument('--systemos', default='out/owner/systemos-23G93')
    parser.add_argument('--output', default=DEFAULT)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        raise SystemExit(f'refusing {output}')
    pins = {}
    for name, directory in (('os', args.os), ('systemos', args.systemos)):
        report = json.loads((ROOT / directory / 'verification.json').read_text())
        pins[name] = {key: report[key] for key in ('image_sha256', 'blocks_verified', 'image_bytes',
                                                    'volume_uuid', 'trusted_key_sha256', 'manifest_sha256')}
    if pins['os']['trusted_key_sha256'] != pins['systemos']['trusted_key_sha256']:
        raise SystemExit('OS and SystemOS policies use different owner keys')
    output.write_text(json.dumps(pins, indent=2) + '\n')
    print(output.relative_to(ROOT), json.dumps(pins, indent=2))


if __name__ == '__main__':
    main()
