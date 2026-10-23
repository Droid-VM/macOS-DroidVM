#!/usr/bin/env python3
"""Run the macOS 14.6.1 (23G93) VM from the DroidVM app: a persistent vms.json entry whose disks live in
/storage/emulated/0/DroidVM/MacOS.

  droidvm-app.py prepare [--kernel-arg NAME=VALUE ...]   push the images, register the VM, let the app's daemon boot it once
                                                         with a placeholder boot disk to dump the FDT, then build and push the
                                                         real boot disk (ADT from that FDT) and stop the VM
  droidvm-app.py boot [--kernel-arg ...]                 rebuild only the boot disk from the FDT dumped last time
                                                         (new kernel, new kernel arguments)
  droidvm-app.py register                                (re)write the vms.json entry through the daemon's config transaction
  droidvm-app.py start|stop|status

The daemon plumbing (IPC, configuration transaction, VM template) is the iOS tool's (ios/tools/droidvm-app.py, imported and
parameterised, never written to). The boot disk rides in "extra_options" as --block so no disk registry entry is needed; the OS,
SystemOS and Data disks are --virtio-mmio-block like in run-macos-vm.py.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scripts'))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ios = load(ROOT.parent / 'ios/tools/droidvm-app.py', 'ios_droidvm_app')
run = load(ROOT / 'scripts/run-macos-vm.py', 'run_macos_vm')

FOLDER = run.FOLDER
VM_NAME = 'macOS 14.6.1 (DroidVM)'
VM_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, 'macos-14.6.1.droidvm.macos'))
MEM_MB = 3072
OUT = ROOT / 'out/app'
BOOT = FOLDER + '/boot.img'
DTB = FOLDER + '/generated.dtb'
REQUIRED_ARGS = ['mac-sandbox-permissive=1', 'mac-amfi-launch-permissive=1', 'union-hide-lower=1']   # see TODO.md: without them launchd cannot get far
# Everything the iOS functions read as module state: the VM identity, the folder (also its ownership reference), the output directory.
ios.FOLDER, ios.VM_NAME, ios.VM_ID, ios.MEM_MB, ios.OUT, ios.BOOT = FOLDER, VM_NAME, VM_ID, MEM_MB, OUT, BOOT
adb, sh = ios.adb, ios.sh


def fix_owner(path):
    sh(f'chown {run.OWNER} {path} && chmod 660 {path}')


ios.fix_owner = fix_owner


def template(persistent):
    """The iOS VM definition with the macOS particulars: eight vCPUs, boot disk as --block, no GPU/input mmio devices."""
    vm = ORIGINAL_VM_CONFIG(persistent)
    vm.update({'cpu_count': 8, 'disks': [],
               'extra_options': ['--block', BOOT + ',lock=false', '--dump-device-tree-blob', DTB,
                                 '--virtio-mmio-block', FOLDER + '/os.img,ro=true,lock=false',
                                 '--virtio-mmio-block', FOLDER + '/systemos.img,ro=true,lock=false',
                                 '--virtio-mmio-block', run.STORE + ',lock=false']})
    return vm


ORIGINAL_VM_CONFIG = ios.vm_config
ios.vm_config = template


def push_images(args):
    artifacts = ROOT / 'artifacts/23G93'
    run.push_cached(['adb', '-s', ios.SERIAL], artifacts / 'os.raw', 'os.img')
    run.push_cached(['adb', '-s', ios.SERIAL], artifacts / 'systemos.img', 'systemos.img')
    run.ensure_store(['adb', '-s', ios.SERIAL])
    if sh(f'test -e {BOOT} && echo yes', check=False).strip() != 'yes':
        placeholder = OUT / 'placeholder.img'
        OUT.mkdir(parents=True, exist_ok=True)
        subprocess.run(['truncate', '-s', '64M', str(placeholder)], check=True)
        adb('push', str(placeholder), BOOT, timeout=300)
        fix_owner(BOOT)


def boot_disk(args):
    """Build the boot disk from the FDT the daemon's crosvm dumped for this very VM and push it."""
    OUT.mkdir(parents=True, exist_ok=True)
    fdt = OUT / 'generated.dtb'
    adb('pull', DTB, str(fdt), timeout=60)
    adt = OUT / 'kernel.macho.adt'
    run.make_adt(fdt, hex(MEM_MB * 1024 * 1024 - 0xA00000), '47554e5941480001', adt, cpu_regs=None)   # every vCPU the app gives the VM
    artifacts = ROOT / 'artifacts/23G93'
    line = run.kernel_args(REQUIRED_ARGS + args.kernel_arg)
    local = OUT / 'boot'
    if local.exists():
        subprocess.run(['rm', '-rf', str(local)], check=True)
    local.mkdir()
    disk = run.build_boot_disk(local, artifacts / 'boot/kernel.macho.trustcache', artifacts / 'data-seed/scratch-data.img', adt, line)
    adb('push', str(disk), BOOT, timeout=900)
    fix_owner(BOOT)
    print('boot disk pushed:', BOOT, '\nkernel args:', line)


def prepare(args):
    push_images(args)
    ios.register(args)
    ipc = ios.Ipc()
    sh(f'rm -f {DTB}')
    print('start (placeholder boot disk)', ipc.call('vm_start', vm_id=VM_ID).get('success'))
    for _ in range(60):
        time.sleep(2)
        if sh(f'test -s {DTB} && echo yes', check=False).strip() == 'yes':
            break
    else:
        raise SystemExit('the daemon did not dump the FDT')
    time.sleep(3)
    print('stop', ipc.call('vm_stop', vm_id=VM_ID).get('success'))
    boot_disk(args)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    for name in ('prepare', 'boot'):
        sub.add_parser(name).add_argument('--kernel-arg', action='append', default=[], help='extra kernel argument NAME[=VALUE]')
    for name in ('register', 'start', 'stop', 'status'):
        sub.add_parser(name)
    args = parser.parse_args()
    if args.cmd in ('status', 'stop'):
        ios.control(args)
    elif args.cmd == 'boot':
        boot_disk(args)
    elif args.cmd == 'prepare':
        prepare(args)
    else:
        {'register': ios.register, 'start': ios.start}[args.cmd](args)


if __name__ == '__main__':
    main()
