#!/usr/bin/env python3
"""Stage Metal plugin bundles for a boot: a copy of the Data seed with the bundles in /Library/GPUBundles (the first directory IOGPU
searches for <MetalPluginName>.bundle; /Library is a link into the Data volume's .data, make-macos-systemos.sh), and a trust cache bundle with one owner module of their Mach-O CDHashes before the original modules (as UniXNU's
make-owner-trust-bundle.py).

    stage-gpu-plugin.py [--probe EXECUTABLE] [--setup-done] BUNDLE...        [MACOS_TAG=27.0.1]

--probe adds a launchd job that runs EXECUTABLE once at boot (overlay/metal/metal-probe.mm: what dyld and Metal make of the plugin).
--setup-done writes /var/db/.AppleSetupDone: loginwindow then goes to its login window instead of Language Chooser and Setup Assistant
(Language Chooser waits for bluetoothd, which the board disables, in IOBluetoothHostController's first use).

Output: out/metal/stage/{scratch-data.img,kernel.macho.trustcache}; boot with MACOS_DATA_SEED / MACOS_TRUSTCACHE set to them
(scripts/droidvm-app.py). The Data volume is volatile (NativeRamBlock), so the seed is what the guest sees on every boot. Needs sudo
(the APFS image is mounted read-write with sources/linux-apfs-rw/apfs.ko)."""
import argparse
import hashlib
import os
import plistlib
import struct
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sources/UniXNU/drivers/DarwinBoot/Test'))
import packed_ramdisk  # noqa: E402

TAG = os.environ.get('MACOS_TAG', '27.0.1')
ARTIFACTS = ROOT / f'artifacts/{TAG}'
OUT = ROOT / 'out/metal/stage'
LC_CODE_SIGNATURE = 0x1d
GPU_BUNDLES = '.data/Library/GPUBundles'
PROBE_DIR = '.data/usr/local/libexec'                  # /usr/local is a link into .data as well
PROBE_JOB = '.data/Library/LaunchDaemons/org.droidvm.metal-probe.plist'
SETUP_DONE = 'db/.AppleSetupDone'                      # the Data volume is /private/var


def cdhash(path):
    """The CDHash of a thin Mach-O: SHA-256 (truncated to 20 bytes) of its SHA-256 CodeDirectory, or None when it is not Mach-O."""
    data = path.read_bytes()
    if data[:4] != b'\xcf\xfa\xed\xfe':
        return None
    count, = struct.unpack_from('<I', data, 16)
    at = 32
    for _ in range(count):
        command, size = struct.unpack_from('<II', data, at)
        if command == LC_CODE_SIGNATURE:
            offset, length = struct.unpack_from('<II', data, at + 8)
            blob = data[offset:offset + length]
            magic, _, blobs = struct.unpack_from('>III', blob, 0)
            assert magic == 0xfade0cc0, f'{path}: no embedded signature'
            for index in range(blobs):
                kind, start = struct.unpack_from('>II', blob, 12 + 8 * index)
                cd_magic, cd_length = struct.unpack_from('>II', blob, start)
                hash_type = blob[start + 37]
                if cd_magic == 0xfade0c02 and hash_type == 2:
                    return hashlib.sha256(blob[start:start + cd_length]).digest()[:20]
            raise SystemExit(f'{path}: no SHA-256 CodeDirectory')
        at += size
    raise SystemExit(f'{path}: not signed')


def trust_bundle(hashes, original):
    count, = struct.unpack_from('<I', original)
    starts = struct.unpack_from(f'<{count}I', original, 4)
    originals = [original[start:end] for start, end in zip(starts, list(starts[1:]) + [len(original)])]
    hashes = sorted(set(hashes))   # the loader and the kernel binary-search a module's hashes
    identifier = uuid.uuid5(uuid.NAMESPACE_URL, 'droidvm-macos-gpu:' + ''.join(h.hex() for h in hashes))
    own = struct.pack('<I16sI', 2, identifier.bytes, len(hashes)) + b''.join(h + bytes([2, 0, 0, 0]) for h in hashes)
    modules = [own, *originals]
    header = 4 + 4 * len(modules)
    offsets, cursor = [], header
    for module in modules:
        offsets.append(cursor)
        cursor += len(module)
    return struct.pack(f'<{len(modules) + 1}I', len(modules), *offsets) + b''.join(modules)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--probe', type=Path)
    parser.add_argument('--setup-done', action='store_true')
    parser.add_argument('bundles', nargs='+', type=Path)
    args = parser.parse_args()
    bundles = [b.resolve() for b in args.bundles]
    if any(not (b / 'Contents/Info.plist').is_file() for b in bundles):
        raise SystemExit('a bundle needs Contents/Info.plist (the macOS layout)')
    hashes = [h for b in bundles for f in sorted(b.rglob('*')) if f.is_file() and (h := cdhash(f))]
    if args.probe:
        hashes.append(cdhash(args.probe))
    OUT.mkdir(parents=True, exist_ok=True)
    trust = OUT / 'kernel.macho.trustcache'
    trust.write_bytes(trust_bundle(hashes, (ARTIFACTS / 'boot/kernel.macho.trustcache').read_bytes()))
    print(f'{trust}: {len(hashes)} CDHashes ' + ' '.join(h.hex() for h in hashes))

    logical, extents = packed_ramdisk.regions((ARTIFACTS / 'data-seed/scratch-data.img').read_bytes())
    with tempfile.TemporaryDirectory(prefix='data-seed-', dir=str(OUT)) as scratch:
        raw = Path(scratch) / 'seed.raw'
        with raw.open('wb') as handle:
            handle.truncate(logical)
            for offset, data in extents:
                handle.seek(offset)
                handle.write(data)
        mount = Path(scratch) / 'mount'
        mount.mkdir()
        if subprocess.run(['grep', '-q', '^apfs ', '/proc/modules']).returncode:
            subprocess.run(['sudo', 'insmod', str(ROOT / 'sources/linux-apfs-rw/apfs.ko')], check=True)
        loop = subprocess.check_output(['sudo', 'losetup', '--find', '--show', str(raw)], text=True).strip()
        try:
            subprocess.run(['sudo', 'mount', '-t', 'apfs', '-o', 'readwrite', loop, str(mount)], check=True)
            try:
                target = mount / GPU_BUNDLES
                subprocess.run(['sudo', 'mkdir', '-p', str(target)], check=True)
                for bundle in bundles:
                    subprocess.run(['sudo', 'rm', '-rf', str(target / bundle.name)], check=True)
                    subprocess.run(['sudo', 'cp', '-R', str(bundle), str(target)], check=True)
                subprocess.run(['sudo', 'chown', '-R', '0:0', str(target)], check=True)
                subprocess.run(['sudo', 'chmod', '-R', 'go-w,a+rX', str(target)], check=True)
                if args.probe:
                    executable = mount / PROBE_DIR / args.probe.name
                    job = mount / PROBE_JOB
                    subprocess.run(['sudo', 'mkdir', '-p', str(executable.parent), str(job.parent)], check=True)
                    subprocess.run(['sudo', 'install', '-o', '0', '-g', '0', '-m', '755', str(args.probe), str(executable)], check=True)
                    plist = plistlib.dumps({'Label': 'org.droidvm.metal-probe', 'ProgramArguments': ['/usr/local/libexec/' + args.probe.name],
                                            'RunAtLoad': True}, fmt=plistlib.FMT_XML)
                    subprocess.run(['sudo', 'tee', str(job)], input=plist, stdout=subprocess.DEVNULL, check=True)
                    subprocess.run(['sudo', 'chown', '0:0', str(job)], check=True)
                    subprocess.run(['sudo', 'chmod', '644', str(job)], check=True)
                if args.setup_done:
                    marker = mount / SETUP_DONE
                    subprocess.run(['sudo', 'mkdir', '-p', str(marker.parent)], check=True)
                    subprocess.run(['sudo', 'install', '-o', '0', '-g', '0', '-m', '444', '/dev/null', str(marker)], check=True)
                subprocess.run(['sync'], check=True)
            finally:
                subprocess.run(['sudo', 'umount', str(mount)], check=True)
        finally:
            subprocess.run(['sudo', 'losetup', '-d', loop], check=True)
        seed = OUT / 'scratch-data.img'
        seed.unlink(missing_ok=True)
        packed_ramdisk.pack(raw, seed)
    print(f'{seed}: ' + ' '.join(f'/Library/GPUBundles/{b.name}' for b in bundles))


if __name__ == '__main__':
    main()
