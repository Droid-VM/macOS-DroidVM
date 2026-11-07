#!/usr/bin/env python3
"""Run the macOS 14.6.1 (23G93) VM from the DroidVM app: a persistent vms.json entry whose disks live in
/storage/emulated/0/DroidVM/MacOS.

  droidvm-app.py prepare [--kernel-arg NAME=VALUE ...]   push the images, register the VM, let the app's daemon boot it once
                                                         with a placeholder boot disk to dump the FDT, then build and push the
                                                         real boot disk (ADT from that FDT) and stop the VM
  droidvm-app.py push                                    only push the OS/SystemOS images (and create the Data store)
  droidvm-app.py boot [--kernel-arg ...]                 rebuild only the boot disk from the FDT dumped last time
                                                         (new kernel, new kernel arguments)
  droidvm-app.py register                                (re)write the vms.json entry through the daemon's config transaction
  droidvm-app.py net                                     only switch the registered VM's network (MACOS_NET) and dump its new FDT,
                                                         keeping every other setting made in the app; then boot
  droidvm-app.py snd                                     only switch the registered VM's virtio-snd card (MACOS_SND) and dump its
                                                         new FDT, keeping every other setting made in the app; then boot
  droidvm-app.py media                                   only switch the registered VM's virtio-media codecs (MACOS_MEDIA) and dump
                                                         its new FDT, keeping every other setting made in the app; then boot
  droidvm-app.py store-patch                             write out/metal/stage/store-patch.{bin,txt} (stage-gpu-plugin.py --store) into
                                                         the stopped VM's Data store, the blocks it replaces saved beside it first
  droidvm-app.py start|stop|status

The daemon plumbing (IPC, configuration transaction, VM template) is the iOS tool's (ios/tools/droidvm-app.py, imported and
parameterised, never written to). The boot disk rides in "extra_options" as --block so no disk registry entry is needed; the OS,
SystemOS and Data disks are --virtio-mmio-block like in run-macos-vm.py.
"""
import argparse
import os
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
TAG = os.environ.get('MACOS_TAG', '23G93')   # artifacts/TAG and out/owner/{os,systemos}-TAG (macOS 27.2: MACOS_TAG=27.2)
# CSR_ALLOW_UNRESTRICTED_FS (as k27/try.sh): the dyld cache has no SF_RESTRICTED, and without it launchd cannot map the cache
os.environ.setdefault('MACOS_LP_SIP0', '0x2')
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
VM_NAME = 'macOS 27 (DroidVM)'
VM_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, 'macos-14.6.1.droidvm.macos'))
# MACOS_CPUS: vCPUs. Gunyah's idle vCPUs stay runnable on the host (WFI does not return), so eight of them on the eight cores left
# the host's GPU proxy, display blit and SurfaceFlinger competing with them, and WindowServer's vCPU was descheduled for whole
# frames (the guest's timers ran up to 0.5 s late during a window drag).
CPUS = int(os.environ.get('MACOS_CPUS') or 8)
# MACOS_CPU_PIN=1: droidvmd's default affinity, vCPU i on host core i. Pinned, a vCPU waited whenever a host thread (SurfaceFlinger,
# the display commit, another app's burst) had its core, though others were idle: with eight vCPUs a window drag stalled 50-450 ms
# about six times in ten seconds (none with six, whose two big cores stayed free). Each vCPU may run on any host core instead.
HOST_CORES = int(os.environ.get('MACOS_HOST_CORES') or 8)
CPU_AFFINITY = '' if os.environ.get('MACOS_CPU_PIN') == '1' else ':'.join(f'{i}=0-{HOST_CORES - 1}' for i in range(CPUS))
MEM_MB = int(os.environ.get('MACOS_MEM_MB') or 5120)   # MACOS_MEM_MB: the host's hugepage pool may not supply more (STARTING)
OUT = ROOT / 'out/app'
BOOT = FOLDER + '/boot.img'
DTB = FOLDER + '/generated.dtb'
# MACOS_GPU=1: Metal (DroidVMGpu's NativeAdreno, Turnip) on the virtio GPU's 3D (vgpu-3d=1, drm2kgsl on the host): needs
# MACOS_VIRTIO_GPU=1. crosvm's --droidvm-gpu (the host's KGSL, the old route) is gone from the VM.
GPU = os.environ.get('MACOS_GPU') == '1'
# WindowServer's frame pacing: CA triple buffering and the plugin's nextWakeupTime (updates a refresh apart, not on the VBL grid); a
# heavy window drag 60 to ~118 frames a second with them (kc283 to kc292)
GPU_ARGS = ['vgpu-3d=1', 'ca-triple-buffer=1', 'ca-free-wakeup=1']
# Not WindowServer:MallocZeroOnFree=0 (magazine malloc, no zeroing on free; about 8% more drag frames): SkyLight relies on fresh
# allocations being zero, as xzone's zero-on-free gives them, e.g. -[WSDisplayRenderSpace targetIDAtScreenLocation:...] mallocs an
# event record, sets a few fields and has CGSEventReclaimObjects CFRelease the others: WindowServer crashed on every touch's hit test.
# MACOS_EXEC_ENV can still add it.
GPU_EXEC_ENV = []
# MACOS_VIRTIO_GPU=1: the display is crosvm's virtio-gpu on virtio-mmio (--virtio-mmio-gpu, the last virtio-mmio window) instead of
# simplefb. The daemon builds its --gpu (virglrenderer, context-types=drm, udmabuf) and the gpu-0 screen's display service from the
# gpu_* fields and screens; the guest scans out IOSurface pages as guest-handle blobs, which the host blits (zero copy in the guest).
VIRTIO_GPU = os.environ.get('MACOS_VIRTIO_GPU') == '1'
REFRESH_HZ = int(os.environ.get('MACOS_REFRESH_HZ') or 120)
# MACOS_NET (default 1): the app's br-wifi network (a tap bridged to the phone's wlan0) as crosvm's virtio-net on virtio-mmio
# (--virtio-mmio-net, before --virtio-mmio-gpu's window), /arm-io/net in the ADT, driven by DroidVMEthernet
# (en0, DHCP from the Wi-Fi's router). The MAC is the one en0 had with no device behind it, so the Data volume's en0 stays en0.
# MACOS_NET=0: no device, en0 drops every packet (it still exists for the TimeSync clock). The template changes: register and prepare.
NET = os.environ.get('MACOS_NET', '1') == '1'
NET_MAC = '02:44:56:4d:00:01'
NET_BRIDGE = 'br-wifi'
# MACOS_MEDIA=1: VideoToolbox's paravirtualized codecs (DroidVMVideo) on the phone's MediaCodec: crosvm's virtio-media decoder and
# encoder on virtio-mmio (--virtio-mmio-media; their windows are the last ones, after --virtio-mmio-gpu's), /arm-io/virtio-media-N in
# the ADT, their buffers in the media_host pool (--pre-alloc media-host-mb=MACOS_MEDIA_POOL_MB, merged with the app's own --pre-alloc).
# The backends run under the app's uid (the codec service refuses uid 0). The template changes: register, or media for the VM as it is.
# The pool only has to exist (crosvm refuses the device on gunyah without one): DroidVMVideo's buffers are guest memory (USERPTR).
MEDIA = ['decoder', 'encoder'] if os.environ.get('MACOS_MEDIA') == '1' else []
MEDIA_POOL_MB = int(os.environ.get('MACOS_MEDIA_POOL_MB') or 8)
# MACOS_SND=1: the speaker and microphone (DroidVMAudio) on the phone's AAudio: crosvm's virtio-snd card (the upstream iPadOS rig's
# backend=aaudio, its helper under the app's uid) on virtio-mmio (--virtio-mmio-snd; its window follows --virtio-mmio-gpu's and comes
# before the media ones), /arm-io/virtio-snd in the ADT. Without it DroidVMAudio still publishes both devices and plays into silence.
# The template changes: register, or snd for the VM as it is.
SND = os.environ.get('MACOS_SND') == '1'
# MACOS_MEDIA_VIDC=1: the decoder on msm_vidc itself (crosvm's vidc=true: guest CAPTURE buffers as udmabufs, no MediaCodec).
MEDIA_VIDC = os.environ.get('MACOS_MEDIA_VIDC') == '1'
# The guest's display size is the boot console's (simplefb, the GOP DroidVMDisplay reads), so both screens carry it.
WIDTH, HEIGHT = 1920, 1080
FIRMWARE = FOLDER + '/edk2-macos.fd'   # ~/edk2-gunyah-topo built with -D VIRTIO_GPU_ENABLE=FALSE (edk2-gunyah-macos-novgpu.fd)
REQUIRED_ARGS = ['mac-amfi-launch-permissive=1', 'union-hide-lower=1', 'malloc-ranges-off=1', 'arm64_maxoffset=0x7FFE000000']   # see TODO.md: without them launchd cannot get far
# The board's -no_slto_panic is gone in xnu-12377: waitq and port locks spin under LockTimeOut (0.25 s, twice that for a waitq), and a
# vCPU the busy host did not run for that long while holding one panicked the guest at launchd's spawn storms; 40 times is 10 s
REQUIRED_ARGS.append('ml-timeout-lock-scale=40')
# CoreAudio (and Swift's clocks) take the host clock as 24 MHz whatever mach_timebase_info says; the counter here runs at 19.2 MHz, so
# without the kernel scaling it (patch 0042) the HAL writes every 80 ms instead of 64 ms and the sound stutters and falls behind the picture
REQUIRED_ARGS.append('droidvm-timebase-hz=24000000')
# MACOS_DROP_ARGS=NAME[,NAME]: leave those of the arguments above (and of GPU_ARGS) out
REQUIRED_ARGS = [a for a in REQUIRED_ARGS if a.split('=')[0] not in os.environ.get('MACOS_DROP_ARGS', '').split(',')]
# exec-env (one boot argument, groups split by ';'): WebKit's WebContent reserves a 64 GiB Gigacage aligned to 64 GiB, which the 39-bit
# user space (the GPU carveout at 64-448 GiB) cannot hold; without the cage Safari's pages load instead of WebContent crashing at launch
EXEC_ENV = ['com.apple.WebKit.WebContent:GIGACAGE_ENABLED=no']
# MACOS_EXEC_ENV=NAME:VAR=VALUE[;...]: more groups (e.g. metal-probe:TU_DARWIN_VIRTGPU=1, Turnip on virtio-gpu 3D for one process)
EXEC_ENV += [g for g in os.environ.get('MACOS_EXEC_ENV', '').split(';') if g]
# Everything the iOS functions read as module state: the VM identity, the folder (also its ownership reference), the output directory.
ios.FOLDER, ios.VM_NAME, ios.VM_ID, ios.MEM_MB, ios.OUT, ios.BOOT = FOLDER, VM_NAME, VM_ID, MEM_MB, OUT, BOOT
adb, sh = ios.adb, ios.sh


def fix_owner(path):
    sh(f'chown {run.OWNER} {path} && chmod 660 {path}')


ios.fix_owner = fix_owner


def template(persistent):
    """The iOS VM definition with the macOS particulars: eight vCPUs, boot disk as --block, no GPU/input mmio devices."""
    vm = ORIGINAL_VM_CONFIG(persistent)
    vm.update({'cpu_count': CPUS, 'cpu_affinity': CPU_AFFINITY, 'disks': [],
               'extra_options': ['--block', BOOT + ',lock=false', '--dump-device-tree-blob', DTB,
                                 '--virtio-mmio-block', FOLDER + '/os.img,ro=true,lock=false',
                                 '--virtio-mmio-block', FOLDER + '/systemos.img,ro=true,lock=false',
                                 '--virtio-mmio-block', run.STORE + ',lock=false',
                                 *(['--virtio-mmio-net'] if NET else []), *(['--virtio-mmio-gpu'] if VIRTIO_GPU else []),
                                 *snd_options(), *media_options()]})
    if NET:
        vm['networks'] = [{'network_id': network_id(), 'mac_address': NET_MAC}]
    if VIRTIO_GPU:
        vm.update({'gpu_backend': 'gpu_virglrenderer', 'gpu_mode': 'native', 'gpu_api': 'drm2kgsl'})
        # The app's edk2 drives the virtio-gpu (and on MMIO hangs with its queue size 0); this one has no driver for it, so the
        # bootloader keeps the simplefb GOP it wants (edk2-gunyah VIRTIO_GPU_ENABLE=FALSE; see FIRMWARE).
        vm['boot'] = dict(vm['boot'], uefi=dict(vm['boot']['uefi'], firmware=FIRMWARE))
        vm['screens'] = {'gpu-0': dict(vm['screens']['gpu-0'], enabled=True, exporter='native', transport_cap='gpu',
                                       width=WIDTH, height=HEIGHT, refresh_rate=REFRESH_HZ),
                         # simplefb stays (edk2's GOP, DarwinBoot and the boot console draw there) but is not shown
                         'simplefb': dict(vm['screens']['simplefb'], exporter='none', width=WIDTH, height=HEIGHT)}
    return vm


def media_options():
    if not MEDIA:
        return []
    uid = sh(f'stat -c %u {ios.APP}').strip()
    return ['--pre-alloc', f'media-host-mb={MEDIA_POOL_MB}', *[o for kind in MEDIA for o in ('--virtio-media', f'kind={kind},uid={uid}' + (',vidc=true' if MEDIA_VIDC and kind == 'decoder' else ''))],
            '--virtio-mmio-media']


def snd_options():
    if not SND:
        return []
    uid = sh(f'stat -c %u {ios.APP}').strip()
    return ['--virtio-snd', f'backend=aaudio,capture=true,num_output_devices=1,num_input_devices=1,uid={uid}', '--virtio-mmio-snd']


def strip_snd(options):
    """extra_options without what snd_options() adds."""
    kept, skip = [], False
    for option in options:
        if skip:
            skip = False
        elif option == '--virtio-snd':
            skip = True
        elif option != '--virtio-mmio-snd':
            kept.append(option)
    return kept


def strip_media(options):
    """extra_options without what media_options() adds."""
    kept, skip = [], False
    for option in options:
        if skip:
            skip = False
        elif option in ('--virtio-media', '--pre-alloc'):   # the app's own --pre-alloc is not among the extra options
            skip = True
        elif option != '--virtio-mmio-media':
            kept.append(option)
    return kept


def network_id():
    """The id of the app's br-wifi network (its networks.json), as the upstream rig's fresh-deploy.sh looks it up."""
    networks = json.loads(sh(f'cat {ios.APP}/files/networks.json'))['networks']
    ids = [n['id'] for n in networks if NET_BRIDGE in (n.get('bridge_name'), n.get('name'))]
    if not ids:
        raise SystemExit(f'no {NET_BRIDGE} network in the app (MACOS_NET=0 boots without one)')
    return ids[0]


ORIGINAL_VM_CONFIG = ios.vm_config
ios.vm_config = template


def push_images(args):
    artifacts = ROOT / f'artifacts/{TAG}'
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
    # The VM stopped just before (xnu12377-smoke.sh) may still be going down while the daemon rewrites the FDT: the pull fails then
    for attempt in range(10):
        try:
            adb('pull', DTB, str(fdt), timeout=60)
            break
        except subprocess.CalledProcessError:
            if attempt == 9:
                raise
            time.sleep(3)
    adt = OUT / 'kernel.macho.adt'
    # Below the shim's RAM base (0x600000 of firmware window), the framebuffer and the pools at the top of RAM (0xA00000 before:
    # the window and a 1280x800 framebuffer's 4 MiB)
    run.make_adt(fdt, hex(MEM_MB * 1024 * 1024 - 0x600000 - run.fdt_framebuffer_bytes(fdt) - run.fdt_pool_bytes(fdt)), '47554e5941480001', adt, cpu_regs=None,
                 virtio_gpu=VIRTIO_GPU, net=NET, snd=SND, media=len(MEDIA))   # every vCPU the app gives the VM
    artifacts = ROOT / f'artifacts/{TAG}'
    line = run.kernel_args(REQUIRED_ARGS + ([a for a in GPU_ARGS if a.split('=')[0] not in os.environ.get('MACOS_DROP_ARGS', '').split(',')] if GPU else []) +
                           ['exec-env=' + ';'.join(EXEC_ENV + (GPU_EXEC_ENV if GPU else []))] + args.kernel_arg)
    local = OUT / 'boot'
    if local.exists():
        subprocess.run(['rm', '-rf', str(local)], check=True)
    local.mkdir()
    # MACOS_TRUSTCACHE / MACOS_DATA_SEED: replacements staged by scripts/stage-gpu-plugin.py (the Metal plugin and its CDHashes)
    trust = Path(os.environ.get('MACOS_TRUSTCACHE') or artifacts / 'boot/kernel.macho.trustcache')
    seed = Path(os.environ.get('MACOS_DATA_SEED') or artifacts / 'data-seed/scratch-data.img')
    disk = run.build_boot_disk(local, trust, seed, adt, line)
    adb('push', str(disk), BOOT, timeout=900)
    fix_owner(BOOT)
    print('boot disk pushed:', BOOT, '\nkernel args:', line)


def dump_fdt():
    """Start the registered VM once with the boot disk it has, until crosvm has dumped the FDT, and stop it."""
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


def prepare(args):
    push_images(args)
    ios.register(args)
    dump_fdt()
    boot_disk(args)


def net(args):
    """The registered VM with (MACOS_NET=1) or without the virtio-mmio network: --virtio-mmio-net before --virtio-mmio-gpu (crosvm's
    order) and the br-wifi network at NET_MAC. A new MMIO window moves the virtio-gpu one, so the FDT is dumped again."""
    ipc = ios.Ipc()
    row = ios.find_vm(ipc)
    if row and row.get('state') != 'STOPPED':
        raise SystemExit(f'stop the running VM first ({row.get("state")})')
    vm = next(v for v in json.loads(sh(f'cat {ios.APP}/files/vms.json'))['vms'] if v['id'] == VM_ID)
    options = [o for o in vm['extra_options'] if o != '--virtio-mmio-net']
    if NET:
        options.insert(options.index('--virtio-mmio-gpu') if '--virtio-mmio-gpu' in options else len(options), '--virtio-mmio-net')
    vm.update({'extra_options': options, 'networks': [{'network_id': network_id(), 'mac_address': NET_MAC}] if NET else []})
    status = ipc.call('vm_config_status')
    reply = ipc.call('vm_config_apply', revision=status['revision'], operations=[{'op': 'replace', 'config': vm}])
    print('replace', reply.get('success'), reply.get('message', ''), reply.get('error', ''))
    if not reply.get('success'):
        raise SystemExit(1)
    dump_fdt()


def media(args):
    """The registered VM with (MACOS_MEDIA=1) or without the virtio-media decoder and encoder, every other setting kept; their windows
    come last, so the others stay where they were, but the FDT gains them: it is dumped again."""
    ipc = ios.Ipc()
    row = ios.find_vm(ipc)
    if row and row.get('state') != 'STOPPED':
        raise SystemExit(f'stop the running VM first ({row.get("state")})')
    vm = next(v for v in json.loads(sh(f'cat {ios.APP}/files/vms.json'))['vms'] if v['id'] == VM_ID)
    vm['extra_options'] = strip_media(vm['extra_options']) + media_options()   # the snd options stay ahead of them
    status = ipc.call('vm_config_status')
    reply = ipc.call('vm_config_apply', revision=status['revision'], operations=[{'op': 'replace', 'config': vm}])
    print('replace', reply.get('success'), reply.get('message', ''), reply.get('error', ''))
    if not reply.get('success'):
        raise SystemExit(1)
    dump_fdt()


def snd(args):
    """The registered VM with (MACOS_SND=1) or without the virtio-snd card, every other setting kept: its window goes before the
    media ones (crosvm's order), which move, so the FDT is dumped again."""
    ipc = ios.Ipc()
    row = ios.find_vm(ipc)
    if row and row.get('state') != 'STOPPED':
        raise SystemExit(f'stop the running VM first ({row.get("state")})')
    vm = next(v for v in json.loads(sh(f'cat {ios.APP}/files/vms.json'))['vms'] if v['id'] == VM_ID)
    options = strip_snd(vm['extra_options'])
    kept = strip_media(options)
    vm['extra_options'] = kept + snd_options() + options[len(kept):]   # the media options, as the VM has them, stay last
    status = ipc.call('vm_config_status')
    reply = ipc.call('vm_config_apply', revision=status['revision'], operations=[{'op': 'replace', 'config': vm}])
    print('replace', reply.get('success'), reply.get('message', ''), reply.get('error', ''))
    if not reply.get('success'):
        raise SystemExit(1)
    dump_fdt()


def store_patch(args):
    """The blocks stage-gpu-plugin.py --store wrote into a copy of the Data store, written into the phone's (in place: the file is
    17 GiB, mostly holes). The blocks they replace go to data-store.undo.{bin,txt} first; the same loop with the undo files puts
    them back."""
    row = ios.find_vm(ios.Ipc())
    if row and row.get('state') != 'STOPPED':
        raise SystemExit(f'stop the running VM first ({row.get("state")})')
    stage = ROOT / 'out/metal/stage'
    for name in ('store-patch.bin', 'store-patch.txt'):
        adb('push', str(stage / name), f'{FOLDER}/{name}', timeout=600)
    store, patch, undo = run.STORE, f'{FOLDER}/store-patch', f'{FOLDER}/data-store.undo'
    sh(f'cp {patch}.txt {undo}.txt && rm -f {undo}.bin && at=0 && while read first count; do '
       f'dd if={store} of={undo}.bin bs=4096 skip=$first seek=$at count=$count conv=notrunc 2>/dev/null || exit 1; '
       f'dd if={patch}.bin of={store} bs=4096 skip=$at seek=$first count=$count conv=notrunc 2>/dev/null || exit 1; '
       f'at=$((at + count)); done < {patch}.txt && rm {patch}.bin {patch}.txt && sync', timeout=600)
    print(sh(f'ls -la {store} {undo}.bin'))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    for name in ('prepare', 'boot'):
        sub.add_parser(name).add_argument('--kernel-arg', action='append', default=[], help='extra kernel argument NAME[=VALUE]')
    for name in ('push', 'register', 'net', 'snd', 'media', 'store-patch', 'start', 'stop', 'status'):
        sub.add_parser(name)
    args = parser.parse_args()
    if args.cmd in ('status', 'stop'):
        ios.control(args)
    elif args.cmd == 'push':
        push_images(args)
    elif args.cmd == 'boot':
        boot_disk(args)
    elif args.cmd == 'prepare':
        prepare(args)
    elif args.cmd == 'net':
        net(args)
    elif args.cmd == 'snd':
        snd(args)
    elif args.cmd == 'media':
        media(args)
    elif args.cmd == 'store-patch':
        store_patch(args)
    else:
        {'register': ios.register, 'start': ios.start}[args.cmd](args)


if __name__ == '__main__':
    main()
