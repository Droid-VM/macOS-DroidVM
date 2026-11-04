#!/usr/bin/env python3
"""Bundle the unchanged static (OS) and System (Cryptex1,SystemOS) trust caches of the IPSW for DarwinBoot, on Linux.

  make-trust-bundle.py STATIC.trustcache SYSTEM.trustcache [EXTRA.trustcache ...] OUTPUT.bundle

Port of UniXNU scripts/build-original-system-trust.py: both inputs are the IM4P members of the IPSW (StaticTrustCache and
Cryptex1,SystemTrustCache, as `unixnu ipsw fetch` stores them). The bundle is `u32 count, u32 offsets[count], modules`,
DarwinBoot's kernel.macho.trustcache sidecar. For 21H461 the result is the pinned 7416ca4f... of UniXNU-sheng board.toml.
EXTRA: further trust caches of the IPSW, after those two (macOS 13 and later: Cryptex1,AppTrustCache, Safari's App cryptex).
"""
import hashlib
from pathlib import Path
import struct
import sys

MODULES = ('da88460e6e513438d5307e5c526f76497a74754476a24da29f239f0c90120fc2',   # static, 21H461
           'd121ba89167e03aafd00fa687c30cd8ebc4ccafd10c1408adb2ba3de12403651')   # System, 21H461
BUNDLE = '7416ca4f8377146626bb284e2133c76bee6cb4e3ee0af5d648b186235a7323a7'


def der(data, at):
    tag, size = data[at:at + 2]
    at += 2
    if size & 128:
        count = size & 127
        size = int.from_bytes(data[at:at + count], 'big')
        at += count
    if at + size > len(data):
        raise SystemExit('truncated DER')
    return tag, data[at:at + size], at + size


def payload(path):
    data = Path(path).read_bytes()
    tag, sequence, end = der(data, 0)
    fields, cursor = [], 0
    while cursor < len(sequence):
        kind, value, cursor = der(sequence, cursor)
        fields.append((kind, value))
    if tag != 0x30 or end != len(data) or [kind for kind, _ in fields][:4] != [0x16, 0x16, 0x16, 4] or fields[0][1] != b'IM4P':
        raise SystemExit(f'{path}: not a trust-cache IM4P')
    module = fields[3][1]
    if struct.unpack_from('<I', module)[0] != 2 or len(module) != 24 + struct.unpack_from('<I', module, 20)[0] * 24:
        raise SystemExit(f'{path}: not a complete version-2 trust cache')
    return module


if len(sys.argv) < 4:
    raise SystemExit(__doc__)
static, system = payload(sys.argv[1]), payload(sys.argv[2])
extras = [payload(path) for path in sys.argv[3:-1]]
for module, expected in zip((static, system), MODULES):
    if hashlib.sha256(module).hexdigest() != expected:
        print(f'warning: module sha256 {hashlib.sha256(module).hexdigest()} is not the 21H461 one', file=sys.stderr)
modules = [static, system, *extras]
offsets, cursor = [], 4 + 4 * len(modules)
for module in modules:
    offsets.append(cursor)
    cursor += len(module)
bundle = struct.pack(f'<{len(modules) + 1}I', len(modules), *offsets) + b''.join(modules)
Path(sys.argv[-1]).write_bytes(bundle)
digest = hashlib.sha256(bundle).hexdigest()
print(f'{sys.argv[-1]}: {len(bundle)} bytes, sha256 {digest}' + ('' if digest == BUNDLE else ' (not the 21H461 pin)'))
