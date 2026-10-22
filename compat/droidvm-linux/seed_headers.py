#!/usr/bin/env python3
"""Pre-place the DriverKit / TrustCache headers prepare-xnu-source.py restores, using authenticated `gh api` downloads.

Each file is verified against the git blob sha of the pinned GitHub listing; prepare-xnu-source.py then skips existing files.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

tree = Path(sys.argv[1])
work = tree / '.cache/xnu-work'
sources = tree / '.cache/sources'
TAG, TRUST_TAG = 'xnu-10063.121.3', 'xnu-8796.101.5'
jobs = [(sources / 'xnu-driverkit-10063.121.3.json', work / 'iokit/DriverKit', 'iokit/DriverKit', TAG, False),
        (sources / 'xnu-driverkit-crypto-10063.121.3.json', work / 'iokit/DriverKit/crypto', 'iokit/DriverKit/crypto', TAG, False),
        (sources / 'xnu-trustcache-8796.101.5.json', work / 'EXTERNAL_HEADERS/TrustCache', 'EXTERNAL_HEADERS/TrustCache', TRUST_TAG, False)]
done = 0
for listing, destination, path, tag, _ in jobs:
    for entry in json.loads(listing.read_text()):
        if entry['type'] != 'file' or not entry['name'].endswith('.h'):
            continue
        target = destination / entry['name']
        if target.exists():
            continue
        for attempt in range(6):
            result = subprocess.run(['gh', 'api', '-H', 'Accept: application/vnd.github.raw',
                                     f'repos/apple-oss-distributions/xnu/contents/{path}/{entry["name"]}?ref={tag}'],
                                    capture_output=True)
            data = result.stdout
            if result.returncode == 0 and hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == entry['sha']:
                break
            time.sleep(2 * (attempt + 1))
        else:
            raise SystemExit(f'cannot fetch {path}/{entry["name"]}')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        done += 1
print(f'seeded {done} headers')
