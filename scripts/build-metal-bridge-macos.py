#!/usr/bin/env python3
"""Build UniXNU's native Metal bridge (drivers/NativeMetal/bridge/NativeMetalBridge.rs: the pinned metal2vulkan runtime behind a C ABI) as a
static library for macOS arm64e on Linux: UniXNU's scripts/build-native-metal-bridge.py with the arm64e-apple-darwin target, which is
tier 3 (nightly, -Zbuild-std), through configs/arm64e-apple-darwin.json (below). C and assembly of the dependencies build with LLVM 21 against MacOSX26.1.sdk.

    build-metal-bridge-macos.py

Source: METAL2VULKAN_SOURCE (default: the dedicated worktree sources/UniXNU/.cache/gpu-reference/metal2vulkan-555b13d) at the compatible
translator pin, with patches from NATIVE_METAL_SOURCE. A clean worktree at the pin is patched; one already holding exactly the patched tree is
reused as it is; any other state is refused. Output: out/metal/bridge/libnative_metal_bridge.a"""
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIXNU = ROOT / 'sources/UniXNU'
NATIVE = Path(os.environ.get('NATIVE_METAL_SOURCE', UNIXNU / 'drivers/NativeMetal'))
SOURCE = Path(os.environ.get('METAL2VULKAN_SOURCE', UNIXNU / '.cache/gpu-reference/metal2vulkan-555b13d'))
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
# AdrenoMetal main's 0046 (main-optimizations) is the whole of its translator from the pin: 0002-0041 and its own
# changes in one patch, so where it is present it is the stack alone.
_MAIN = sorted((NATIVE / 'bridge/patches').glob('*-main-optimizations-on-development-*.patch'))
PATCHES = (_MAIN[-1:] or sorted((NATIVE / 'bridge/patches').glob('*.patch'))) + [
    ROOT / 'patches/metal2vulkan-macos/0003-rate-map-buffer-reflection.patch',
    ROOT / 'patches/metal2vulkan-macos/0004-opaque-indirect-pointer-reflection.patch',
    ROOT / 'patches/metal2vulkan-macos/0005-identity-texture-swizzle.patch',
    ROOT / 'patches/metal2vulkan-macos/0006-sixteen-mib-memory-blocks.patch',
    # NativeMetal 935c468's bridge (nmb_device_hold_back_memory, nmb_device_trim_memory) asks the runtime for these; the board's
    # metal2vulkan 0013 and 0020 (Droid-VM/UniXNU patches/metal2vulkan) have them on its own translator stack, not this one.
    ROOT / 'patches/metal2vulkan-macos/0007-hold-back-and-trim-kept-memory.patch',
]
pin = '555b13d57e09bff70996a88cff64f1275256d5cf'

if subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip() != pin:
    raise SystemExit(f'{SOURCE} is not at the pinned translator commit {pin}')


def tree_of(index, patches=(), worktree=False):
    """The tree of the pin with `patches` applied, or of SOURCE's files (new ones too) where `worktree`, through a scratch index."""
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    git = ['git', '-C', str(SOURCE)]
    subprocess.run(git + ['read-tree', pin], env=env, check=True)
    for patch in patches:
        subprocess.run(git + ['apply', '--cached', str(patch)], env=env, check=True)
    if worktree:
        subprocess.run(git + ['add', '-A', '.'], env=env, check=True)
    return subprocess.check_output(git + ['write-tree'], env=env, text=True).strip()


# Apply to a dedicated translator worktree; never reset the caller's source.
OUT.mkdir(parents=True, exist_ok=True)
patched, current = tree_of(OUT / 'index.patched', PATCHES), tree_of(OUT / 'index.current', worktree=True)
if current == patched:
    pass   # the patched worktree of an earlier build
elif current == subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', pin + '^{tree}'], text=True).strip():
    for patch in PATCHES:
        subprocess.run(['git', '-C', str(SOURCE), 'apply', str(patch)], check=True)
else:
    raise SystemExit(f'{SOURCE} holds changes that are neither the pin nor the pin with the patch stack ({len(PATCHES)} patches)')
runtime_id = os.environ.get('NMB_RUNTIME_ID', 'upstream-rate-map-20261113')
# the runtime's example library and function-constant fixture, assembled to AIR for the bridge's self-tests
air, fc_air = OUT / 'runtime_examples.air', OUT / 'function_constant.air'
fixtures = SOURCE / 'crates/metal2vulkan-validation/fixtures/public'
# llvm-as names the module after its input as given: relative names keep the workspace's path out of the embedded AIR
subprocess.run([str(LLVM / 'llvm-as'), '-o', str(air), 'examples/runtime_examples.ll'], cwd=fixtures, check=True)
subprocess.run([str(LLVM / 'llvm-as'), '-o', str(fc_air), 'kernel_function_constant_gate_fold.ll'], cwd=fixtures, check=True)
# the GPU scanout's half-float conversion kernel (NativeMetal shaders/scanout_convert.ll, GpuScanoutPresenter.h)
scanout_air = OUT / 'scanout_convert.air'
subprocess.run([str(LLVM / 'llvm-as'), '-o', str(scanout_air), 'shaders/scanout_convert.ll'], cwd=NATIVE, check=True)
manifest = OUT / 'Cargo.toml'
# The same library wherever the workspace is (CI, setup-env.py): the sources are reached through links inside this workspace, so cargo
# hashes their packages by relative path (an absolute one went into every crate's metadata and symbol), and trim-paths drops the
# workspace, registry and sysroot paths from panic locations and debug information.
links = OUT / 'src'
links.mkdir(parents=True, exist_ok=True)
for name, target in (('NativeMetal', NATIVE), ('metal2vulkan', SOURCE)):
    if (links / name).is_symlink():
        (links / name).unlink()
    (links / name).symlink_to(target)
manifest.write_text('\n'.join([
    'cargo-features = ["trim-paths"]',
    '[package]', 'name = "native-metal-bridge"', 'version = "0.1.0"', 'edition = "2024"', '[workspace]', 'exclude = ["src"]',   # the translator's crates keep their own workspace
    '[lib]', 'crate-type = ["staticlib"]', 'path = "src/NativeMetal/bridge/NativeMetalBridge.rs"',
    '[dependencies]',
    'metal2vulkan = { path = "src/metal2vulkan/crates/metal2vulkan", features = ["ash"] }',
    'metal2vulkan-runtime = { path = "src/metal2vulkan/crates/metal2vulkan-runtime" }',
    'libc = "0.2"',
    # WindowServer's update thread spends much of a frame in the runtime's small functions across the translator's crates: one
    # optimisation unit with link-time optimisation inlines them across crate boundaries (as build-adreno-metal-bridge.py)
    '[profile.release]', 'panic = "unwind"', 'debug = 1', 'lto = "fat"', 'codegen-units = 1', 'trim-paths = "all"', '',
]))
# The crates.io versions are configs/metal-bridge.Cargo.lock's (cargo build --locked): a new resolution took newer ones
shutil.copyfile(ROOT / 'configs/metal-bridge.Cargo.lock', OUT / 'Cargo.lock')
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
    # MACOS_RUST_TOOLCHAIN: CI installs configs/env.lock.json's dated nightly (the dev machine's "nightly" is that one)
    result = subprocess.run(['cargo', '+' + os.environ.get('MACOS_RUST_TOOLCHAIN', 'nightly'), 'build', '--release', '--locked', '-Zbuild-std=std,panic_unwind', '-Zjson-target-spec', '--manifest-path',
                             str(manifest), '--target', str(TARGET_SPEC), '--target-dir', str(target_dir)], env=env, stdout=stream, stderr=subprocess.STDOUT,
                            timeout=3600)
if result.returncode:
    raise SystemExit(log.read_text()[-6000:])
library = OUT / 'libnative_metal_bridge.a'
shutil.copyfile(target_dir / TRIPLE / 'release/libnative_metal_bridge.a', library)
print(f'{library}: {library.stat().st_size} bytes (translator {pin[:12]})')
