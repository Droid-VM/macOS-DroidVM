#!/usr/bin/env python3
"""Build DroidVMGpu (NativeAdreno published for Metal on the virtio GPU's 3D, vgpu-3d=1) as a native kext of the collection:
overlay/kext/DroidVMGpu.json.

    build-droidvm-gpu.py

The sources, exported to out/x12377/src-gpu laid out as a UniXNU tree: NativeAdreno 805c7e4 (the commit UniXNU-droidvm bf7fc44 builds
with) with patches/droidvm-gpu/NativeAdreno, and bf7fc44's package/DroidVMGpu.cpp and DroidVMGpuWire.h with
patches/droidvm-gpu/UniXNU-droidvm (0002: the hardware classes NativeAdrenoVm/Ring/Timer never attached, the wire removed; the VM
has no droidvm-gpu device); AdrenoPM4 and ArmSmmu4K at the commits UniXNU's wip/droidvm pins. The patches are the commits of
branch droidvm-macos of sources/UniXNU/drivers/NativeAdreno and of sources/UniXNU-droidvm: after a commit there, export them again
(git format-patch --no-signature 805c7e4..droidvm-macos, bf7fc44..droidvm-macos). overlay/kext/DroidVMGpuKext.cpp starts the publish.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'out/x12377/src-gpu'
UNIXNU = ROOT / 'sources/UniXNU'
DROIDVM = ROOT / 'sources/UniXNU-droidvm'
PATCHES = ROOT / 'patches/droidvm-gpu'
REF = 'bf7fc44'
PINS = {'drivers/NativeAdreno': '805c7e4bfb7451eb6923f4a14dea8c657b9be7d2', 'kits/AdrenoPM4': '445f8fe6d115738352b9d78dc70af6d61aa7f62f',
        'kits/ArmSmmu4K': '4d0d6598b1a36aeec3de01091893fa6660e49388'}


def patch(directory, patches, strip):
    for path in patches:
        result = subprocess.run(['patch', f'-p{strip}', '--forward', '--batch', '--no-backup-if-mismatch', '-s', '-d', str(directory),
                                 '-i', str(path)], capture_output=True, text=True)
        if result.returncode:
            sys.exit(f'{path.name} does not apply:\n{result.stdout}{result.stderr}')


for path, commit in PINS.items():
    subprocess.run(['rm', '-rf', str(SRC / path)], check=True)
    (SRC / path).mkdir(parents=True)
    archive = subprocess.run(['git', '-C', str(UNIXNU / path), 'archive', commit], capture_output=True, check=True).stdout
    subprocess.run(['tar', '-x', '-C', str(SRC / path)], input=archive, check=True)
board = SRC / 'kits/droidvm'
board.mkdir(parents=True, exist_ok=True)
for name in ('DroidVMGpu.cpp', 'DroidVMGpuWire.h'):
    (board / name).write_bytes(subprocess.run(['git', '-C', str(DROIDVM), 'show', f'{REF}:package/{name}'], capture_output=True,
                                              check=True).stdout)
adreno = SRC / 'drivers/NativeAdreno'
patch(adreno, sorted((PATCHES / 'NativeAdreno').glob('*.patch')), 1)
patch(board, sorted((PATCHES / 'UniXNU-droidvm').glob('*.patch')), 2)   # a/package/NAME

sources = [adreno / 'NativeAdrenoSubmit.cpp', adreno / 'NativeAdrenoMemory.cpp', adreno / 'NativeAdrenoCpu.cpp',
           adreno / 'NativeAdrenoUserClient.cpp', adreno / 'NativeAdrenoPublish.cpp', board / 'DroidVMGpu.cpp',
           SRC / 'kits/AdrenoPM4/AdrenoPM4.c', ROOT / 'overlay/kext/DroidVMGpuKext.cpp', ROOT / 'overlay/kext/NativeKextGlue.cpp']
# IOKit/graphics (AGXAccelerator's IOAccelerator) from the macOS SDK's Kernel.framework: toolchains/sdks/MacOSX26.1.sdk.tar.xz, extracted
GRAPHICS = ROOT / 'out/x12377/inc-gfx'
if not (GRAPHICS / 'IOKit/graphics').exists():
    (GRAPHICS / 'IOKit').mkdir(parents=True, exist_ok=True)
    (GRAPHICS / 'IOKit/graphics').symlink_to(ROOT / 'toolchains/sdks/MacOSX26.1.sdk/System/Library/Frameworks/Kernel.framework/Headers/IOKit/graphics')
includes = [adreno, SRC / 'kits/ArmSmmu4K', SRC / 'kits/AdrenoPM4', board, GRAPHICS]
print(f'droidvm-gpu: UniXNU-droidvm {REF}, NativeAdreno {PINS["drivers/NativeAdreno"][:7]}, '
      f'{len(list((PATCHES / "NativeAdreno").glob("*.patch")))} + {len(list((PATCHES / "UniXNU-droidvm").glob("*.patch")))} patches')
subprocess.run(['python3', str(ROOT / 'scripts/build-native-kext.py'), 'DroidVMGpu', *map(str, sources),
                *[f'-I{path}' for path in includes]], check=True)
