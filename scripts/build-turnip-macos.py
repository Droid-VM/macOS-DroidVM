#!/usr/bin/env python3
"""Cross-build Turnip (Mesa freedreno Vulkan with UniXNU's darwin kernel backend, patches/mesa/turnip-darwin-kmd.patch) for macOS
arm64e on Linux: the ios branch of UniXNU's scripts/build-turnip-darwin.py with this host's compilers.

    build-turnip-macos.py [--configure-only] [--builtin-pack PACK]

Source: sources/UniXNU-turnip/.cache/mesa-work at the pin of that tree's scripts/data/adreno-compiler-inputs.json with its recorded
patches applied. sources/UniXNU-turnip is a worktree of sources/UniXNU at Droid-VM/UniXNU wip/droidvm (527b8b7, 2026-11-06: Droid-VM/mesa
cecc0e9 and 21 patches, the virtio GPU backend and its queue priority, deadline queue, BO cache budgets and lazy BOs among them), apart from
the board's own UniXNU checkout (whose NativeMetal and other pins stay):
    git -C sources/UniXNU worktree add --detach ../UniXNU-turnip 527b8b7
    git -C sources/UniXNU/.cache/mesa-work fetch --depth 1 https://github.com/Droid-VM/mesa cecc0e96d7193c72356a31abb0cc589e4fc0415e
    git -C sources/UniXNU/.cache/mesa-work worktree add --detach $PWD/sources/UniXNU-turnip/.cache/mesa-work cecc0e96d7193c72356a31abb0cc589e4fc0415e
    then git apply each of the pins' "patches" there, in order.
The darwin backend's ABI header is the NativeAdreno the kernel's DroidVMGpu is built from (out/x12377/src-gpu, scripts/build-droidvm-gpu.py).
Compiles with LLVM 21 (arm64e-apple-macos14.0, MacOSX26.1.sdk) and links with Apple's ld-classic (scripts/apple-ld.py --raw).
Output: out/metal/mesa-tu/src/freedreno/vulkan/libvulkan_freedreno.dylib"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIXNU = ROOT / 'sources/UniXNU-turnip'
SOURCE = UNIXNU / '.cache/mesa-work'
OUT = ROOT / 'out/metal/mesa-tu'
SDK = ROOT / 'toolchains/sdks/MacOSX26.1.sdk'
ABI = ROOT / 'out/x12377/src-gpu/drivers/NativeAdreno'
LLVM = Path('/usr/lib/llvm-21/bin')
STRIP = ROOT / 'toolchains/linux/toolchain/bin/aarch64-apple-darwin-strip'

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('--configure-only', action='store_true')
parser.add_argument('--builtin-pack', type=Path, help="embed Turnip's own built-in shaders, exported from this exact build on the guest "
                    '(tu_export_builtin_shader_pack after vkCreateDevice): no device compiles them again')
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
           '-Dbuildtype=release', '-Db_ndebug=true']
# The built-in shader pack's identity (patches/mesa/turnip-builtin-shader-pack.patch wants 64 hex digits, else it neither exports nor
# loads one), as the board's build-turnip-darwin.py: bound to every source edit (the recorded patches and patches/mesa-macos), the
# compiler and the options, the pack itself left out (it would make the identity circular). A pack from any other build is refused.
LOCAL_PATCHES = sorted((ROOT / 'patches/mesa-macos').glob('*.patch'))
profile = dict(mesa_revision=pins['mesa']['commit'], target='macos-arm64e',
               source_diff_sha256=hashlib.sha256(subprocess.check_output(['git', '-C', str(SOURCE), 'diff', 'HEAD', '--binary'])).hexdigest(),
               local_patches=[hashlib.sha256(patch.read_bytes()).hexdigest() for patch in LOCAL_PATCHES],
               compiler=subprocess.check_output([str(LLVM / 'clang'), '--version'], text=True), options=options)
source_id = hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
pack_header = ''
if args.builtin_pack:
    pack = args.builtin_pack.read_bytes()
    if not 112 <= len(pack) <= 4 << 20 or pack[:8] != b'TUBUILT1' or pack[16:80] != source_id.encode():
        raise SystemExit(f'{args.builtin_pack} is not from this build (source id {source_id}); export it again from this build')
    header = OUT.parent / 'tu_builtin_pack.generated.h'
    header.write_text('static const unsigned char tu_builtin_pack_bytes[] = {\n' +
                      ''.join(','.join('0x%02x' % b for b in pack[i:i + 16]) + ',\n' for i in range(0, len(pack), 16)) + '};\n')
    pack_header = str(header)
(OUT.parent / 'mesa-tu-builtin-profile.json').write_text(json.dumps(dict(source_id=source_id, profile=profile,
                                                                         pack=str(args.builtin_pack or '')), indent=2) + '\n')
# The same identity as Turnip's build id: its pipelineCacheUUID, which names metal2vulkan's driver pipeline records, otherwise hashes
# the library file's mtime (no ELF build id here), which every staging of the plugin changes, so no record outlived a restage.
options += ['-Dtu-builtin-source-id=' + source_id, '-Dtu-builtin-pack-header=' + pack_header, '-Dtu-build-id=' + source_id]
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
# This build's Mesa changes (patches/mesa-macos, in order, LOCAL_PATCHES above), applied to the recorded source for the build and taken
# back out after it: the recorded patches stay what validate_recorded_patches checks.


def local_patches(apply):
    for patch in LOCAL_PATCHES if apply else reversed(LOCAL_PATCHES):
        result = subprocess.run(['git', 'apply'] + ([] if apply else ['--reverse']) + [str(patch)], cwd=SOURCE,
                                capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(f'{patch.name} no longer applies\n{result.stderr}')


log = OUT.parent / 'mesa-tu-build.log'
local_patches(True)
try:
    with log.open('w') as stream:
        result = subprocess.run(['ninja', '-C', str(OUT), '-j16'], env=env, stdout=stream, stderr=subprocess.STDOUT)
finally:
    local_patches(False)
if result.returncode:
    raise SystemExit(f'build failed; see {log}\n' + '\n'.join(
        l for l in log.read_text().splitlines() if ': error:' in l or 'fatal error:' in l or l.startswith('FAILED:'))[:3000])
library = OUT / 'src/freedreno/vulkan/libvulkan_freedreno.dylib'
# As the board's build (UniXNU 527b8b7): the entrypoints Mesa leaves unimplemented are weak flat-namespace imports, which dyld looked
# up in every loaded image in every process that opened a Metal device (3 s of CPU); bound to the library itself they stay NULL.
# The board's script reads chained fixups; ld-classic writes dyld-info binds, so this host's twin (which keeps the linker's
# ad-hoc signature valid). Idempotent.
subprocess.run([sys.executable, str(ROOT / 'scripts/macho-weak-self-binds-dyldinfo.py'), str(library)], check=True)
symbols = subprocess.run([str(LLVM / 'llvm-nm'), '-gU', str(library)], capture_output=True, text=True).stdout
if ' T _vk_icdGetInstanceProcAddr' not in symbols:
    raise SystemExit(f'{library} does not export vk_icdGetInstanceProcAddr')
print(f'{library}: {library.stat().st_size} bytes, built-in source id {source_id}' + (', built-in pack embedded' if pack_header else ''))
