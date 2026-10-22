#!/usr/bin/env python3
"""Fetch only the macOS IPSW directory and BuildManifest, then inventory identities."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import plistlib
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class RemoteFile(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.position = url, size, 0
        self.cache = {}
        self.downloaded = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        if whence not in (0, 1, 2):
            raise ValueError('invalid whence')
        position = (0, self.position, self.size)[whence] + offset
        if position < 0:
            raise ValueError('negative seek')
        self.position = position
        return position

    def readinto(self, buffer):
        want = max(0, min(len(buffer), self.size - self.position))
        done = 0
        while done < want:
            index, inside = divmod(self.position, 256 * 1024)
            if index not in self.cache:
                start = index * 256 * 1024
                end = min(start + 256 * 1024, self.size) - 1
                expected = f'bytes {start}-{end}/{self.size}'
                request = urllib.request.Request(self.url, headers={
                    'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity'})
                with urllib.request.urlopen(request, timeout=30) as response:
                    if response.status != 206 or response.headers.get('Content-Range') != expected:
                        raise ValueError('server did not return the exact requested range')
                    data = response.read(end - start + 2)
                if len(data) != end - start + 1:
                    raise ValueError('incorrect range length')
                self.downloaded += len(data)
                if len(self.cache) >= 8:
                    self.cache.pop(next(iter(self.cache)))
                self.cache[index] = data
            part = self.cache[index][inside:inside + want - done]
            buffer[done:done + len(part)] = part
            done += len(part)
            self.position += len(part)
        return done


def local_path(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f'path must stay within {ROOT}')
    return path


def inspect(profile_path, output):
    profile = json.loads(profile_path.read_text())
    spec = profile['ipsw']
    if output.exists():
        raise ValueError(f'refusing to overwrite {output}')
    with RemoteFile(spec['url'], spec['filesize']) as stream, zipfile.ZipFile(stream) as archive:
        member = archive.getinfo('BuildManifest.plist')
        if member.file_size > 16 * 1024 * 1024:
            raise ValueError('unexpectedly large BuildManifest')
        raw = archive.read(member)  # zipfile validates CRC before accepting the member.
        expected_hash = spec.get('manifest_sha256')
        if expected_hash and hashlib.sha256(raw).hexdigest() != expected_hash:
            raise ValueError('BuildManifest differs from pinned input')
        manifest = plistlib.loads(raw)
        if (manifest['ProductVersion'], manifest['ProductBuildVersion']) != (spec['version'], spec['buildid']):
            raise ValueError('IPSW version/build mismatch')
        if spec['identifier'] not in manifest['SupportedProductTypes']:
            raise ValueError('product absent from BuildManifest')
        identities = []
        for identity in manifest['BuildIdentities']:
            components = {}
            for name in ('OS', 'Cryptex1,SystemOS', 'KernelCache', 'DeviceTree',
                         'StaticTrustCache', 'Cryptex1,SystemTrustCache', 'BaseSystem'):
                component = identity.get('Manifest', {}).get(name)
                if component is None:
                    continue
                path = component.get('Info', {}).get('Path')
                item = archive.getinfo(path) if path else None
                digest = component.get('Digest')
                components[name] = {
                    'path': path, 'apple_digest_hex': digest.hex() if digest else None,
                    'size': item.file_size if item else None,
                    'compressed_size': item.compress_size if item else None,
                    'zip_method': item.compress_type if item else None,
                }
            identities.append({
                'device_class': identity.get('Info', {}).get('DeviceClass'),
                'variant': identity.get('Info', {}).get('Variant'),
                'restore_behavior': identity.get('Info', {}).get('RestoreBehavior'),
                'chip_id': identity.get('ApChipID'), 'board_id': identity.get('ApBoardID'),
                'components': components,
            })
        report = {'profile': str(profile_path.relative_to(ROOT)), 'url': spec['url'],
                  'version': manifest['ProductVersion'], 'build': manifest['ProductBuildVersion'],
                  'manifest_sha256': hashlib.sha256(raw).hexdigest(),
                  'whole_ipsw_sha256_verified': False, 'downloaded_bytes': stream.downloaded,
                  'identities': identities}
    output.mkdir(parents=True)
    (output / 'BuildManifest.plist').write_bytes(raw)
    (output / 'identities.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'identities'}, indent=2))
    print(f'{len(identities)} identities; saved to {output.relative_to(ROOT)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default='configs/macos-23G93.json')
    parser.add_argument('--output', default='artifacts/23G93/metadata')
    args = parser.parse_args()
    inspect(local_path(args.profile), local_path(args.output))
