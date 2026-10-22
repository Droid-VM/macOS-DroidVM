#!/usr/bin/env python3
"""Copy the reference toolchain into macos; never retain links into the source workspace."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'toolchains/linux'


def main(source):
    reference = source.resolve()
    old = reference / 'out/gunyah-linux'
    config = json.loads((old / 'bin/linux-toolchain.json').read_text())
    if DEST.exists():
        raise ValueError(f'{DEST} already exists; refusing to overwrite')
    mapping = {str(old): str(DEST), str(Path(config['sdk'])): str(DEST / 'sdk'),
               str(reference): str(ROOT)}

    def relocate(value):
        if isinstance(value, dict):
            return {k: relocate(v) for k, v in value.items()}
        if isinstance(value, list):
            return [relocate(v) for v in value]
        if isinstance(value, str):
            for before in sorted(mapping, key=len, reverse=True):
                if value == before or value.startswith(before + '/'):
                    return mapping[before] + value[len(before):]
        return value

    records = []
    def copy_tree(src, dst):
        # Dereference source symlinks: the result is independent of ios and its caches.
        shutil.copytree(src, dst, symlinks=False, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        for path in sorted(dst.rglob('*')):
            if path.is_file():
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                records.append({'path': str(path.relative_to(DEST)), 'sha256': digest})

    for name in ('toolchain', 'host-deps', 'python-deps', 'apple-iig', 'cctools-work'):
        copy_tree(old / name, DEST / name)
    copy_tree(Path(config['sdk']), DEST / 'sdk')
    copy_tree(old / 'appleclang/apple-tools', DEST / 'appleclang/apple-tools')
    for name in ('extracted.json',):
        shutil.copy2(old / 'appleclang' / name, DEST / 'appleclang' / name)
    bindir = DEST / 'bin'
    bindir.mkdir()
    for name in ('target-clang', 'target-clang++', 'target-iig', 'xcrun', 'plutil', 'ditto'):
        (bindir / name).symlink_to(ROOT / 'compat/xnu-linux/linux/darwin-tool.py')
    config = relocate(config)
    config['appleclang']['container'] = 'macos-appleclang'
    config['appleclang']['workspace'] = str(ROOT)
    # A new isolated runtime must be started and verified before enabling compilation.
    config['appleclang'].pop('image_id', None)
    config['xnu_build_verified'] = False
    (bindir / 'linux-toolchain.json').write_text(json.dumps(config, indent=2) + '\n')
    (DEST / 'import-manifest.json').write_text(json.dumps({
        'source': str(reference), 'files': records, 'runtime_started': False}, indent=2) + '\n')
    print(f'Imported {len(records)} files into {DEST}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    main(parser.parse_args().reference)
