#!/usr/bin/env python3
"""Boot the locally built macOS root once on the phone (crosvm-mmio on Gunyah) and keep the evidence.

Adapted from ios tools/run-droidvm.py (ios commit 9a1e72d). The single virtio-mmio disk is the Data store (rw, sparse), containing
the System/Data volume group. The boot disk is assembled here from the kernel, trust cache bundle, Data seed, UniXNU.efi and
DarwinBoot.efi; its ADT is generated from the FDT this exact VM configuration produces (crosvm --dump-device-tree-blob).
"""
import argparse
import hashlib
import importlib.util
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
TAG = os.environ.get('MACOS_TAG', '27.2')   # artifacts/TAG
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True
import phone_pool  # noqa: E402

APP = '/data/data/cn.classfun.droidvm/usr'
CROSVM = APP + '/bin/crosvm-mmio'
FOLDER = '/data/media/0/DroidVM/MacOS'              # /storage/emulated/0/DroidVM/MacOS: the images the app's VM and the test runs share
# MACOS_INSTANCE=NAME: a second VM beside the usual one (its own folder MacOS-NAME, data store and App entry), e.g. a new install
# (make-macos-disk.py) tried without touching the VM in use
INSTANCE = os.environ.get('MACOS_INSTANCE', '')
if INSTANCE:
    FOLDER += '-' + INSTANCE
OWNER = 'u0_a258:media_rw'                          # the owner of the DroidVM folder; the daemon opens leased disks as the app
STORE = FOLDER + '/data-store.img'
# The System volume of the Data store's APFS volume group; empty no longer selects a legacy layout.
ROOT_UUID = os.environ.get('MACOS_ROOT_UUID', '4646A7E0-5598-41A2-B158-E1AF6D3CF7FB').upper()
if not ROOT_UUID:
    raise SystemExit('MACOS_ROOT_UUID must name the System volume (disk.json); the legacy union layout was removed')
DATA_STORE_MMIO = 0x0a000000
# /arm-io/pcie's device-interrupt-parent under MACOS_PCIE=1: DroidVMGicMsi takes it as its AAPL,phandle once it is registered as the
# bridge's interrupt controller ('MBIF'; the ADT's nodes have no AAPL,phandle of their own). overlay/kext/DroidVMGicMsi.cpp has it too.
GIC_MBI_PHANDLE = 0x4d424946
OS_UUID = ROOT_UUID
BOARD = ROOT / 'sources/UniXNU-droidvm/board.toml'
ADT_TOOL = ROOT / 'sources/UniXNU-droidvm/scripts/make-droidvm-adt.py'
KERNEL = Path(os.environ.get('MACOS_KERNEL', ROOT / 'out/linux/reference/droidvm/kernel/kernel.macho'))
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


def require_store(adb):
    """A new install must be deployed with droidvm-app.py install before it can boot."""
    if sh(adb, f'test -f {STORE} && echo yes', check=False).strip() != 'yes':
        raise SystemExit(f'{STORE} is missing: create a disk with make-macos-disk.py and deploy it with droidvm-app.py install')


def vm_command(mem_mb):
    return [CROSVM, 'run', '--hypervisor', 'gunyah', '--mem', str(mem_mb), '--cpus', '1',
            '--protected-vm-pseudo-unprotected', '--no-balloon', '--disable-sandbox',
            '--hugepages', '--prepare-lend-mthp-mode', 'single',
            '--simplefb', 'width=1280,height=800,format=a8r8g8b8',
            '--serial', 'type=file,hardware=serial,num=1,path=serial.log',
            '--dump-device-tree-blob', 'generated.dtb',
            '--block', 'boot.img,lock=false',
            '--virtio-mmio-block', f'{STORE},lock=false',
            APP + '/share/droidvm/edk2-gunyah.fd']


# The iOS board's offline display probes (bsd_init's native_mobile_graphics_load_probe): on xnu-12377 they find DroidVMDisplay's
# IOMobileFramebuffer and drive a user client with no owner (offline-mobile-graphics-client: a NULL dereference in externalMethod).
IOS_DISPLAY_PROBES = ('offline-mobile-graphics-load', 'offline-mobile-graphics-client', 'offline-legacy-register', 'offline-legacy-gop',
                      'offline-legacy-phase', 'offline-legacy-unit-scale', 'offline-legacy-pm', 'offline-legacy-validate',
                      'offline-legacy-transfer', 'offline-legacy-cpu-present')


def kernel_args(extra):
    board = tomllib.loads(BOARD.read_text())
    arguments = [a for a in board['payload']['kernel_args'] if not a.startswith(GPU_ARGS)]
    dropped = {a[5:] for a in extra if a.startswith('drop:')}      # drop:NAME removes a board argument (the line is limited to 1000 bytes)
    if os.environ.get('MACOS_KERNEL'):
        # armcpu-diagnostics=1 panics when one interrupt drains more than 128 timer interrupts: a macOS boot under load reaches that
        dropped |= set(IOS_DISPLAY_PROBES) | {'armcpu-diagnostics'}
    if os.environ.get('MACOS_KERNEL'):
        # bluetoothd runs, on the ADT's virtual controller (/bluetooth, below): IOBluetoothHostController's first use
        # (+defaultController) waits on CoreBluetooth's state with no timeout -- System Settings' Sharing pane and Language Chooser
        # hung in -[IOBluetoothCoreBluetoothCoordinator init].
        for i, a in enumerate(arguments):
            if a.startswith('droidvm-disable-jobs='):
                jobs = [j for j in a.split('=', 1)[1].split(',') if j != 'com.apple.bluetoothd']
                arguments[i] = 'droidvm-disable-jobs=' + ','.join(jobs)
    extra = [a for a in extra if not a.startswith('drop:')]
    names = {a.split('=', 1)[0] for a in extra}
    arguments = [a for a in arguments if a.split('=', 1)[0] not in names | dropped] + extra
    line = ' '.join(arguments)
    if len(line) > 1000:
        raise SystemExit(f'kernel command line is {len(line)} bytes; the limit is 1000')
    return line


def last_virtio_mmio(tool, fdt, skip=0):
    """skip: how many windows from the end to pass over (1: --droidvm-gpu when --virtio-mmio-gpu follows it)."""
    spec = importlib.util.spec_from_file_location('make_droidvm_adt', tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base = sorted(base for base, _ in module.describe(module.parse_fdt(Path(fdt).read_bytes()))['virtio_mmio'])[-1 - skip]
    # Without the MMIO Data store, the first window belongs to GPU/net/audio.
    if base < DATA_STORE_MMIO or (base == DATA_STORE_MMIO and os.environ.get('MACOS_DATA_PCI') != '1'):
        raise SystemExit(f'{fdt} has no virtio-mmio window after the data store: prepare again with --droidvm-gpu in the VM')
    return base


def fdt_pool_bytes(fdt):
    """The bytes of the top of RAM crosvm keeps for its droidvm,pool regions (the drm2kgsl host pool of --gpu ...,context-types=drm):
    the ADT's DRAM ends below them."""
    spec = importlib.util.spec_from_file_location('make_droidvm_adt', ADT_TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return sum(size for props in module.parse_fdt(Path(fdt).read_bytes()).values() if b'droidvm,pool' in props.get('compatible', b'')
               for _, size in module.reg_pairs(props['reg']))


def fdt_framebuffer_bytes(fdt):
    """The bytes of crosvm's simplefb framebuffer (the boot console, below the pools at the top of RAM; its size follows the
    screen's): the ADT's DRAM ends below it too, or the kernel's early mapping of it crosses the DRAM boundary and panics before
    the console is up (pmap_map_bd_with_options)."""
    spec = importlib.util.spec_from_file_location('make_droidvm_adt', ADT_TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return sum(size for props in module.parse_fdt(Path(fdt).read_bytes()).values()
               if props.get('compatible', b'').startswith(b'simple-framebuffer\0') for _, size in module.reg_pairs(props['reg']))


def make_adt(fdt, dram_size, unique_chip_id, output, cpu_regs='0', gpu=False, virtio_gpu=False, net=False, snd=False, media=0):
    """cpu_regs: FDT CPU reg values to start, or None for every CPU of the FDT (ArmCpu starts at most eight).
    gpu: crosvm --droidvm-gpu is on; its window is the FDT's last virtio-mmio one (it follows the disks) and becomes /arm-io/gpu.
    net: crosvm --virtio-mmio-net is on; crosvm puts its window after --droidvm-gpu's and before --virtio-mmio-gpu's: /arm-io/net.
    snd: crosvm --virtio-mmio-snd is on; its window follows --virtio-mmio-gpu's, before the media ones: /arm-io/virtio-snd.
    media: how many crosvm --virtio-media devices --virtio-mmio-media puts on virtio-mmio; theirs are the last windows (after
    --virtio-mmio-gpu's): /arm-io/virtio-media-N."""
    tool = ADT_TOOL
    if os.environ.get('MACOS_KERNEL'):
        # xnu-12377 asks the bootloader for 256 bytes of entropy (xnu-10063: 64); the tool of sources/ stays untouched.
        tool = ROOT / 'out/adt/make-droidvm-adt.py'
        tool.parent.mkdir(parents=True, exist_ok=True)
        text = ADT_TOOL.read_text()
        assert text.count('os.urandom(64)') == 1
        text = text.replace('os.urandom(64)', 'os.urandom(256)')
        # macOS reads the SIP configuration iBoot passes in /chosen/asmb (csr_bootstrap, CONFIG_CSR_FROM_DT): lp-sip0 the bits, lp-sip1 =
        # CSR_ALLOW_UNAUTHENTICATED_ROOT, which mounts the sealed system volume live instead of through its signed snapshot (a boot manifest we lack).
        marker = "node('manifest-properties')]),"
        assert text.count(marker) == 1
        sip = int(os.environ.get('MACOS_LP_SIP0', '0x0'), 0)
        text = text.replace(marker, f"node('manifest-properties'), node('asmb', [('lp-sip0', struct.pack('<Q', {sip:#x})), ('lp-sip1', struct.pack('<I', 1))])]),")
        # MACOS_IOFB=1, the fallback display: /arm-io/framebuffer is the console the bootloader set up (boot_args Video, the GOP), which
        # IOGraphicsFamily's IOBootFramebuffer drives when its provider has AAPL,boot-display (overlay/kext/DroidVMFramebuffer.json);
        # WindowServer (CoreDisplay's CGXMappedDisplayStart) opens every IOFramebuffer. The display route is IOMFB (DroidVMDisplay).
        marker = "              *[node('gpu', [('compatible', b'droidvm,gpu\\0'),"
        assert text.count(marker) == 1
        if os.environ.get('MACOS_IOFB') == '1':
            text = text.replace(marker, "              node('framebuffer', [('compatible', b'droidvm,framebuffer\\0'), ('AAPL,boot-display', struct.pack('<I', 1))]),\n" + marker)
        # MACOS_DISPLAY=1, the display: IOMobileFramebuffer.framework expects the framebuffers of an /arm-io node compatible
        # "paravirtualizedgraphics,gpu" (as vma2's), whose nub DroidVMDisplay's AppleParavirtGPU matches (overlay/kext/DroidVMDisplay.json).
        if os.environ.get('MACOS_DISPLAY') == '1':
            text = text.replace(marker, "              node('display', [('compatible', b'paravirtualizedgraphics,gpu\\0')]),\n" + marker)
        # The PCI host (crosvm's --input devices are virtio-pci functions): /arm-io/pcie, the FDT's ECAM window, where DroidVMInput
        # finds the app's touch screen, tablet, mouse and keyboard (overlay/kext/DroidVMInput.json).
        assert text.count('    vm = describe(parse_fdt(args.fdt.read_bytes()))') == 1
        text = text.replace('    vm = describe(parse_fdt(args.fdt.read_bytes()))',
                            '    fdt_nodes = parse_fdt(args.fdt.read_bytes())\n    vm = describe(fdt_nodes)')
        # crosvm's PL030 RTC supplies wall time before userspace services create absolute deadlines.
        text = text.replace(marker, "              *[node('rtc', [('compatible', b'arm,pl030\\0'),"
                                    " ('reg', struct.pack('<QQ', address - ARMIO_BASE, size))])"
                                    " for props in fdt_nodes.values() if props.get('arm,primecell-periphid') == struct.pack('>I', 0x41030)"
                                    " for address, size in reg_pairs(props['reg'])],\n" + marker)
        if os.environ.get('MACOS_PCIE') == '1':
            # MACOS_PCIE=1: Apple's own bridge, AppleVirtualPlatformPCIE (docs/k27-vmapple-pcie-msi-plan.md), takes /arm-io/pcie
            # (its personality on IOPlatformDevice: overlay/kext/AppleVirtualPlatformPCIE.json). It reads #address-cells 3 and
            # #size-cells 2, and each 28-byte ranges entry as a flags word and the little-endian PCI address, CPU address and size
            # (it adds the PCI address, which crosvm makes the CPU's). The parent address is relative to arm-io, whose ranges
            # add ARMIO_BASE during IODTResolveAddressing; its interrupt parent is the service whose AAPL,phandle is
            # device-interrupt-parent, DroidVMGicMsi on /arm-io/gic-mbi (crosvm's MBI frame, from the FDT's mbi-alias), and
            # msi-frame-index that service's memory with the frame. Without the FDT's MBI frame (no --mbi-spis) it has no MSI.
            text = text.replace(marker, "              *[node('pcie', [('compatible', b'pcie,vmapple1\\0'), ('device_type', b'pci\\0'),"
                                        " ('reg', struct.pack('<QQ', address - ARMIO_BASE, size)),"
                                        " ('#address-cells', struct.pack('<I', 3)), ('#size-cells', struct.pack('<I', 2)),"
                                        " ('ranges', b''.join(struct.pack('<IQQQ', c[i], c[i + 1] << 32 | c[i + 2], (c[i + 3] << 32 | c[i + 4]) - ARMIO_BASE,"
                                        " c[i + 5] << 32 | c[i + 6]) for c in [cells(props['ranges'])] for i in range(0, len(c), 7))),"
                                        f" ('device-interrupt-parent', struct.pack('<I', {GIC_MBI_PHANDLE:#x})),"
                                        " *([('msi-frame-index', struct.pack('<I', 0))] if any('mbi-alias' in p for p in fdt_nodes.values()) else []),"
                                        " ('dma-coherent', b'')]) for props in fdt_nodes.values()"
                                        " if b'pci-host-ecam-generic' in props.get('compatible', b'') for address, size in [reg_pairs(props['reg'])[0]]],\n"
                                        "              *[node('gic-mbi', [('compatible', b'droidvm,gic-mbi\\0'),"
                                        " ('reg', struct.pack('<QQ', struct.unpack('>Q', props['mbi-alias'])[0] - ARMIO_BASE, 0x1000)),"
                                        " ('mbi-ranges', struct.pack('<II', *cells(props['mbi-ranges'])))])"
                                        " for props in fdt_nodes.values() if 'mbi-alias' in props],\n" + marker)
        else:
            text = text.replace(marker, "              *[node('pcie', [('compatible', b'pci-host-ecam-generic\\0'), ('reg', struct.pack('<QQ', address - ARMIO_BASE, size)),"
                                        " ('dma-coherent', b'')]) for address, size in [reg_pairs(props['reg'])[0] for props in fdt_nodes.values()"
                                        " if b'pci-host-ecam-generic' in props.get('compatible', b'')]],\n" + marker)
        # The Data volume persists in the data store (NativeRamBlock with DroidVMDataStore), so /chosen does not say ephemeral-storage:
        # with hw.ephemeral_storage set, usermanagerd skips its persona manager (os_variant_uses_ephemeral_storage) and then fails the
        # assertion _gPersonaManager != nil on loginwindow's persona login, and loginwindow never launches Dock, Finder and SystemUIServer.
        marker = "*([('ephemeral-storage', struct.pack('<I', 1))] if (args.data_ramdisk or args.packed_data_ramdisk) else []),"
        assert text.count(marker) == 1
        # MACOS_BOOT_MANIFEST_HASH=1 (k27, the macOS 27 kexts): /chosen/boot-manifest-hash, the SHA-384 of the boot manifest iBoot
        # would pass. 27's Image4 kext initializes its nonce magazine with it and panics without ("unable to initialize magazine: 7");
        # there is no manifest, so it is zeros.
        if os.environ.get('MACOS_BOOT_MANIFEST_HASH') == '1':
            text = text.replace(marker, "('boot-manifest-hash', bytes(48)), " + marker)
        text = text.replace(marker, "*([('ephemeral-storage', struct.pack('<I', 1))] if (args.data_ramdisk or args.packed_data_ramdisk)"
                                    " and args.data_store_mmio is None else []),"
                            if os.environ.get('MACOS_DATA_PCI') != '1' else '')
        # MACOS_VMM_PRESENT=0: /defaults without vmm-present, so kern.hv_vmm_present is 0. MobileGestalt answers IsVirtualDevice from it,
        # and Core Animation on a virtual device keeps a half-float 'RGhA' framebuffer (IOMFBDisplay::framebuffer_pixel_format returns
        # before its 'BGRA' choice) and takes the VM's display paths (CursorPlane).
        if os.environ.get('MACOS_VMM_PRESENT', '1') == '0':
            marker = "('vmm-present', struct.pack('<I', 1)),"
            assert text.count(marker) == 1
            text = text.replace(marker, '')
        # /bluetooth, as upstream's iPadOS 27 board (UniXNU-droidvm make-droidvm-adt.py): bluetoothd finds its controller by name
        # (IOServiceNameMatching "marconi-bt", then "bluetooth") and without one exits ("Unable to match bluetooth service in device
        # tree"), and CoreBluetooth's clients never get a state: IOBluetoothCoreBluetoothCoordinator's init waits for its central
        # manager's first state update with no timeout, and System Settings' Sharing pane hung there. transport-encoding 10 is the
        # virtual transport of Apple's own VMs (bluetoothd's VirtualController); with kern.hv_vmm_present set ("Bluetooth is running
        # inside a Virtual Machine, so skipping chip initialization") it needs no chip. local-mac-address: six bytes, not all zero,
        # locally administered and stable for one unique chip ID.
        marker = "        node('options', []),"
        assert text.count(marker) == 1
        text = text.replace(marker, marker + "\n        node('bluetooth', [('device_type', b'bluetooth\\0'), ('transport-encoding', struct.pack('<I', 10)),"
                                    " ('local-mac-address', bytes([0x02, 0xd7]) + zlib.crc32(b'bluetooth' + (args.unique_chip_id or 0x4456)"
                                    ".to_bytes(8, 'little')).to_bytes(4, 'big'))]),")
        # virtio_gpu (crosvm --virtio-mmio-gpu, the last virtio-mmio window): /arm-io/virtio-gpu, the display's scanout device
        # (DroidVMDisplay); like the upstream tool's --virtio-gpu-mmio, it is not one of the generic virtio-mmio nodes.
        marker = "    parser.add_argument('--display-gamut',"
        assert text.count(marker) == 1
        text = text.replace(marker, "    parser.add_argument('--virtio-gpu-mmio', type=lambda value: int(value, 0), default=None)\n"
                                    "    parser.add_argument('--net-mmio', type=lambda value: int(value, 0), default=None)\n"
                                    "    parser.add_argument('--snd-mmio', type=lambda value: int(value, 0), default=None)\n"
                                    "    parser.add_argument('--media-mmio', type=lambda value: [int(v, 0) for v in value.split(',') if v], default=[])\n" + marker)
        marker = "if window[0] not in (args.data_store_mmio, args.gpu_mmio) and window[0] not in input_bases]"
        assert text.count(marker) == 1
        text = text.replace(marker, "if window[0] not in (args.data_store_mmio, args.gpu_mmio, args.virtio_gpu_mmio, args.net_mmio, args.snd_mmio)"
                                    " and window[0] not in input_bases and window[0] not in args.media_mmio]")
        marker = "                for address, size in gpu]]),"
        assert text.count(marker) == 1
        text = text.replace(marker, "                for address, size in gpu],\n"
                                    "              *[node('virtio-gpu', [('compatible', b'droidvm,virtio-gpu\\0'),"
                                    " ('reg', struct.pack('<QQ', address - ARMIO_BASE, size)), ('dma-coherent', b''),"
                                    # drm-host-pool: the FDT's drm2kgsl_host pool (absolute GPA, size), where the host carves the 3D
                                    # contexts' shmem (DroidVMVirtioGpu3D.cpp; as the upstream tool's)
                                    " *[('drm-host-pool', struct.pack('<QQ', *reg_pairs(props['reg'])[0])) for path, props in fdt_nodes.items()"
                                    " if path.startswith('/reserved-memory/drm2kgsl_host@')]])"
                                    " for address, size in vm['virtio_mmio'] if address == args.virtio_gpu_mmio],\n"
                                    # net (crosvm --virtio-mmio-net): /arm-io/net, DroidVMEthernet's virtio-net (as the upstream tool's --net-mmio)
                                    "              *[node('net', [('compatible', b'droidvm,net\\0'),"
                                    " ('reg', struct.pack('<QQ', address - ARMIO_BASE, size)), ('dma-coherent', b'')])"
                                    " for address, size in vm['virtio_mmio'] if address == args.net_mmio],\n"
                                    # virtio-snd (crosvm --virtio-mmio-snd): DroidVMAudio's sound card (as the upstream tool's --snd-mmio)
                                    "              *[node('virtio-snd', [('compatible', b'droidvm,virtio-snd\\0'),"
                                    " ('reg', struct.pack('<QQ', address - ARMIO_BASE, size)), ('dma-coherent', b'')])"
                                    " for address, size in vm['virtio_mmio'] if address == args.snd_mmio],\n"
                                    # virtio-media-N (crosvm --virtio-mmio-media): DroidVMVideo's decoder and encoder, with the FDT's
                                    # media_host pool (absolute GPA, size) their MMAP buffers live in (as the upstream tool's --media-mmio)
                                    "              *[node('virtio-media-%d' % index, [('compatible', b'droidvm,virtio-media\\0'),"
                                    " ('reg', struct.pack('<QQ', address - ARMIO_BASE, size)), ('dma-coherent', b''),"
                                    " *[('media-host-pool', struct.pack('<QQ', *reg_pairs(props['reg'])[0])) for path, props in fdt_nodes.items()"
                                    " if path.startswith('/reserved-memory/media_host@')]])"
                                    " for index, (address, size) in enumerate([window for base in args.media_mmio for window in vm['virtio_mmio']"
                                    " if window[0] == base])]]),")
        # The CPU clusters (the kernel's BCM2837 board is AMP, sched_amp): each cpu's cluster-type is 'P' where the FDT's
        # capacity-dmips-mhz is the highest of the CPUs started (crosvm --cpu-capacity, from the app's topology), else 'E'; all 'P'
        # when they are equal or absent. The AMP kernel panics on a CPU without one; MACOS_AMP=0 leaves them out for an older kernel,
        # which would read 'P' as a second cluster it does not have. MACOS_CPU_TYPES=EEEEEEPP sets them by CPU instead (a test).
        types = os.environ.get('MACOS_CPU_TYPES', '')
        if os.environ.get('MACOS_AMP', '1') == '1' and types:
            assert set(types) <= {'E', 'P'}
            marker = "('device_type', b'cpu\\0'), ('compatible', b'arm,armv8\\0'),"
            assert text.count(marker) == 1
            text = text.replace(marker, marker + f" ('cluster-type', {types!r}[index].encode() + b'\\0'),")
        elif os.environ.get('MACOS_AMP', '1') == '1':
            marker = "    cpus = [node('cpu%d' % index,"
            assert text.count(marker) == 1
            text = text.replace(marker, "    capacity = {cells(props['reg'])[0]: cells(props['capacity-dmips-mhz'])[0] for path, props in fdt_nodes.items()\n"
                                        "                if path.startswith('/cpus/') and props.get('device_type') == b'cpu\\0' and 'capacity-dmips-mhz' in props}\n"
                                        "    top = max((capacity.get(reg, 0) for reg in cpu_regs), default=0)\n" + marker)
            marker = "('device_type', b'cpu\\0'), ('compatible', b'arm,armv8\\0'),"
            assert text.count(marker) == 1
            text = text.replace(marker, "('device_type', b'cpu\\0'), ('compatible', b'arm,armv8\\0'),"
                                        " ('cluster-type', b'P\\0' if capacity.get(reg, top) == top else b'E\\0'),")
        tool.write_text(text)
    subprocess.run(['python3', str(tool), '--fdt', str(fdt), '--dram-size', dram_size,
                    '--dram-base', '0x80600000', '--owned-memory-size', '0x30000000',
                    *(['--cpu-regs', cpu_regs] if cpu_regs else []),
                    '--root-match-volume-uuid', OS_UUID, '--packed-data-ramdisk',
                    '--ipad-identity', '--unique-chip-id', unique_chip_id, '--chip-id', '8011',
                    '--trust-cache',
                    *(['--data-ramdisk', '--data-store-mmio', hex(DATA_STORE_MMIO)] if os.environ.get('MACOS_DATA_PCI') != '1' else []),
                    '--reclaim-memory',
                    *(['--gpu-mmio', hex(last_virtio_mmio(tool, fdt, media + int(snd) + int(virtio_gpu) + int(net)))] if gpu else []),
                    *(['--net-mmio', hex(last_virtio_mmio(tool, fdt, media + int(snd) + int(virtio_gpu)))] if net else []),
                    *(['--virtio-gpu-mmio', hex(last_virtio_mmio(tool, fdt, media + int(snd)))] if virtio_gpu else []),
                    *(['--snd-mmio', hex(last_virtio_mmio(tool, fdt, media))] if snd else []),
                    *(['--media-mmio', ','.join(hex(last_virtio_mmio(tool, fdt, media - 1 - i)) for i in range(media))] if media else []),
                    # MACOS_GAMUT=sRGB: /product artwork-display-gamut sRGB. With the panel's P3, MobileGestalt's
                    # HasExtendedColorDisplay makes Core Animation compose into wide-color framebuffers ('b3a8'); the display copies
                    # 8-bit 'BGRA' best (scripts/stage-gpu-plugin.py removes the MobileGestalt cache that would keep the old answer).
                    '--display-gamut', os.environ.get('MACOS_GAMUT', 'P3'),
                    '--output', str(output)], check=True)


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
    artifacts = ROOT / f'artifacts/{TAG}'
    trust = artifacts / 'boot/kernel.macho.trustcache'
    data = Path(os.environ.get('MACOS_DATA_SEED') or artifacts / 'disk/scratch-data.img')
    for path in (KERNEL, trust, data, INPUTS / 'UniXNU.efi', INPUTS / 'DarwinBoot.efi'):
        if not path.is_file():
            raise SystemExit(f'missing {path}')
    phone_pool.prepare_host_pool(adb, mem_mb, mem_mb + 128, local / 'host-pool-before.json')
    require_store(adb)
    sh(adb, f'mkdir -p {remote}')
    run_env = f'LD_LIBRARY_PATH={APP}/lib'
    line = kernel_args(args.kernel_arg)
    # Pass 1: let crosvm describe this VM (FDT) with a placeholder boot disk, then stop it.
    placeholder = local / 'placeholder.img'
    subprocess.run(['truncate', '-s', '64M', str(placeholder)], check=True)
    subprocess.run(adb + ['push', str(placeholder), remote + '/boot.img'], check=True, timeout=300)
    vm = vm_command(mem_mb)
    sh(adb, f'cd {remote} && (env {run_env} {shlex.join(vm)} < /dev/null > crosvm-pass1.log 2>&1 &) ; sleep 12; pkill -x crosvm-mmio ; sleep 2; ls -la generated.dtb')
    subprocess.run(adb + ['pull', remote + '/generated.dtb', str(local / 'generated.dtb')], check=True, timeout=30)
    sh(adb, 'sleep 5')
    adt = local / 'kernel.macho.adt'
    make_adt(local / 'generated.dtb', dram_size, args.unique_chip_id, adt)
    disk = build_boot_disk(local, trust, data, adt, line)
    subprocess.run(adb + ['push', str(disk), remote + '/boot.img'], check=True, timeout=600)
    phone_pool.prepare_host_pool(adb, mem_mb, mem_mb + 128, local / 'host-pool-run.json')
    (local / 'command.txt').write_text(shlex.join(vm) + '\n')
    (local / 'inputs.json').write_text(json.dumps({
        'kernel_sha256': sha256(KERNEL), 'trust_sha256': sha256(trust), 'data_seed_sha256': sha256(data),
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
