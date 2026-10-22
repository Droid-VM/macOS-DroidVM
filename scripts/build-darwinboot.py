#!/usr/bin/env python3
"""Build DarwinBoot.efi from the locked UniXNU DarwinBoot with this project's patch, using the local EDK II and GCC.

The patch (patches/darwinboot-reclaim-memory-and-256mb-kernel.patch) ports ios droidvm-linux/patches/darwinboot-reclaim-memory.patch to
the locked DarwinBoot (the /chosen/darwinboot-memory-limit consumer) and raises the kernel read limit from 128 MiB to 256 MiB: the
macOS kernel embeds 143 MB of block hashes. Output: artifacts/boot-inputs/DarwinBoot.efi and a provenance entry.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'out/darwinboot'
EDK2 = ROOT / 'sources/edk2'
PATCH = ROOT / 'patches/darwinboot-reclaim-memory-and-256mb-kernel.patch'


def main():
    for source in (EDK2 / 'BaseTools/Source/C/bin/GenFw', ROOT / 'sources/GunyahBootPkg/GunyahBoot.dsc'):
        if not source.exists():
            raise SystemExit(f'missing {source}')
    driver = WORK / 'DarwinBoot'
    shutil.rmtree(driver, ignore_errors=True)
    shutil.copytree(ROOT / 'sources/UniXNU/drivers/DarwinBoot', driver, ignore=shutil.ignore_patterns('.git'))
    subprocess.run(['patch', '-p1', '--no-backup-if-mismatch', '-i', str(PATCH)], cwd=driver, check=True)
    workspace = WORK / 'ws'
    shutil.rmtree(workspace, ignore_errors=True)
    workspace.mkdir(parents=True)
    env = dict(os.environ, WORKSPACE=str(workspace), EDK_TOOLS_PATH=str(EDK2 / 'BaseTools'), PYTHON_COMMAND='python3',
               PACKAGES_PATH=':'.join([str(ROOT / 'sources'), str(EDK2), str(ROOT / 'sources/UniXNU/package'), str(driver)]),
               GCC_AARCH64_PREFIX='aarch64-linux-gnu-')
    command = ('set +u; source "$1/edksetup.sh" BaseTools; set -u; '
               'build -p GunyahBootPkg/GunyahBoot.dsc -m DarwinBootPkg/Driver/DarwinBoot.inf -a AARCH64 -b DEBUG -t GCC -n 4')
    subprocess.run(['bash', '-c', command, 'bash', str(EDK2)], cwd=ROOT, env=env, check=True)
    efi = next(workspace.rglob('DarwinBootPkg/Driver/DarwinBoot/OUTPUT/DarwinBoot.efi'))
    destination = ROOT / 'artifacts/boot-inputs/DarwinBoot.efi'
    shutil.copyfile(efi, destination)
    provenance = ROOT / 'artifacts/boot-inputs/provenance.json'
    record = json.loads(provenance.read_text())
    record['DarwinBoot.efi'] = {
        'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'bytes': destination.stat().st_size,
        'source': 'scripts/build-darwinboot.py: sources/UniXNU/drivers/DarwinBoot + ' + PATCH.name +
                  ', edk2 ' + subprocess.check_output(['git', '-C', str(EDK2), 'rev-parse', 'HEAD'], text=True).strip()}
    provenance.write_text(json.dumps(record, indent=2) + '\n')
    print(destination, record['DarwinBoot.efi']['sha256'])


if __name__ == '__main__':
    main()
