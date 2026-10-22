#!/usr/bin/env python3
"""Boot the locally built macOS 23G93 root once on the phone (crosvm-mmio on Gunyah) and keep the evidence.

Adapted from ios tools/run-droidvm.py (ios commit 9a1e72d). Disks, virtio-mmio in this order: OS (ro), SystemOS (ro), Data store (rw,
sparse). The boot disk is assembled here from the kernel, trust cache bundle, Data seed, UniXNU.efi and DarwinBoot.efi; its ADT is
generated from the FDT this exact VM configuration produces (crosvm --dump-device-tree-blob).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True
import phone_pool  # noqa: E402

APP = '/data/data/cn.classfun.droidvm/usr'
CROSVM = APP + '/bin/crosvm-mmio'
CACHE = '/data/local/tmp/macos-disk-cache'
STORE = '/data/local/tmp/droidvm/macos-data-store.img'
STORE_GIB = 16
OS_UUID = '63E8D68F-1310-4609-8FD8-CA9501AAFAD4'
BOARD = ROOT / 'sources/UniXNU-droidvm/board.toml'
ADT_TOOL = ROOT / 'sources/UniXNU-droidvm/scripts/make-droidvm-adt.py'
KERNEL = ROOT / 'out/linux/reference/droidvm/kernel/kernel.macho'
INPUTS = ROOT / 'artifacts/boot-inputs'
GPU_ARGS = ('droidvm-gpu', 'sheng-gpu-addon')     # no GPU device in this VM: those arguments would wait for a node
PAYLOAD_MIB = 384                                  # the macOS kernel carries 143 MB of block hashes


def sh(adb, command, timeout=60, check=True):
    return subprocess.run(adb + ['shell', command], capture_output=True, text=True, timeout=timeout, check=check).stdout


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        while block := stream.read(1 << 24):
            digest.update(block)
    return digest.hexdigest()


def push_cached(adb, source):
    """Push a large read-only image once; the device name carries the first 16 hex digits of its sha256."""
    size = source.stat().st_size
    remote = f'{CACHE}/{source.name}-{size}-{sha256(source)[:16]}.img'
    if sh(adb, f'stat -c %s {remote} 2>/dev/null', check=False).strip() != str(size):
        sh(adb, f'mkdir -p {CACHE}')
        print(f'pushing {source} -> {remote}', flush=True)
        subprocess.run(adb + ['push', str(source), remote + '.part'], check=True, timeout=14400)
        sh(adb, f'mv {remote}.part {remote}')
    return remote


def ensure_store(adb):
    if sh(adb, f'test -e {STORE} && echo yes', check=False).strip() == 'yes':
        return
    label = 'DroidVMDataStore\\001\\000\\000\\000'
    sh(adb, f'mkdir -p {Path(STORE).parent} && truncate -s {STORE_GIB}G {STORE} && '
            f'printf "{label}" | dd of={STORE} bs=4096 conv=notrunc,sync count=1 2>/dev/null')


def vm_command(os_img, systemos_img, mem_mb):
    return [CROSVM, 'run', '--hypervisor', 'gunyah', '--mem', str(mem_mb), '--cpus', '1',
            '--protected-vm-pseudo-unprotected', '--no-balloon', '--disable-sandbox',
            '--hugepages', '--prepare-lend-mthp-mode', 'single',
            '--simplefb', 'width=1280,height=800,format=a8r8g8b8',
            '--serial', 'type=file,hardware=serial,num=1,path=serial.log',
            '--dump-device-tree-blob', 'generated.dtb',
            '--block', 'boot.img,lock=false',
            '--virtio-mmio-block', f'{os_img},ro=true,lock=false',
            '--virtio-mmio-block', f'{systemos_img},ro=true,lock=false',
            '--virtio-mmio-block', f'{STORE},lock=false',
            APP + '/share/droidvm/edk2-gunyah.fd']


def kernel_args(extra):
    board = tomllib.loads(BOARD.read_text())
    arguments = [a for a in board['payload']['kernel_args'] if not a.startswith(GPU_ARGS)]
    names = {a.split('=', 1)[0] for a in extra}
    arguments = [a for a in arguments if a.split('=', 1)[0] not in names] + extra
    line = ' '.join(arguments)
    if len(line) > 1000:
        raise SystemExit(f'kernel command line is {len(line)} bytes; the limit is 1000')
    return line


def build_boot_disk(local, trust, data, adt, line):
    stage = local / 'stage'
    payloads = stage / 'EFI/UniXNU/Payloads'
    payloads.mkdir(parents=True)
    (stage / 'EFI/BOOT').mkdir(parents=True)
    shutil.copyfile(INPUTS / 'UniXNU.efi', stage / 'EFI/BOOT/BOOTAA64.EFI')
    shutil.copyfile(INPUTS / 'DarwinBoot.efi', payloads / 'DarwinBoot.efi')
    shutil.copyfile(KERNEL, payloads / 'kernel.macho')
    shutil.copyfile(trust, payloads / 'kernel.macho.trustcache')
    shutil.copyfile(data, payloads / 'scratch-data.img')
    shutil.copyfile(adt, payloads / 'kernel.macho.adt')
    (stage / 'EFI/UniXNU/unixnu.toml').write_text(
        'version = 1\n[boot]\ntimeout = 3\ndefault = "xnu"\n[kits]\nautoload = false\n[[driver]]\npath = "Payloads/DarwinBoot.efi"\n'
        '[[entry]]\nid = "xnu"\ntitle = "DroidVM: macOS 14.6.1 (23G93) on the DroidVM kernel"\ntype = "xnu"\n'
        'path = "Payloads/kernel.macho"\ninitrd = "Payloads/scratch-data.img"\n' f'args = "{line}"\n')
    image = local / 'boot.img'
    env = dict(os.environ, MTOOLS_SKIP_CHECK='1', TZ='UTC')
    subprocess.run(['mformat', '-C', '-F', '-T', str(PAYLOAD_MIB * 2048), '-v', 'MACOSESP', '-i', str(image), '::'],
                   check=True, env=env, capture_output=True)
    for entry in sorted(stage.iterdir()):
        subprocess.run(['mcopy', '-i', str(image), '-s', '-Q', '-m', str(entry), '::/'], check=True, env=env, capture_output=True)
    shutil.rmtree(stage)
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', help='adb serial (default: the only attached device)')
    parser.add_argument('--mem-mb', type=int, default=3072, help='guest RAM; the host hugepage pool of this phone backs about 3.5 GiB')
    parser.add_argument('--seconds', type=int, default=240)
    parser.add_argument('--label', default='macos')
    parser.add_argument('--keep', action='store_true', help='leave the VM running')
    parser.add_argument('--kernel-arg', action='append', default=[], help='extra kernel argument NAME[=VALUE]')
    parser.add_argument('--unique-chip-id', default='47554e5941480001')
    args = parser.parse_args()
    mem_mb = args.mem_mb
    dram_size = hex(mem_mb * 1024 * 1024 - 0xA00000)     # the firmware window below the shim's RAM base
    adb = ['adb'] + (['-s', args.serial] if args.serial else [])
    subprocess.run(adb + ['get-state'], check=True, timeout=15)
    stamp = datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')
    local = ROOT / 'research/runs' / f'{stamp}-{args.label}'
    local.mkdir(parents=True)
    remote = f'/data/local/tmp/macos-{stamp}-{args.label}'
    artifacts = ROOT / 'artifacts/23G93'
    trust = artifacts / 'boot/kernel.macho.trustcache'
    data = artifacts / 'data-seed/scratch-data.img'
    for path in (KERNEL, trust, data, INPUTS / 'UniXNU.efi', INPUTS / 'DarwinBoot.efi'):
        if not path.is_file():
            raise SystemExit(f'missing {path}')
    phone_pool.prepare_host_pool(adb, mem_mb, mem_mb + 128, local / 'host-pool-before.json')
    os_img = push_cached(adb, artifacts / 'os.raw')
    sys_img = push_cached(adb, artifacts / 'systemos.img')
    ensure_store(adb)
    sh(adb, f'mkdir -p {remote}')
    run_env = f'LD_LIBRARY_PATH={APP}/lib'
    line = kernel_args(args.kernel_arg)
    # Pass 1: let crosvm describe this VM (FDT) with a placeholder boot disk, then stop it.
    placeholder = local / 'placeholder.img'
    subprocess.run(['truncate', '-s', '64M', str(placeholder)], check=True)
    subprocess.run(adb + ['push', str(placeholder), remote + '/boot.img'], check=True, timeout=300)
    vm = vm_command(os_img, sys_img, mem_mb)
    sh(adb, f'cd {remote} && (env {run_env} {shlex.join(vm)} < /dev/null > crosvm-pass1.log 2>&1 &) ; sleep 12; pkill -x crosvm-mmio ; sleep 2; ls -la generated.dtb')
    subprocess.run(adb + ['pull', remote + '/generated.dtb', str(local / 'generated.dtb')], check=True, timeout=30)
    sh(adb, 'sleep 5')
    adt = local / 'kernel.macho.adt'
    subprocess.run(['python3', str(ADT_TOOL), '--fdt', str(local / 'generated.dtb'), '--dram-size', dram_size,
                    '--dram-base', '0x80600000', '--owned-memory-size', '0x20000000', '--cpu-regs', '0',
                    '--root-match-volume-uuid', OS_UUID, '--packed-data-ramdisk',
                    '--ipad-identity', '--unique-chip-id', args.unique_chip_id, '--chip-id', '8011',
                    '--trust-cache', '--data-ramdisk', '--data-store-mmio', '0x0a002000', '--reclaim-memory',
                    '--output', str(adt)], check=True)
    disk = build_boot_disk(local, trust, data, adt, line)
    subprocess.run(adb + ['push', str(disk), remote + '/boot.img'], check=True, timeout=600)
    phone_pool.prepare_host_pool(adb, mem_mb, mem_mb + 128, local / 'host-pool-run.json')
    (local / 'command.txt').write_text(shlex.join(vm) + '\n')
    (local / 'inputs.json').write_text(json.dumps({
        'kernel_sha256': sha256(KERNEL), 'trust_sha256': sha256(trust), 'data_seed_sha256': sha256(data),
        'os_sha256': sha256(artifacts / 'os.raw'), 'systemos_sha256': sha256(artifacts / 'systemos.img'),
        'boot_disk_sha256': sha256(disk), 'kernel_args': line, 'os_volume_uuid': OS_UUID,
        'unixnu_efi_sha256': sha256(INPUTS / 'UniXNU.efi'), 'darwinboot_efi_sha256': sha256(INPUTS / 'DarwinBoot.efi')}, indent=2) + '\n')
    sh(adb, f'cd {remote} && rm -f serial.log && (nohup env {run_env} {shlex.join(vm)} < /dev/null > crosvm.log 2>&1 &)')
    print(f'VM started; evidence {local}; remote {remote}', flush=True)
    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline:
        time.sleep(15)
        if not sh(adb, 'pidof crosvm-mmio', check=False).strip():
            print('crosvm exited', flush=True)
            break
    for name in ('serial.log', 'crosvm.log'):
        subprocess.run(adb + ['pull', f'{remote}/{name}', str(local / name)], timeout=60)
    if not args.keep:
        sh(adb, 'pkill -x crosvm-mmio', check=False)
    print(f'Evidence: {local}')


if __name__ == '__main__':
    main()
