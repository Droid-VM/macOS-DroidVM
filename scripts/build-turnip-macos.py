#!/usr/bin/env python3
"""Cross-build Turnip (Mesa freedreno Vulkan with UniXNU's darwin kernel backend, patches/mesa/turnip-darwin-kmd.patch) for macOS
arm64e on Linux: the ios branch of UniXNU's scripts/build-turnip-darwin.py with this host's compilers.

    build-turnip-macos.py [--configure-only]

Source: sources/UniXNU/.cache/mesa-work at the pin of scripts/data/adreno-compiler-inputs.json with its recorded patches applied.
The darwin backend's ABI header is the NativeAdreno the kernel's DroidVMGpu is built from (out/x12377/src-gpu, scripts/build-droidvm-gpu.py).
Compiles with LLVM 21 (arm64e-apple-macos14.0, MacOSX26.1.sdk) and links with Apple's ld-classic (scripts/apple-ld.py --raw).
Output: out/metal/mesa-tu/src/freedreno/vulkan/libvulkan_freedreno.dylib"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIXNU = ROOT / 'sources/UniXNU'
SOURCE = UNIXNU / '.cache/mesa-work'
OUT = ROOT / 'out/metal/mesa-tu'
SDK = ROOT / 'toolchains/sdks/MacOSX26.1.sdk'
ABI = ROOT / 'out/x12377/src-gpu/drivers/NativeAdreno'
LLVM = Path('/usr/lib/llvm-21/bin')
STRIP = ROOT / 'toolchains/linux/toolchain/bin/aarch64-apple-darwin-strip'

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('--configure-only', action='store_true')
args = parser.parse_args()

sys.path.insert(0, str(UNIXNU / 'scripts'))
from mesa_patch_identity import validate_recorded_patches  # noqa: E402

pins = json.loads((UNIXNU / 'scripts/data/adreno-compiler-inputs.json').read_text())
if subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip() != pins['mesa']['commit']:
    raise SystemExit(f'{SOURCE} is not at the pinned Mesa commit')
(UNIXNU / '.cache').mkdir(exist_ok=True)
validate_recorded_patches(UNIXNU, SOURCE, pins)
if not (ABI / 'NativeAdrenoABI.h').is_file():
    raise SystemExit('run scripts/build-droidvm-gpu.py first (it exports NativeAdreno to out/x12377/src-gpu)')

OUT.parent.mkdir(parents=True, exist_ok=True)
linker = OUT.parent / 'apple-ld-raw'
linker.write_text(f'#!/bin/sh\nexec python3 {ROOT / "scripts/apple-ld.py"} --raw "$@"\n')
linker.chmod(0o755)
flags = ['-target', 'arm64e-apple-macos14.0', '-isysroot', str(SDK), '-fstack-protector-strong']
link_flags = flags + ['--ld-path=' + str(linker)]
cross = OUT.parent / 'mesa-tu-macos.cross'
cross.write_text(
    '[binaries]\nc = %r\ncpp = %r\nobjc = %r\nar = %r\nstrip = %r\npkg-config = \'/usr/bin/false\'\n'
    % (str(LLVM / 'clang'), str(LLVM / 'clang++'), str(LLVM / 'clang'), str(LLVM / 'llvm-ar'), str(STRIP)) +
    "[host_machine]\nsystem = 'darwin'\ncpu_family = 'aarch64'\ncpu = 'arm64'\nendian = 'little'\n"
    "[properties]\nneeds_exe_wrapper = true\n[built-in options]\n" +
    ''.join('%s = %r\n' % (k, flags) for k in ('c_args', 'cpp_args', 'objc_args')) +
    ''.join('%s = %r\n' % (k, link_flags) for k in ('c_link_args', 'cpp_link_args', 'objc_link_args')))
options = ['-Dgallium-drivers=', '-Dvulkan-drivers=freedreno', '-Dfreedreno-kmds=darwin', '-Dtu-darwin-abi-dir=' + str(ABI),
           '-Dplatforms=macos', '-Dglx=disabled', '-Degl=disabled', '-Dgbm=disabled', '-Dopengl=false', '-Dgles1=disabled',
           '-Dgles2=disabled', '-Dllvm=disabled', '-Dshared-glapi=disabled', '-Dxmlconfig=disabled', '-Dshader-cache=disabled',
           '-Dtools=', '-Dbuild-tests=false', '-Dvideo-codecs=', '-Dvulkan-layers=',
           # as UniXNU's tablet build: release without assertions and per-pass NIR validation
           '-Dlibunwind=disabled', '-Dlmsensors=disabled', '-Dvalgrind=disabled', '-Dexpat=disabled', '-Dzstd=disabled',
           '-Dbuildtype=release', '-Db_ndebug=true',
           '-Dtu-builtin-source-id=macos-arm64e-' + pins['mesa']['commit'][:12], '-Dtu-builtin-pack-header=']
env = {k: v for k, v in os.environ.items() if not k.startswith(('IR3_', 'FD_MESA_', 'NIR_', 'MESA_SHADER_', 'TU_'))}
env.update(CC=str(LLVM / 'clang'), CXX=str(LLVM / 'clang++'), CFLAGS='', CXXFLAGS='', CPPFLAGS='', LDFLAGS='')
# the compiler driver's temporary objects must be where the Darling container sees them (it mounts the workspace only)
(OUT.parent / 'tmp').mkdir(exist_ok=True)
env['TMPDIR'] = str(OUT.parent / 'tmp')
log = OUT.parent / 'mesa-tu-configure.log'
if (OUT / 'build.ninja').exists():
    command = ['meson', 'configure', str(OUT), *options]
else:
    command = ['meson', 'setup', str(OUT), str(SOURCE), '--wrap-mode=nodownload', '--cross-file', str(cross), *options]
with log.open('w') as stream:
    if subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT).returncode:
        raise SystemExit(f'configure failed; see {log}\n' + '\n'.join(log.read_text().splitlines()[-15:]))
if args.configure_only:
    print(f'configured {OUT}')
    sys.exit(0)
log = OUT.parent / 'mesa-tu-build.log'
with log.open('w') as stream:
    result = subprocess.run(['ninja', '-C', str(OUT), '-j16'], env=env, stdout=stream, stderr=subprocess.STDOUT)
if result.returncode:
    raise SystemExit(f'build failed; see {log}\n' + '\n'.join(
        l for l in log.read_text().splitlines() if ': error:' in l or 'fatal error:' in l or l.startswith('FAILED:'))[:3000])
library = OUT / 'src/freedreno/vulkan/libvulkan_freedreno.dylib'
symbols = subprocess.run([str(LLVM / 'llvm-nm'), '-gU', str(library)], capture_output=True, text=True).stdout
if ' T _vk_icdGetInstanceProcAddr' not in symbols:
    raise SystemExit(f'{library} does not export vk_icdGetInstanceProcAddr')
print(f'{library}: {library.stat().st_size} bytes')
