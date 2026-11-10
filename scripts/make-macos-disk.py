#!/usr/bin/env python3
"""Make a new install of macOS for the k27 kernel, in the single-volume layout (docs/k27-real-disk-layout-plan.md P6): one APFS
container holding the IPSW's System volume as the root, in a volume group with a new Data volume, and Preboot, VM, Update, Hardware
and xART volumes, the way an installed Mac's internal container is laid out.

    make-macos-disk.py [--size-gib 48] [--data-uuid UUID] OUTPUT_DIR        [MACOS_TAG=27.2]

Inputs (artifacts/TAG): os.raw (the OS member, a bare APFS container whose only volume is the System volume), dec/*.dmg (Cryptex1,SystemOS
decrypted: macos-fetch-member.py, then ipsw fw aea), app-cryptex/*.dmg (Cryptex1,AppOS).

What goes where:
- System volume (os.raw's, firmlinks and mount points as Apple made them): the SystemOS cryptex's content merged in. The kernel
  starts dyld without ignition (kern_exec.c native_owner_cache_prepare), so nothing grafts the cryptex from Preboot: launchd and the
  mount phases need the shared cache on the root before Preboot is mounted. /sbin/fsck remains Apple's original binary.
- Preboot: Cryptexes/OS -> / (the cryptex is on the root), Cryptexes/App (the AppOS cryptex, where /System/Cryptexes/App leads), the
  state directory cryptexd opens. The same under the root's own /System/Volumes/Preboot, which is what shows until Preboot is mounted.
- Data: /System/Library/Templates/Data of the System volume, as macOS's installer fills it. Users, the Metal plugin and the rest are
  stage-gpu-plugin.py --disk's.

The container is built in its final place, the page window of a Data store (scripts/data_store.py): the whole disk is the store's
overlay over an empty seed of the same size, every page with data present. Output in OUTPUT_DIR: data-store.img (the phone's
data-store.img), scratch-data.img (the seed, MACOS_DATA_SEED), disk.json (the volumes' UUIDs: the root's is MACOS_ROOT_UUID). Needs
sudo (losetup, the Linux apfs-rw driver).
"""
import argparse
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'sources/UniXNU/drivers/DarwinBoot/Test'))
import packed_ramdisk  # noqa: E402
from data_store import PAGE, Store  # noqa: E402

spec = importlib.util.spec_from_file_location('apfs_add_volumes', ROOT / 'scripts/apfs-add-volumes.py')
volumes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(volumes)
grow = volumes.grow
TAG = os.environ.get('MACOS_TAG', '27.2')
ARTIFACTS = ROOT / f'artifacts/{TAG}'
APFS_KO = ROOT / 'sources/linux-apfs-rw/apfs.ko'
LABEL = b'DroidVMDataStore\x01\x00\x00\x00'   # run-macos-vm.py ensure_store
# as on the live disk (docs/k27-real-disk-layout-plan.md P5): Data in the System volume's group; Update, VM, Hardware, xART beside
OTHER_VOLUMES = [('Preboot', 'B'), ('VM', 'V'), ('Update', 'E'), ('Hardware', 'H'), ('xART', 'X')]
# the x86_64 and Rosetta caches are of no use on this board (their files land uncompressed: Linux writes no APFS compression)
CRYPTEX_EXCLUDES = ['/System/Library/dyld/dyld_shared_cache_x86_64*', '/System/Library/dyld/aot_shared_cache*']


def sudo(*command, **options):
    return subprocess.run(['sudo', *map(str, command)], check=True, **options)


def one(pattern):
    found = sorted(ARTIFACTS.glob(pattern))
    if len(found) != 1:
        raise SystemExit(f'{ARTIFACTS}/{pattern}: {len(found)} files, one wanted')
    return found[0]


def build_container(store_path, offset, logical, data_uuid):
    """os.raw into the window, the container grown to LOGICAL and the volumes added."""
    os_raw = ARTIFACTS / 'os.raw'
    if os_raw.stat().st_size > logical:
        raise SystemExit(f'{os_raw} is larger than {logical} bytes')
    subprocess.run(['dd', f'if={os_raw}', f'of={store_path}', 'bs=1M', f'seek={offset}', 'oflag=seek_bytes',
                    'conv=notrunc,sparse', 'status=none'], check=True)
    image = grow.Image(store_path, offset, logical)
    roles = volumes.role_volumes(image)
    if list(roles) != [volumes.ROLES['S']]:
        raise SystemExit(f'{os_raw}: one System volume expected, roles {[hex(r) for r in roles]}')
    specs = [('Data', volumes.ROLES['D'], False, data_uuid)] + \
            [(name, volumes.ROLES[role], False, str(uuid.uuid4()).upper()) for name, role in OTHER_VOLUMES]
    volumes.add_volumes(image, specs, logical if logical > os_raw.stat().st_size else None, roles[volumes.ROLES['S']][0])
    image.map.close()
    image.handle.close()
    return volumes.role_volumes(grow.Image(store_path, offset, logical))


def fill(loop, roles, scratch):
    """One volume of the container mounted at a time (read-write), its source read-only from another image: with the System,
    Preboot and Data volumes mounted together, the Linux apfs-rw driver crashed the host twice in the cryptex's copy (apfs_node_query
    on a freed node; memory devbox-apfs-rw-panic-make-macos-disk). The Data template is read from os.raw, not the System volume."""
    def phase(volume, source, work):
        point, source_point = scratch / 'volume', scratch / 'source'
        point.mkdir(exist_ok=True)
        source_point.mkdir(exist_ok=True)
        source_loop = subprocess.check_output(['sudo', 'losetup', '--find', '--show', '--read-only', str(source)], text=True).strip()
        mounted = []
        try:
            sudo('mount', '-t', 'apfs', '-o', 'ro', source_loop, source_point)
            mounted.append(source_point)
            sudo('mount', '-t', 'apfs', '-o', f'readwrite,vol={roles[volumes.ROLES[volume]][0]}', loop, point)
            mounted.append(point)
            work(point, source_point)
            subprocess.run(['sync'], check=True)
            print(volume, subprocess.check_output(['df', '-h', '--output=used', str(point)], text=True).split()[-1], flush=True)
        finally:
            for mount in reversed(mounted):
                sudo('umount', mount)
            sudo('losetup', '-d', source_loop)

    def system(target, cryptex):
        sudo('rsync', '-aH', '--numeric-ids', *[f'--exclude={e}' for e in CRYPTEX_EXCLUDES], f'{cryptex}/', f'{target}/')
        preboot_dirs(target / 'System/Volumes/Preboot')

    def preboot_dirs(base):
        sudo('mkdir', '-p', base / 'Cryptexes', base / 'com.apple.security.cryptexd/Cryptexes')
        sudo('ln', '-sfn', '/', base / 'Cryptexes/OS')

    def preboot(target, cryptex):
        preboot_dirs(target)
        sudo('rsync', '-aH', '--numeric-ids', f'{cryptex}/', f'{target}/Cryptexes/App/')

    def data(target, os_volume):
        sudo('rsync', '-aH', '--numeric-ids', f'{os_volume}/System/Library/Templates/Data/', f'{target}/')
        # what make-macos-data-seed.sh made of the template (directories the first boot would otherwise make itself)
        for directory in ('tmp', 'log', 'run', 'vm', 'folders', 'db/dslocal/nodes/Default'):
            sudo('mkdir', '-p', target / 'private/var' / directory)
        sudo('mkdir', '-p', target / 'private/tmp')
        sudo('chmod', '1777', target / 'private/var/tmp', target / 'private/tmp')

    phase('S', one('dec/*.dmg'), system)
    phase('B', one('app-cryptex/*.dmg'), preboot)
    phase('D', ARTIFACTS / 'os.raw', data)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--size-gib', type=int, default=48)
    parser.add_argument('--data-uuid', default=None)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    logical = args.size_gib << 30
    pages = logical // PAGE
    bitmap_blocks = (pages + 8 * PAGE - 1) // (8 * PAGE)
    offset = (2 + bitmap_blocks) * PAGE
    data_uuid = (args.data_uuid or str(uuid.uuid4())).upper()
    args.output.mkdir(parents=True, exist_ok=True)
    store_path, seed_path = args.output / 'data-store.img', args.output / 'scratch-data.img'

    # the seed: an empty disk of LOGICAL bytes (no extents), and the store's header made against it
    seed = struct.pack('<8sIIQQ', b'DBRDISK1', 1, PAGE, logical, 0)
    packed_ramdisk.regions(seed)
    digest = packed_ramdisk.logical_hash(logical, [])
    with open(store_path, 'xb') as handle:
        handle.truncate(offset + logical)
        handle.write(LABEL + bytes(PAGE - len(LABEL)))
        handle.write(grow.header(pages, digest, 1))
    roles = build_container(store_path, offset, logical, data_uuid)
    print('volumes', {volumes.ROLE_NAMES.get(r, hex(r)): v for r, v in roles.items()})

    if subprocess.run(['grep', '-q', '^apfs ', '/proc/modules']).returncode:
        sudo('insmod', APFS_KO)
    loop = subprocess.check_output(['sudo', 'losetup', '--find', '--show', '--offset', str(offset), '--sizelimit', str(logical),
                                    str(store_path)], text=True).strip()
    try:
        with tempfile.TemporaryDirectory(prefix='macos-disk-', dir=str(args.output)) as scratch:
            fill(loop, roles, Path(scratch))
    finally:
        sudo('losetup', '-d', loop)

    store = Store(store_path, writable=True)
    store.check(logical, [])
    present = store.mark_data()
    store.close()
    seed_path.write_bytes(seed)
    names = {'S': 'system', 'D': 'data', **{role: name.lower() for name, role in OTHER_VOLUMES}}
    layout = {'tag': TAG, 'bytes': logical, 'store': store_path.name, 'seed': seed_path.name, 'window_offset': offset,
              **{names[volumes.ROLE_NAMES[r]]: {'index': i, 'uuid': u} for r, (i, u) in roles.items()}}
    (args.output / 'disk.json').write_text(json.dumps(layout, indent=2) + '\n')
    print(f'{store_path}: {present} pages present ({present * PAGE >> 20} MiB); seed {seed_path}, identity {digest[:16]}')
    print(f'MACOS_ROOT_UUID={roles[volumes.ROLES["S"]][1]}')


if __name__ == '__main__':
    main()
