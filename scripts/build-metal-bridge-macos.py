#!/usr/bin/env python3
"""Build UniXNU's native Metal bridge (drivers/NativeMetal/bridge/NativeMetalBridge.rs: the pinned metal2vulkan runtime behind a C ABI) as a
static library for macOS arm64e on Linux: UniXNU's scripts/build-native-metal-bridge.py with the arm64e-apple-darwin target, which is
tier 3 (nightly, -Zbuild-std), through configs/arm64e-apple-darwin.json (below). C and assembly of the dependencies build with LLVM 21 against MacOSX26.1.sdk.

    build-metal-bridge-macos.py

Source: sources/UniXNU/.cache/gpu-reference/metal2vulkan at the pin of scripts/data/gpu-metal-vulkan-inputs.json; its recorded patches
are applied here if they are not yet. Output: out/metal/bridge/libnative_metal_bridge.a"""
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIXNU = ROOT / 'sources/UniXNU'
SOURCE = UNIXNU / '.cache/gpu-reference/metal2vulkan'
OUT = ROOT / 'out/metal/bridge'
SDK = ROOT / 'toolchains/sdks/MacOSX26.1.sdk'
LLVM = Path('/usr/lib/llvm-21/bin')
TRIPLE = 'arm64e-apple-darwin'
# rustc's arm64e-apple-darwin leaves pointer authentication off: function pointers from C (dlsym, vkGetInstanceProcAddr: signed with IA,
# discriminator 0) were called as raw addresses, and C would call Rust's unsigned ones. rustc implements clang's ABI (blraaz, paciza,
# pacibsp/retab, signed static function pointers) for cfg(target_abi = "pauthtest") only, so this is the built-in target with that ABI;
# init-fini off: dyld signs Mach-O initializers itself.
TARGET_SPEC = ROOT / 'configs/arm64e-apple-darwin.json'
PATCHES = sorted((UNIXNU / 'drivers/NativeMetal/bridge/patches').glob('*.patch'))

pin = json.loads((UNIXNU / 'scripts/data/gpu-metal-vulkan-inputs.json').read_text())['translator']['commit']
if subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip() != pin:
    raise SystemExit(f'{SOURCE} is not at the pinned translator commit {pin}')
for patch in PATCHES:
    if subprocess.run(['git', '-C', str(SOURCE), 'apply', '--reverse', '--check', str(patch)], capture_output=True).returncode:
        subprocess.run(['git', '-C', str(SOURCE), 'apply', str(patch)], check=True)
OUT.mkdir(parents=True, exist_ok=True)
# the runtime's example library and function-constant fixture, assembled to AIR for the bridge's self-tests
air, fc_air = OUT / 'runtime_examples.air', OUT / 'function_constant.air'
fixtures = SOURCE / 'crates/metal2vulkan-validation/fixtures/public'
subprocess.run([str(LLVM / 'llvm-as'), '-o', str(air), str(fixtures / 'examples/runtime_examples.ll')], check=True)
subprocess.run([str(LLVM / 'llvm-as'), '-o', str(fc_air), str(fixtures / 'kernel_function_constant_gate_fold.ll')], check=True)
manifest = OUT / 'Cargo.toml'
manifest.write_text('\n'.join([
    '[package]', 'name = "native-metal-bridge"', 'version = "0.1.0"', 'edition = "2024"', '[workspace]',
    '[lib]', 'crate-type = ["staticlib"]', 'path = ' + json.dumps(str(UNIXNU / 'drivers/NativeMetal/bridge/NativeMetalBridge.rs')),
    '[dependencies]',
    'metal2vulkan = { path = ' + json.dumps(str(SOURCE / 'crates/metal2vulkan')) + ', features = ["ash"] }',
    'metal2vulkan-runtime = { path = ' + json.dumps(str(SOURCE / 'crates/metal2vulkan-runtime')) + ' }',
    'libc = "0.2"',
    # the shader cache's hashes: not UniXNU's "asm" (ARMv8 SHA-256 instructions), which pulls sha2-asm and cc-rs, and cc-rs takes
    # target_abi = "pauthtest" for the Linux pauthtest target
    'sha2 = "0.10"',
    '[profile.release]', 'panic = "unwind"', 'debug = 1', '',
]))
key = TRIPLE.replace('-', '_')
env = dict(os.environ, RUSTFLAGS='-Zpointer-authentication=-init-fini', NMB_FIXTURE_AIR=str(air), NMB_FC_AIR=str(fc_air), MACOSX_DEPLOYMENT_TARGET='14.0', SDKROOT=str(SDK),
           **{f'CC_{key}': str(LLVM / 'clang'), f'CXX_{key}': str(LLVM / 'clang++'), f'AR_{key}': str(LLVM / 'llvm-ar'),
              f'CFLAGS_{key}': f'-isysroot {SDK}', f'CXXFLAGS_{key}': f'-isysroot {SDK}'})
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
