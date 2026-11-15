#!/usr/bin/env python3
"""Build UniXNU's native Metal bridge (drivers/NativeMetal/bridge/NativeMetalBridge.rs: the pinned metal2vulkan runtime behind a C ABI) as a
static library for macOS arm64e on Linux: UniXNU's scripts/build-native-metal-bridge.py with the arm64e-apple-darwin target, which is
tier 3 (nightly, -Zbuild-std), through configs/arm64e-apple-darwin.json (below). C and assembly of the dependencies build with LLVM 21 against MacOSX26.1.sdk.

    build-metal-bridge-macos.py

Source: METAL2VULKAN_SOURCE at the compatible translator pin, with patches from NATIVE_METAL_SOURCE.
Patches are applied once to a dedicated worktree; METAL2VULKAN_PREPATCHED=1 reuses it. Output: out/metal/bridge/libnative_metal_bridge.a"""
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIXNU = ROOT / 'sources/UniXNU'
NATIVE = Path(os.environ.get('NATIVE_METAL_SOURCE', UNIXNU / 'drivers/NativeMetal'))
SOURCE = Path(os.environ.get('METAL2VULKAN_SOURCE', UNIXNU / '.cache/gpu-reference/metal2vulkan'))
OUT = ROOT / 'out/metal/bridge'
SDK = ROOT / 'toolchains/sdks/MacOSX26.1.sdk'
LLVM = Path('/usr/lib/llvm-21/bin')
TRIPLE = 'arm64e-apple-darwin'
# rustc's arm64e-apple-darwin leaves pointer authentication off: function pointers from C (dlsym, vkGetInstanceProcAddr: signed with IA,
# discriminator 0) were called as raw addresses, and C would call Rust's unsigned ones. rustc implements clang's ABI (blraaz, paciza,
# pacibsp/retab, signed static function pointers) for cfg(target_abi = "pauthtest") only, so this is the built-in target with that ABI;
# init-fini off: dyld signs Mach-O initializers itself.
TARGET_SPEC = ROOT / 'configs/arm64e-apple-darwin.json'
# Use AdrenoMetal's complete patch stack at its matching translator pin. Patch 0040
# consolidates the older runtime/board patches; do not append that older stack.
# Set METAL2VULKAN_PREPATCHED=1 when reusing the dedicated patched worktree.
PATCHES = sorted((NATIVE / 'bridge/patches').glob('*.patch')) + [
    ROOT / 'patches/metal2vulkan-macos/0003-rate-map-buffer-reflection.patch',
    ROOT / 'patches/metal2vulkan-macos/0004-opaque-indirect-pointer-reflection.patch',
    ROOT / 'patches/metal2vulkan-macos/0005-identity-texture-swizzle.patch',
]
pin = '555b13d57e09bff70996a88cff64f1275256d5cf'

if subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip() != pin:
    raise SystemExit(f'{SOURCE} is not at the pinned translator commit {pin}')


# Apply to a dedicated translator worktree; never reset the caller's source.
OUT.mkdir(parents=True, exist_ok=True)
if os.environ.get('METAL2VULKAN_PREPATCHED') != '1':
    for patch in PATCHES:
        subprocess.run(['git', '-C', str(SOURCE), 'apply', str(patch)], check=True)
runtime_id = os.environ.get('NMB_RUNTIME_ID', 'upstream-rate-map-20261113')
# the runtime's example library and function-constant fixture, assembled to AIR for the bridge's self-tests
air, fc_air = OUT / 'runtime_examples.air', OUT / 'function_constant.air'
fixtures = SOURCE / 'crates/metal2vulkan-validation/fixtures/public'
subprocess.run([str(LLVM / 'llvm-as'), '-o', str(air), str(fixtures / 'examples/runtime_examples.ll')], check=True)
subprocess.run([str(LLVM / 'llvm-as'), '-o', str(fc_air), str(fixtures / 'kernel_function_constant_gate_fold.ll')], check=True)
# the GPU scanout's half-float conversion kernel (NativeMetal shaders/scanout_convert.ll, GpuScanoutPresenter.h)
scanout_air = OUT / 'scanout_convert.air'
subprocess.run([str(LLVM / 'llvm-as'), '-o', str(scanout_air), str(NATIVE / 'shaders/scanout_convert.ll')], check=True)
manifest = OUT / 'Cargo.toml'
manifest.write_text('\n'.join([
    '[package]', 'name = "native-metal-bridge"', 'version = "0.1.0"', 'edition = "2024"', '[workspace]',
    '[lib]', 'crate-type = ["staticlib"]', 'path = ' + json.dumps(str(NATIVE / 'bridge/NativeMetalBridge.rs')),
    '[dependencies]',
    'metal2vulkan = { path = ' + json.dumps(str(SOURCE / 'crates/metal2vulkan')) + ', features = ["ash"] }',
    'metal2vulkan-runtime = { path = ' + json.dumps(str(SOURCE / 'crates/metal2vulkan-runtime')) + ' }',
    'libc = "0.2"',
    # WindowServer's update thread spends much of a frame in the runtime's small functions across the translator's crates: one
    # optimisation unit with link-time optimisation inlines them across crate boundaries (as build-adreno-metal-bridge.py)
    '[profile.release]', 'panic = "unwind"', 'debug = 1', 'lto = "fat"', 'codegen-units = 1', '',
]))
key = TRIPLE.replace('-', '_')
env = dict(os.environ, NMB_RUNTIME_ID=runtime_id, RUSTFLAGS='-Zpointer-authentication=-init-fini', NMB_FIXTURE_AIR=str(air), NMB_FC_AIR=str(fc_air), NMB_SCANOUT_AIR=str(scanout_air), MACOSX_DEPLOYMENT_TARGET='14.0', SDKROOT=str(SDK),
           **{f'CC_{key}': str(LLVM / 'clang'), f'CXX_{key}': str(LLVM / 'clang++'), f'AR_{key}': str(LLVM / 'llvm-ar'),
              f'CFLAGS_{key}': f'-target arm64e-apple-macos14.0 -isysroot {SDK} -O2', f'CXXFLAGS_{key}': f'-isysroot {SDK}'},
           # dependencies' C goes through cc-rs, which would derive a Linux triple from the target spec's target_abi (pauthtest): its
           # defaults off, the triple and SDK are CFLAGS' above
           CRATE_CC_NO_DEFAULTS='1')
target_dir = OUT / 'target'
log = OUT / 'build.log'
with log.open('w') as stream:
    result = subprocess.run(['cargo', '+nightly', 'build', '--release', '-Zbuild-std=std,panic_unwind', '-Zjson-target-spec', '--manifest-path',
                             str(manifest), '--target', str(TARGET_SPEC), '--target-dir', str(target_dir)], env=env, stdout=stream, stderr=subprocess.STDOUT,
                            timeout=3600)
if result.returncode:
    raise SystemExit(log.read_text()[-6000:])
library = OUT / 'libnative_metal_bridge.a'
shutil.copyfile(target_dir / TRIPLE / 'release/libnative_metal_bridge.a', library)
print(f'{library}: {library.stat().st_size} bytes (translator {pin[:12]})')
