#!/usr/bin/env python3
"""Download one pinned IPSW member by ranges, verify ZIP CRC32 and the Apple manifest digest, then publish it.

    macos-fetch-member.py COMPONENT [--output-dir artifacts/23G93]

COMPONENT is a key of identity.components in the profile (OS, Cryptex1,SystemOS, ...). Every request carries
If-Match with the pinned strong ETag. Stored members resume from the .part file; deflated members restart.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import struct
import time
import urllib.request
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('inputs', ROOT / 'scripts/macos-inputs.py')
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)
CHUNK = 16 * 1024 * 1024


def fetch(url, etag, start, end, total):
    expected = f'bytes {start}-{end}/{total}'
    for attempt in range(30):
        try:
            request = urllib.request.Request(url, headers={
                'Range': f'bytes={start}-{end}', 'If-Match': etag, 'Accept-Encoding': 'identity'})
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status != 206 or response.headers.get('Content-Range') != expected:
                    raise ValueError('server did not return the exact requested range')
                if response.headers.get('ETag') != etag:
                    raise ValueError('remote identity changed')
                data = response.read(end - start + 2)
            if len(data) == end - start + 1:
                return data
        except urllib.error.HTTPError as error:
            if error.code == 412:
                raise ValueError('remote identity changed')
            print('retry', attempt, error, flush=True)
        except (OSError, ValueError) as error:
            if 'identity changed' in str(error) or 'exact requested' in str(error):
                raise
            print('retry', attempt, error, flush=True)
        time.sleep(3)
    raise SystemExit(f'range {start}-{end} failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component')
    parser.add_argument('--profile', default='configs/macos-23G93.json')
    parser.add_argument('--output-dir', default='artifacts/23G93')
    parser.add_argument('--identity', help='device class of another BuildManifest identity (e.g. vma2macosap); read from the inventory of macos-inputs.py')
    args = parser.parse_args()
    profile = json.loads(inputs.local_path(args.profile).read_text())
    spec_ipsw = profile['ipsw']
    if args.identity:
        inventory = json.loads(inputs.local_path('artifacts/23G93/metadata/identities.json').read_text())
        found = [i for i in inventory['identities'] if i['device_class'] == args.identity and i['variant'] == 'macOS Customer Erase']
        if len(found) != 1:
            raise SystemExit(f'identity {args.identity!r} not found exactly once in the inventory')
        entry = found[0]['components'][args.component]
        component = {'path': entry['path'], 'size': entry['size'], 'compressed_size': entry['compressed_size'],
                     'zip_method': entry['zip_method'], 'apple_digest_hex': entry['apple_digest_hex']}
    else:
        component = profile['identity']['components'][args.component]
    digest_hex = component['apple_digest_hex']
    algorithm = {64: 'sha256', 96: 'sha384', 128: 'sha512', 40: 'sha1'}[len(digest_hex)]
    out_dir = inputs.local_path(args.output_dir)
    final = out_dir / Path(component['path']).name
    if final.exists():
        raise SystemExit(f'{final} exists')
    out_dir.mkdir(parents=True, exist_ok=True)
    with inputs.RemoteFile(spec_ipsw['url'], spec_ipsw['filesize']) as remote, zipfile.ZipFile(remote) as archive:
        entry = archive.getinfo(component['path'])
        remote.seek(entry.header_offset)
        header = remote.read(30)
        name_len, extra_len = struct.unpack_from('<HH', header, 26)
        start = entry.header_offset + 30 + name_len + extra_len
        etag = remote.etag
    assert (entry.file_size, entry.compress_size, entry.compress_type) == (
        component['size'], component['compressed_size'], component['zip_method']), 'component metadata changed'
    part = final.with_name(final.name + '.part')
    crc, digest, written = 0, hashlib.new(algorithm), 0
    stored = entry.compress_type == 0
    if part.exists() and stored:
        with part.open('rb') as old:
            while block := old.read(1 << 24):
                crc = zlib.crc32(block, crc)
                digest.update(block)
                written += len(block)
        if written > entry.file_size:
            raise SystemExit('stale .part larger than member')
    elif part.exists():
        part.unlink()
    inflater = zlib.decompressobj(-15)
    position = written if stored else 0
    with part.open('ab' if stored else 'wb') as handle:
        while position < entry.compress_size:
            end = min(position + CHUNK, entry.compress_size) - 1
            data = fetch(spec_ipsw['url'], etag, start + position, start + end, spec_ipsw['filesize'])
            position = end + 1
            if not stored:
                data = inflater.decompress(data)
            handle.write(data)
            crc = zlib.crc32(data, crc)
            digest.update(data)
            written += len(data)
            print(f'{written / entry.file_size:6.1%}', end='\r', flush=True)
        if not stored:
            tail = inflater.flush()
            handle.write(tail)
            crc = zlib.crc32(tail, crc)
            digest.update(tail)
            written += len(tail)
        handle.flush()
        os.fsync(handle.fileno())
    if written != entry.file_size or crc != entry.CRC:
        raise SystemExit(f'size/CRC mismatch: {written} {crc:#x} vs {entry.file_size} {entry.CRC:#x}')
    if digest.hexdigest() != digest_hex:
        raise SystemExit(f'{algorithm} differs from the Apple manifest digest: {digest.hexdigest()}')
    part.rename(final)
    print(json.dumps({'file': str(final.relative_to(ROOT)), 'size': written, 'crc32': f'{crc:#010x}',
                      algorithm: digest.hexdigest(), 'matches_apple_manifest_digest': True}, indent=2))


if __name__ == '__main__':
    main()
