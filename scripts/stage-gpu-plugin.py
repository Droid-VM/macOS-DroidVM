#!/usr/bin/env python3
"""Stage Metal plugin bundles for a boot: a copy of the Data seed with the bundles in /Library/GPUBundles (the first directory IOGPU
searches for <MetalPluginName>.bundle; /Library is a link into the Data volume's .data, make-macos-systemos.sh), and a trust cache bundle with one owner module of their Mach-O CDHashes before the original modules (as UniXNU's
make-owner-trust-bundle.py).

    stage-gpu-plugin.py [--probe EXECUTABLE] [--setup-done] [--log-stream PREDICATE [--log-debug SUBSYSTEM]...] [--top SECONDS]
                        [--disable-job LABEL]... [--user NAME:PASSWORD] BUNDLE...        [MACOS_TAG=27.0.1]

--probe adds a launchd job that runs EXECUTABLE once at boot (overlay/metal/metal-probe.mm: what dyld and Metal make of the plugin).
--setup-done writes /var/db/.AppleSetupDone: loginwindow then goes to its login window instead of Language Chooser and Setup Assistant
(Language Chooser waits for bluetoothd, which the board disables, in IOBluetoothHostController's first use).
--log-stream adds a launchd job running `log show --last boot` then `log stream` with --predicate PREDICATE: the unified log's messages (os_log,
which no daemon writes to stderr) since boot on its stdout, which stderr-log=1 puts in the kernel's log. --log-debug writes
/Library/Preferences/Logging/Subsystems/SUBSYSTEM.plist (what `log config` writes) so the log keeps SUBSYSTEM's info and debug
messages from boot on.
--top adds a launchd job printing, a minute after it starts, the largest zones (zprint) and vm_stat, then `top` (the 15 busiest
processes) every SECONDS, all on its stdout, so in the kernel's log too.
--run SECONDS COMMAND adds a launchd job running COMMAND (sh -c) SECONDS after it starts, its output in the kernel's log as --top's
(e.g. `--run 330 'sample SecurityAgent 2 -file /dev/stdout'` for a hung process's stacks).
--user adds a local administrator (uid 501, staff, admin; SALTED-SHA512-PBKDF2 shadow hash) to the Data volume's directory
(/var/db/dslocal): the setup assistant that would create one is skipped. loginwindow creates its home on the first login.
--disable-job writes LABEL to launchd's overrides (/var/db/com.apple.xpc.launchd/disabled.plist): a system daemon that only spins on
this board (audiomxd retries the Bluetooth audio service of a controller the board does not have about eight times a second, apsd
throws at start and is relaunched every ten seconds, each crash report taking a ReportCrashService past its 120 MB limit).

Output: out/metal/stage/{scratch-data.img,kernel.macho.trustcache}; boot with MACOS_DATA_SEED / MACOS_TRUSTCACHE set to them
(scripts/droidvm-app.py). The Data volume is volatile (NativeRamBlock), so the seed is what the guest sees on every boot. Needs sudo
(the APFS image is mounted read-write with sources/linux-apfs-rw/apfs.ko)."""
import argparse
import hashlib
import os
import plistlib
import shlex
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
LOG_JOB = '.data/Library/LaunchDaemons/org.droidvm.log-stream.plist'
LOG_PREFS = '.data/Library/Preferences/Logging/Subsystems'   # only --log-debug writes there
TOP_JOB = '.data/Library/LaunchDaemons/org.droidvm.top.plist'
RUN_JOB = '.data/Library/LaunchDaemons/org.droidvm.run.{}.plist'
SETUP_DONE = 'db/.AppleSetupDone'                      # the Data volume is /private/var
LAUNCHD_DISABLED = 'db/com.apple.xpc.launchd/disabled.plist'
DSLOCAL = 'db/dslocal/nodes/Default'


def add_user(dslocal, name, password, uid=501):
    """A local administrator as System Settings writes one: the user record and its admin and staff memberships."""
    def write(path, record):
        subprocess.run(['sudo', 'tee', str(path)], input=plistlib.dumps(record, fmt=plistlib.FMT_BINARY), stdout=subprocess.DEVNULL,
                       check=True)
        subprocess.run(['sudo', 'chown', '0:0', str(path)], check=True)
        subprocess.run(['sudo', 'chmod', '600', str(path)], check=True)

    salt, iterations = os.urandom(32), 50000
    entropy = hashlib.pbkdf2_hmac('sha512', password.encode(), salt, iterations, 128)
    shadow = plistlib.dumps({'SALTED-SHA512-PBKDF2': {'entropy': entropy, 'iterations': iterations, 'salt': salt}}, fmt=plistlib.FMT_BINARY)
    guid = str(uuid.uuid4()).upper()
    write(dslocal / 'users' / (name + '.plist'), {
        'name': [name], 'realname': [name], 'uid': [str(uid)], 'gid': ['20'], 'home': ['/Users/' + name], 'shell': ['/bin/zsh'],
        'generateduid': [guid], 'passwd': ['********'], 'authentication_authority': [';ShadowHash;HASHLIST:<SALTED-SHA512-PBKDF2>'],
        'ShadowHashData': [shadow], '_writers_passwd': [name], '_writers_realname': [name], '_writers_hint': [name]})
    for group in ('admin', 'staff'):
        path = dslocal / 'groups' / (group + '.plist')
        record = plistlib.loads(subprocess.run(['sudo', 'cat', str(path)], capture_output=True, check=True).stdout)
        record['users'] = [u for u in record.get('users', []) if u != name] + [name]
        record['groupmembers'] = [g for g in record.get('groupmembers', []) if g != guid] + [guid]
        write(path, record)


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
    parser.add_argument('--log-stream', metavar='PREDICATE')
    parser.add_argument('--log-debug', metavar='SUBSYSTEM', action='append', default=[])
    parser.add_argument('--top', metavar='SECONDS', type=int)
    parser.add_argument('--run', metavar=('SECONDS', 'COMMAND'), nargs=2, action='append', default=[])
    parser.add_argument('--disable-job', metavar='LABEL', action='append', default=[])
    parser.add_argument('--user', metavar='NAME:PASSWORD')
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
                log_job = mount / LOG_JOB
                subprocess.run(['sudo', 'rm', '-f', str(log_job)], check=True)
                if args.log_stream:
                    subprocess.run(['sudo', 'mkdir', '-p', str(log_job.parent)], check=True)
                    plist = plistlib.dumps({'Label': 'org.droidvm.log-stream', 'RunAtLoad': True,
                                            'ProgramArguments': ['/bin/sh', '-c', 'log show --last boot --info --debug --style compact --predicate {0}; '
                                                'exec log stream --level debug --style compact --predicate {0}'.format(shlex.quote(args.log_stream))]},
                                           fmt=plistlib.FMT_XML)
                    subprocess.run(['sudo', 'tee', str(log_job)], input=plist, stdout=subprocess.DEVNULL, check=True)
                    subprocess.run(['sudo', 'chown', '0:0', str(log_job)], check=True)
                    subprocess.run(['sudo', 'chmod', '644', str(log_job)], check=True)
                top_job = mount / TOP_JOB
                subprocess.run(['sudo', 'rm', '-f', str(top_job)], check=True)
                if args.top:
                    subprocess.run(['sudo', 'mkdir', '-p', str(top_job.parent)], check=True)
                    plist = plistlib.dumps({'Label': 'org.droidvm.top', 'RunAtLoad': True,
                                            'ProgramArguments': ['/bin/sh', '-c', 'sleep 60; zprint -s -t | head -40; vm_stat; exec top -l 0 -s {} '
                                                                 '-o cpu -n 15 -stats pid,command,cpu,time,threads,state'.format(args.top)]},
                                           fmt=plistlib.FMT_XML)
                    subprocess.run(['sudo', 'tee', str(top_job)], input=plist, stdout=subprocess.DEVNULL, check=True)
                    subprocess.run(['sudo', 'chown', '0:0', str(top_job)], check=True)
                    subprocess.run(['sudo', 'chmod', '644', str(top_job)], check=True)
                subprocess.run(['sudo', 'sh', '-c', 'rm -f ' + str(mount / RUN_JOB.format('*'))], check=True)
                for index, (seconds, command) in enumerate(args.run):
                    run_job = mount / RUN_JOB.format(index)
                    subprocess.run(['sudo', 'mkdir', '-p', str(run_job.parent)], check=True)
                    plist = plistlib.dumps({'Label': f'org.droidvm.run.{index}', 'RunAtLoad': True,
                                            'ProgramArguments': ['/bin/sh', '-c', f'sleep {int(seconds)}; {command}']}, fmt=plistlib.FMT_XML)
                    subprocess.run(['sudo', 'tee', str(run_job)], input=plist, stdout=subprocess.DEVNULL, check=True)
                    subprocess.run(['sudo', 'chown', '0:0', str(run_job)], check=True)
                    subprocess.run(['sudo', 'chmod', '644', str(run_job)], check=True)
                disabled = mount / LAUNCHD_DISABLED   # the seed's own overrides are kept (each run starts from the artifact seed)
                if args.disable_job:
                    subprocess.run(['sudo', 'mkdir', '-p', str(disabled.parent)], check=True)
                    seed = subprocess.run(['sudo', 'cat', str(disabled)], capture_output=True).stdout
                    plist = plistlib.dumps({**(plistlib.loads(seed) if seed else {}), **{label: True for label in args.disable_job}},
                                           fmt=plistlib.FMT_XML)
                    subprocess.run(['sudo', 'tee', str(disabled)], input=plist, stdout=subprocess.DEVNULL, check=True)
                    subprocess.run(['sudo', 'chown', '0:0', str(disabled)], check=True)
                    subprocess.run(['sudo', 'chmod', '644', str(disabled)], check=True)
                log_prefs = mount / LOG_PREFS
                subprocess.run(['sudo', 'rm', '-rf', str(log_prefs)], check=True)
                if args.log_debug:
                    subprocess.run(['sudo', 'mkdir', '-p', str(log_prefs)], check=True)
                    prefs = plistlib.dumps({'DEFAULT-OPTIONS': {'Level': {'Enable': 'Debug', 'Persist': 'Debug'}}}, fmt=plistlib.FMT_XML)
                    for sub in args.log_debug:
                        path = log_prefs / (sub + '.plist')
                        subprocess.run(['sudo', 'tee', str(path)], input=prefs, stdout=subprocess.DEVNULL, check=True)
                        subprocess.run(['sudo', 'chmod', '644', str(path)], check=True)
                    subprocess.run(['sudo', 'chown', '-R', '0:0', str(log_prefs)], check=True)
                if args.user:
                    add_user(mount / DSLOCAL, *args.user.split(':', 1))
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
