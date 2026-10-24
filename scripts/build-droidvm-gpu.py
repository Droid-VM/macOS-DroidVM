#!/usr/bin/env python3
"""Build DroidVMGpu (crosvm --droidvm-gpu, the host's KGSL) as a native kext of the collection: overlay/kext/DroidVMGpu.json.

    build-droidvm-gpu.py

The sources are those of UniXNU-droidvm's scripts/build-droidvm-gpu.py at REF (by the wire, below):
NativeAdreno's user client, IOKit surface, execbuf and memory with the PM4 encoder, the hardware classes (NativeAdrenoVm/Ring/Timer)
from package/DroidVMGpu.cpp. NativeAdreno, AdrenoPM4 and ArmSmmu4K are the commits UniXNU's wip/droidvm pins. They are exported to
out/x12377/src-gpu laid out as a UniXNU tree, and that script runs there up to its compile step, so its staged edits (of
NativeAdrenoPublish.cpp, and NativeAdrenoUserClient.cpp or NativeAdrenoMemory.cpp) are used as they are. overlay/kext/DroidVMGpuKext.cpp starts the device.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'out/x12377/src-gpu'
UNIXNU = ROOT / 'sources/UniXNU'
DROIDVM = ROOT / 'sources/UniXNU-droidvm'
# The guest side must speak the wire of the phone's crosvm (DROIDVM_GPU_WIRE): 1 is the App's crosvm of 2026-10-22 (external/crosvm
# drm-droidvm-mmio 7d1e255; UniXNU-droidvm bf7fc44 with NativeAdreno 805c7e4), 3 is crosvm's droidvm wip/virtio-mmio (UniXNU-droidvm
# wip/hackintosh with the NativeAdreno UniXNU wip/droidvm pins).
WIRE = os.environ.get('DROIDVM_GPU_WIRE', '1')
REF, ADRENO_PIN = {'1': ('bf7fc44', '805c7e4bfb7451eb6923f4a14dea8c657b9be7d2'),
                   '3': ('origin/wip/hackintosh', 'b686b9054f57d393c80195b82568a09f8ca106a2')}[WIRE]
PINS = {'drivers/NativeAdreno': ADRENO_PIN, 'kits/AdrenoPM4': '445f8fe6d115738352b9d78dc70af6d61aa7f62f',
        'kits/ArmSmmu4K': '4d0d6598b1a36aeec3de01091893fa6660e49388'}


def git_show(repo, ref, path):
    return subprocess.run(['git', '-C', str(repo), 'show', f'{ref}:{path}'], capture_output=True, check=True).stdout


def export():
    for path, commit in PINS.items():
        stamp = SRC / path / '.commit'
        if stamp.exists() and stamp.read_text() == commit:
            continue
        subprocess.run(['rm', '-rf', str(SRC / path)], check=True)
        (SRC / path).mkdir(parents=True)
        archive = subprocess.run(['git', '-C', str(UNIXNU / path), 'archive', commit], capture_output=True, check=True).stdout
        subprocess.run(['tar', '-x', '-C', str(SRC / path)], input=archive, check=True)
        stamp.write_text(commit)
    (SRC / 'kits/droidvm').mkdir(parents=True, exist_ok=True)
    for name in ('DroidVMGpu.cpp', 'DroidVMGpuWire.h'):
        (SRC / 'kits/droidvm' / name).write_bytes(git_show(DROIDVM, REF, f'package/{name}'))
    (SRC / 'scripts').mkdir(exist_ok=True)
    script = SRC / 'scripts/build-droidvm-gpu.py'
    script.write_bytes(git_show(DROIDVM, REF, 'scripts/build-droidvm-gpu.py'))
    return script


def stage(script):
    """Run the upstream script up to its compiles; returns its globals (staged, staged_memory, ADRENO, ROOT)."""
    text = script.read_text()
    cut = text.find('\ncxx = recipe(')
    if cut < 0:
        sys.exit(f'{script}: no compile step to stop at')
    scope = {'__file__': str(script), '__name__': 'droidvm_gpu_stage'}
    exec(compile(text[:cut], str(script), 'exec'), scope)
    return scope


scope = stage(export())
adreno = scope['ADRENO']
sources = [adreno / 'NativeAdrenoSubmit.cpp', scope.get('staged_memory', adreno / 'NativeAdrenoMemory.cpp'), adreno / 'NativeAdrenoCpu.cpp',
           scope.get('staged_client', adreno / 'NativeAdrenoUserClient.cpp'), scope['staged'], SRC / 'kits/droidvm/DroidVMGpu.cpp', SRC / 'kits/AdrenoPM4/AdrenoPM4.c',
           ROOT / 'overlay/kext/DroidVMGpuKext.cpp', ROOT / 'overlay/kext/NativeKextGlue.cpp']
# IOKit/graphics (AGXAccelerator's IOAccelerator) from the macOS SDK's Kernel.framework: toolchains/sdks/MacOSX26.1.sdk.tar.xz, extracted
GRAPHICS = ROOT / 'out/x12377/inc-gfx'
if not (GRAPHICS / 'IOKit/graphics').exists():
    (GRAPHICS / 'IOKit').mkdir(parents=True, exist_ok=True)
    (GRAPHICS / 'IOKit/graphics').symlink_to(ROOT / 'toolchains/sdks/MacOSX26.1.sdk/System/Library/Frameworks/Kernel.framework/Headers/IOKit/graphics')
includes = [adreno, SRC / 'kits/ArmSmmu4K', SRC / 'kits/AdrenoPM4', SRC / 'kits/droidvm', GRAPHICS]
print(f'droidvm-gpu: wire {WIRE} ({REF}, NativeAdreno {ADRENO_PIN[:7]})')
subprocess.run(['python3', str(ROOT / 'scripts/build-native-kext.py'), 'DroidVMGpu', *map(str, sources),
                *[f'-I{path}' for path in includes]], check=True)
