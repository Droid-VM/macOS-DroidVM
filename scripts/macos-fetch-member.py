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
import threading
import time
import urllib.request
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
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


CRC_POLY = 0xedb88320


def crc_multiply(a, b):
    """a * b modulo the CRC-32 polynomial (reflected), as zlib's multmodp."""
    m, p = 1 << 31, 0
    while True:
        if a & m:
            p ^= b
            if not a & (m - 1):
                return p
        m >>= 1
        b = (b >> 1) ^ CRC_POLY if b & 1 else b >> 1


def crc32_combine(crc1, crc2, length2):
    """The CRC-32 of A+B from those of A and B (zlib's crc32_combine): crc1 times x^(8 * length2), plus crc2."""
    power, square, n = 1 << 31, 1 << 30, length2 * 8   # x^0, x^1
    while n:
        if n & 1:
            power = crc_multiply(square, power)
        square = crc_multiply(square, square)
        n >>= 1
    return crc_multiply(power, crc1) ^ crc2


def parallel_fill(spec_ipsw, etag, start, size, part, jobs):
    """Fetch the chunks of a stored member concurrently into PART (preallocated); PART.chunks lists the finished chunk indices, each
    with the CRC-32 of its bytes. A contiguous prefix left by an earlier sequential run counts as finished (its CRCs unknown).
    Returns the member's CRC-32, combined from the chunks', or None when a chunk's is unknown (the sequential pass computes it)."""
    chunks = (size + CHUNK - 1) // CHUNK
    marks = part.with_name(part.name + '.chunks')
    done, crcs = set(), {}
    if marks.exists():
        for line in marks.read_text().splitlines():
            fields = line.split()
            if fields:
                done.add(int(fields[0]))
                if len(fields) > 1:
                    crcs[int(fields[0])] = int(fields[1], 16)
    elif part.exists():
        done = set(range(min(part.stat().st_size, size) // CHUNK))
    if not part.exists() or part.stat().st_size != size:
        with part.open('ab') as handle:
            handle.truncate(size)
    lock = threading.Lock()
    counter = [len(done)]

    def one(index):
        begin = index * CHUNK
        end = min(begin + CHUNK, size) - 1
        data = fetch(spec_ipsw['url'], etag, start + begin, start + end, spec_ipsw['filesize'])
        crc = zlib.crc32(data)
        os.pwrite(handle_fd, data, begin)
        with lock:
            crcs[index] = crc
            with marks.open('a') as record:
                record.write(f'{index} {crc:08x}\n')
            counter[0] += 1
            print(f'{counter[0] / chunks:6.1%}', end='\r', flush=True)

    with part.open('r+b') as handle:
        handle_fd = handle.fileno()
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            list(pool.map(one, [index for index in range(chunks) if index not in done]))
        os.fsync(handle_fd)
    marks.unlink(missing_ok=True)
    if len(crcs) != chunks:
        return None
    crc = 0
    for index in range(chunks):
        crc = crc32_combine(crc, crcs[index], min(CHUNK, size - index * CHUNK))
    return crc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component')
    parser.add_argument('--profile', default='configs/macos-23G93.json')
    parser.add_argument('--output-dir', default='artifacts/23G93')
    parser.add_argument('--jobs', type=int, default=8, help='parallel range requests for stored (not deflated) members')
    parser.add_argument('--inventory', default='artifacts/23G93/metadata/identities.json', help='identities.json of macos-inputs.py for --identity')
    parser.add_argument('--identity', help='device class of another BuildManifest identity (e.g. vma2macosap); read from the inventory of macos-inputs.py')
    args = parser.parse_args()
    profile = json.loads(inputs.local_path(args.profile).read_text())
    spec_ipsw = profile['ipsw']
    if args.identity:
        inventory = json.loads(inputs.local_path(args.inventory).read_text())
        found = [i for i in inventory['identities'] if i['device_class'] == args.identity and i['variant'] == 'macOS Customer' and i['restore_behavior'] == 'Erase']
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
    combined = None
    if stored and args.jobs > 1:
        combined = parallel_fill(spec_ipsw, etag, start, entry.compress_size, part, args.jobs)
    # An AEA member is checked by its CRC only (below), which the chunks' CRCs give without reading the 10 GB again
    unread = combined is not None and final.name.endswith('.aea')
    if unread:
        crc, written, digest = combined, entry.file_size, None
    elif part.exists() and stored:
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
        while position < entry.compress_size and not unread:
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
    matches = digest is not None and digest.hexdigest() == digest_hex
    if not matches and not final.name.endswith('.aea'):
        raise SystemExit(f'{algorithm} differs from the Apple manifest digest: {digest.hexdigest()}')
    # An AEA archive's manifest digest is not the hash of the encrypted file (observed on macOS 27: the ZIP CRC32 matched and the
    # sha384 did not); its integrity is checked by the AEA decryption and the digest of the decrypted DMG.
    part.rename(final)
    print(json.dumps({'file': str(final.relative_to(ROOT)), 'size': written, 'crc32': f'{crc:#010x}',
                      algorithm: digest.hexdigest() if digest else 'not computed (AEA)', 'matches_apple_manifest_digest': matches}, indent=2))


if __name__ == '__main__':
    main()
