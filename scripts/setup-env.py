#!/usr/bin/env python3
"""The k27 build environment from public sources (configs/env.lock.json, docs/ci-env-plan.md), into this workspace.

    setup-env.py host                 print the apt packages and the rust toolchain the lock wants (install them yourself / in CI)
    setup-env.py toolchain [--jobs N] toolchains/: the SDKs, cctools-port and MIG (Linux Mach-O tools), AppleClang's CLTools in a
                                      Darling container (ld-classic), toolchains/linux/bin26 (the kernel's compiler adapters)
    setup-env.py x12377 [--jobs N]    out/x12377 and out/k27/xnu, the kernel's build environment: the k27 tree (xnu + patches/xnu-12377,
                                      git am), gunyah-linux.mk, the headers-only SDK root fakeroot (AvailabilityVersions, libplatform,
                                      libdispatch, the tree's installhdrs, libfirehose_kernel.a), the KDK headers, ArmCpu/ArmDTPlatform,
                                      inc-hid (needs toolchain)
    setup-env.py sources [--jobs N]   sources/: UniXNU (and the drivers, kits and metal2vulkan the product builds), Turnip's UniXNU and
                                      patched Mesa, UniXNU-droidvm, edk2, linux-apfs-rw, apfsprogs; mkapfs/apfsck, apfs.ko (for the
                                      running kernel), ipsw; artifacts/boot-inputs (UniXNU.efi and DarwinBoot.efi built from source)

Each step skips what is there already and verifies what it downloads. The tools of compat/xnu-linux are the ios workspace's
(UniXNU-gunyah 9843a07), copied: that repository is not public."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'configs/env.lock.json').read_text())
COMPAT = ROOT / 'compat/xnu-linux'


def run(*args, **kwargs):
    print('+', ' '.join(str(a) for a in args), flush=True)
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def sha256(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(entry):
    target = ROOT / entry['to']
    if not (target.exists() and sha256(target) == entry['sha256']):
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + '.download')
        print(f'download {entry["url"]}', flush=True)
        with urllib.request.urlopen(entry['url'], timeout=120) as response, open(partial, 'wb') as output:
            shutil.copyfileobj(response, output, 1 << 20)
        if sha256(partial) != entry['sha256']:
            raise SystemExit(f'{entry["url"]}: sha256 differs from the lock')
        partial.replace(target)
    return target


def git_pinned(entry):
    """A checkout of the pinned commit, verified; an existing one is checked, never reset. The lock entry may also ask for: sparse
    (directories), also (more commits fetched, for git show), submodules (paths, at the commits the tree records), am (a patch
    directory, git am) or apply (git apply) on a new checkout, ancestor (HEAD may descend from the commit: patched, or a branch on it)."""
    path = ROOT / entry['path']
    if not (path / '.git').exists():
        if path.exists() and any(path.iterdir()):
            raise SystemExit(f'{path}: not empty and not a checkout')
        path.mkdir(parents=True, exist_ok=True)
        git = ['git', '-C', path]
        run(*git, 'init', '-q')
        run(*git, 'remote', 'add', 'origin', entry['url'])
        if entry.get('sparse'):
            run(*git, 'sparse-checkout', 'set', *entry['sparse'])
        run(*git, 'fetch', '-q', '--depth', '1', *(['--filter=blob:none'] if entry.get('sparse') else []), 'origin', entry['commit'])
        run(*git, 'checkout', '-q', '--detach', 'FETCH_HEAD')
        if entry.get('also'):
            run(*git, 'fetch', '-q', '--depth', '1', 'origin', *entry['also'])
        if entry.get('submodules'):
            run(*git, 'submodule', 'update', '-q', '--init', '--depth', '1', '--', *entry['submodules'])
        if entry.get('am'):
            run(*git, '-c', 'user.name=setup-env', '-c', 'user.email=setup-env@localhost', 'am', '-q',
                *sorted((ROOT / entry['am']).glob('*.patch')))
        for patch in sorted((ROOT / entry['apply']).glob('*.patch')) if entry.get('apply') else ():
            run(*git, 'apply', patch)
    head = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
    if head != entry['commit'] and not (entry.get('ancestor') and subprocess.run(
            ['git', '-C', str(path), 'merge-base', '--is-ancestor', entry['commit'], 'HEAD']).returncode == 0):
        raise SystemExit(f'{path}: at {head}, the lock wants {entry["commit"]}')
    for name, digest in entry.get('check', {}).items():
        if sha256(path / name) != digest:
            raise SystemExit(f'{path / name}: sha256 differs from the lock')
    return path


def host(_args):
    print('apt-get install -y ' + ' '.join(LOCK['host']['apt']) + ' linux-headers-$(uname -r)')
    rust = LOCK['host']['rust']
    print(f'rustup toolchain install {rust["toolchain"]} --profile minimal --component {",".join(rust["components"])}')


def sdks():
    entry = LOCK['downloads']['macosx-sdk']
    archive = download(entry)
    sdk = ROOT / entry['extract'] / 'MacOSX26.1.sdk'
    if not (sdk / 'SDKSettings.json').exists():
        run('tar', '-C', ROOT / entry['extract'], '-xf', archive)
    git_pinned(LOCK['git']['ios-sdks'])


def toolchain(args):
    spec = dict(LOCK['toolchain'])
    # Another workspace on a machine that has one already (a clean-room check) takes a container and image of its own.
    spec['container'] = os.environ.get('MACOS_DARLING_CONTAINER', spec['container'])
    spec['image'] = os.environ.get('MACOS_DARLING_IMAGE', spec['image'])
    linux = ROOT / spec['linux']
    sdk = ROOT / spec['sdk']
    llvm = LOCK['host']['llvm']['bin']
    sdks()
    # cctools-port (ld64, ar, libtool, ...) and MIG built for Linux, openstep_parser, the adapters in bin/ and bin/linux-toolchain.json
    sources = ROOT / 'toolchains/linux-sources'
    run(sys.executable, COMPAT / 'scripts/setup-linux.py', 'fetch', '--sources', sources)
    if not (linux / 'bin/linux-toolchain.json').exists():
        run(sys.executable, COMPAT / 'scripts/setup-linux.py', 'build', '--sources', sources, '--sdk', sdk, '--output', linux,
            '--llvm-bin', llvm, '--jobs', args.jobs)
    # AppleClang 15 (CLTools) unpacked, never installed, and the Darling image and container it runs in; configure records the
    # container in bin/linux-toolchain.json and proves the compiler on the kernel's typed-allocation probes.
    apple = linux / 'appleclang'
    apple.mkdir(parents=True, exist_ok=True)
    tool = [sys.executable, COMPAT / 'scripts/setup-appleclang.py']
    run(*tool, 'fetch', '--directory', apple)
    if not (apple / 'apple-tools').exists():
        run(*tool, 'extract', '--directory', apple)
    if subprocess.run(['docker', 'image', 'inspect', spec['image']], capture_output=True).returncode:
        run(*tool, 'image', '--directory', apple, '--image', spec['image'])
    if subprocess.run(['docker', 'inspect', spec['container']], capture_output=True).returncode:
        run(*tool, 'start', '--directory', apple, '--image', spec['image'], '--container', spec['container'], '--workspace', ROOT)
    config = json.loads((linux / 'bin/linux-toolchain.json').read_text())
    if 'appleclang' not in config:
        run(*tool, 'configure', '--directory', apple, '--toolchain', linux)
    # ld-classic, the user-space linker (scripts/apple-ld.py), from the same CLTools package
    run(sys.executable, ROOT / 'scripts/apple-ld.py', 'install')
    # bin26: the kernel's adapters, on the host's LLVM 21 (native_compile) against the iPhoneOS 26.5 SDK
    bin26 = linux / 'bin26'
    bin26.mkdir(exist_ok=True)
    for name in ('xcrun', 'target-clang', 'target-clang++', 'target-iig', 'plutil', 'ditto'):
        link = bin26 / name
        if not link.is_symlink():
            link.symlink_to(COMPAT / 'linux/darwin-tool.py')
    config = json.loads((linux / 'bin/linux-toolchain.json').read_text())
    settings = json.loads((sdk / 'SDKSettings.json').read_text())
    config.update(spec['bin26'], sdk=str(sdk), sdk_version=settings['Version'],
                  sdk_settings_sha256=sha256(sdk / 'SDKSettings.json'))
    (bin26 / 'linux-toolchain.json').write_text(json.dumps(config, indent=2) + '\n')
    print(f'toolchain ready: {linux}')


X = ROOT / 'out/x12377'
DEV_ROOT = '/home/qiuqiu/crosvm/macos'   # the workspace the committed gunyah-linux.mk was generated in


def kernel_tree():
    """out/k27/xnu: xnu with the series applied (git am) as branch k27, a worktree of out/x12377/xnu-m; its tree must be the lock's."""
    spec = LOCK['x12377']
    source = git_pinned(LOCK['git']['xnu'])   # out/x12377/xnu-m, pristine (build-firehose.sh reads its EXTERNAL_HEADERS)
    tree = ROOT / 'out/k27/xnu'
    if not tree.exists():
        tree.parent.mkdir(parents=True, exist_ok=True)
        run('git', '-C', source, 'worktree', 'add', '-q', '-b', 'k27', tree, LOCK['git']['xnu']['commit'])
        series = [path for pattern in spec['series'] for path in sorted((ROOT / spec['patches']).glob(pattern))]
        run('git', '-C', tree, '-c', 'user.name=setup-env', '-c', 'user.email=setup-env@localhost', 'am', '-q',
            '--committer-date-is-author-date', *series)
    actual = subprocess.check_output(['git', '-C', str(tree), 'rev-parse', 'HEAD^{tree}'], text=True).strip()
    if actual != spec['k27_tree']:
        raise SystemExit(f'{tree}: tree {actual}, the lock wants {spec["k27_tree"]} (patches/xnu-12377 changed: update the lock)')


def gunyah_mk():
    """out/x12377/gunyah-linux.mk (k27/x12377/build-kernel.sh): the tree's committed one, generated in another workspace, with this
    workspace's paths, the host's packages for the host-deps it named and this machine's memory and CPUs."""
    text = (ROOT / 'out/k27/xnu/gunyah-linux.mk').read_text()
    # host-deps were a private copy of the host's libbsd/libmd/pax/unifdef: the system's (env.lock.json host.apt) are the same
    for include in ('/usr/include/x86_64-linux-gnu', '/usr/include'):
        text = text.replace(f' -I{DEV_ROOT}/toolchains/linux/host-deps{include}', '')
    text = text.replace(DEV_ROOT + '/toolchains/linux/host-deps', '').replace(DEV_ROOT, str(ROOT))
    lines = []
    for line in text.splitlines():
        if line.startswith('override MEMORY_SIZE :='):
            line = f'override MEMORY_SIZE := {os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")}'
        elif line.startswith(('override SYSCTL_HW_PHYSICALCPU :=', 'override SYSCTL_HW_LOGICALCPU :=')):
            line = line.split(':=')[0] + f':= {os.cpu_count()}'
        lines.append(line)
    (X / 'gunyah-linux.mk').write_text('\n'.join(lines) + '\n')


def fakeroot(output, jobs):
    """The headers-only SDK root the kernel compiles against (KERNEL_SDKROOT): AvailabilityVersions installed, libplatform's and
    libdispatch's headers, the k27 tree's installhdrs and libfirehose_kernel.a."""
    if (output / 'usr/local/lib/kernel-arm64e/libfirehose_kernel.a').exists():
        return
    logs = X / 'build/fakeroot-logs'
    logs.mkdir(parents=True, exist_ok=True)
    run('make', '-C', X / 'refer-AvailabilityVersions', 'install', f'-j{jobs}', f'OBJROOT={X / "build/availability"}',
        f'SYMROOT={X / "build/availability"}', f'DSTROOT={output}', 'CMAKE=/usr/bin/cmake', 'NINJA=/usr/bin/ninja',
        stdout=open(logs / 'availability.log', 'w'), stderr=subprocess.STDOUT)
    # xnu's make reads both from SDKROOT (bsd/sys/make_symbol_aliasing.sh): the iOS SDK gets them too, as the dev SDK had them
    sdk = ROOT / LOCK['toolchain']['sdk']
    for name in ('usr/local/libexec/availability.pl', 'usr/include/AvailabilityVersions.h'):
        (sdk / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output / name, sdk / name)
    for source, destination in (('include', 'usr/local/include'), ('private', 'usr/local/include'),
                                ('private/platform', 'System/Library/Frameworks/Kernel.framework/Versions/A/PrivateHeaders/platform')):
        shutil.copytree(X / 'refer-libplatform' / source, output / destination, dirs_exist_ok=True, symlinks=True)
    headers = output / 'usr/local/include/os'
    headers.mkdir(parents=True, exist_ok=True)
    for header in (X / 'refer-libdispatch/os').glob('*.h'):
        result = subprocess.run(['unifdef', '-DKERNEL=1', '-DOS_FIREHOSE_SPI=1', '-DOS_VOUCHER_ACTIVITY_SPI_TYPES=1',
                                 '-UOS_VOUCHER_ACTIVITY_SPI', str(header)], capture_output=True)
        if result.returncode not in (0, 1):
            raise SystemExit(result.stderr.decode())
        (headers / header.name).write_bytes(result.stdout)
    (output / 'AppleInternal').mkdir(exist_ok=True)
    # The tree's exported headers, made by the kernel's own build into build/xnu/hdrs-dst. Its iig outputs come from k27/iig (Apple's
    # iig is Xcode's, not public), newer than their sources so make keeps them, as k27/build-kernel27.sh does for the kernel.
    for source in (ROOT / 'k27/iig').rglob('*'):
        if source.is_file():
            target = X / 'build/xnu/hdrs-obj' / source.relative_to(ROOT / 'k27/iig')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source, target)
    env = dict(os.environ, XNU_BUILD_TARGET='installhdrs', XNU_TREE='../k27/xnu', XNU_OBJ='hdrs', XNU_ARCH='arm64e',
               JOBS=str(jobs),
               XNU_DEPLOYMENT_TARGET_FLAGS='-miphoneos-version-min=26.0 -DXNU_TARGET_OS_OSX')
    run('bash', ROOT / 'k27/x12377/build-kernel.sh', env=env, stdout=open(logs / 'installhdrs.log', 'w'), stderr=subprocess.STDOUT)
    run('cp', '-a', str(X / 'build/xnu/hdrs-dst') + '/.', output)
    run('bash', ROOT / 'k27/x12377/build-firehose.sh', env=dict(os.environ, XNU_ARCH='arm64e'))


def kdk():
    """out/x12377/kdk: CoreEntitlements, TrustCache, CodeSignature and TrustedExecutionMonitor headers of the KDK (nothing else)."""
    script = download(LOCK['downloads']['kdk-headers.py'])
    dmg = download(LOCK['downloads']['kdk'])
    temporary = X / 'build/tmp'   # the pkg is 1 GB, more than a small /tmp holds
    temporary.mkdir(parents=True, exist_ok=True)
    run(sys.executable, script, '--dmg', dmg, '--sha256', LOCK['downloads']['kdk']['sha256'], X / 'kdk',
        env=dict(os.environ, TMPDIR=str(temporary)))


def inc_hid():
    """out/x12377/inc-hid: the macOS SDK's HID and graphics kernel headers, for DroidVMInput (configs' kexts)."""
    kernel = ROOT / 'toolchains/sdks/MacOSX26.1.sdk/System/Library/Frameworks/Kernel.framework/Headers'
    links = {'HIDDriverKit': kernel / 'HIDDriverKit', 'TargetConditionals.h': ROOT / 'toolchains/sdks/MacOSX26.1.sdk/usr/include/TargetConditionals.h',
             'IOKit/graphics': kernel / 'IOKit/graphics', 'IOKit/hidsystem': kernel / 'IOKit/hidsystem', 'IOKit/hid': kernel / 'IOKit/hid'}
    for name, target in links.items():
        link = X / 'inc-hid' / name
        link.parent.mkdir(parents=True, exist_ok=True)
        if not link.is_symlink():
            link.symlink_to(target)


def x12377(args):
    X.mkdir(parents=True, exist_ok=True)
    for name in ('refer-libdispatch', 'refer-libplatform', 'refer-AvailabilityVersions', 'ArmCpu', 'ArmDTPlatform'):
        git_pinned(LOCK['git'][name])
    for name in ('ArmCpu', 'ArmDTPlatform'):
        (X / 'un/build/platform-12377-arm64e' / name).mkdir(parents=True, exist_ok=True)
    kernel_tree()
    gunyah_mk()
    fakeroot(X / 'fakeroot', args.jobs)
    kdk()
    inc_hid()
    print(f'kernel environment ready: {X}')


SOURCES = ('UniXNU', 'NativeMetal', 'NativeAdreno', 'DarwinBoot', 'NativeAES', 'NativeRamBlock', 'VerifiedRoot', 'AdrenoPM4', 'ArmSmmu4K',
           'metal2vulkan', 'UniXNU-turnip', 'mesa', 'UniXNU-droidvm', 'edk2', 'linux-apfs-rw', 'apfsprogs')


def mesa():
    """Turnip's Mesa: the pins of UniXNU-turnip's scripts/data/adreno-compiler-inputs.json, their patches applied on a new checkout."""
    entry = LOCK['git']['mesa']
    turnip = ROOT / LOCK['git']['UniXNU-turnip']['path']
    pins = json.loads((turnip / 'scripts/data/adreno-compiler-inputs.json').read_text())
    if pins['mesa']['commit'] != entry['commit']:
        raise SystemExit(f'UniXNU-turnip pins Mesa {pins["mesa"]["commit"]}, the lock {entry["commit"]}: update the lock')
    new = not (ROOT / entry['path'] / '.git').exists()
    path = git_pinned(entry)
    if new:
        for patch in pins['patches']:
            run('git', '-C', path, 'apply', turnip / patch)


def unixnu_efi(args):
    """artifacts/boot-inputs/UniXNU.efi, built from sources/UniXNU/package (out/unixnu-efi), and its provenance entry."""
    inputs = ROOT / 'artifacts/boot-inputs'
    inputs.mkdir(parents=True, exist_ok=True)
    work = ROOT / 'out/unixnu-efi'
    run('bash', ROOT / LOCK['git']['UniXNU']['path'] / 'package/build.sh', '-b', 'DEBUG', '-t', 'CLANGPDB', stdout=subprocess.DEVNULL,
        env=dict(os.environ, UNIXNU_EDK2=str(ROOT / 'sources/edk2'), UNIXNU_BUILD_DIR=str(work), CLANG_BIN=LOCK['host']['llvm']['bin'] + '/',
                 JOBS=str(args.jobs)))
    target = inputs / 'UniXNU.efi'
    shutil.copyfile(work / 'Build/Out/AARCH64-DEBUG/UniXNU.efi', target)
    provenance = inputs / 'provenance.json'
    record = json.loads(provenance.read_text()) if provenance.exists() else {}
    record['UniXNU.efi'] = {'sha256': sha256(target), 'bytes': target.stat().st_size,
                            'source': f"sources/UniXNU/package/build.sh (DEBUG, CLANGPDB): UniXNU {LOCK['git']['UniXNU']['commit']}, "
                                      f"edk2 {LOCK['git']['edk2']['commit']}, LLVM {LOCK['host']['llvm']['version']}"}
    provenance.write_text(json.dumps(record, indent=2) + '\n')


def sources(args):
    for name in SOURCES:
        mesa() if name == 'mesa' else git_pinned(LOCK['git'][name])
    # The disk tools: mkapfs and apfsck, and apfs.ko for the running kernel (its headers: linux-headers-$(uname -r))
    run('make', '-C', ROOT / 'sources/apfsprogs/mkapfs', f'-j{args.jobs}', stdout=subprocess.DEVNULL)
    run('make', '-C', ROOT / 'sources/apfsprogs/apfsck', f'-j{args.jobs}', stdout=subprocess.DEVNULL)
    if not (ROOT / 'sources/linux-apfs-rw/apfs.ko').exists():
        # a kernel built by clang wants its modules built by clang (gcc refuses its flags)
        clang = 'clang' in Path('/proc/version').read_text()
        run('make', '-C', ROOT / 'sources/linux-apfs-rw', f'-j{args.jobs}', *(['LLVM=1'] if clang else []), stdout=subprocess.DEVNULL,
            env=dict(os.environ, PATH=LOCK['host']['llvm']['bin'] + os.pathsep + os.environ['PATH']))
    # ipsw (blacktop/ipsw): AEA keys and decryption, IM4P (product.py inputs)
    archive = download(LOCK['downloads']['ipsw'])
    if not (ROOT / LOCK['downloads']['ipsw']['extract'] / 'ipsw').exists():
        run('tar', '-C', ROOT / LOCK['downloads']['ipsw']['extract'], '-xzf', archive, 'ipsw')
    # The boot loaders from source: UniXNU.efi (UniXNU's package/build.sh, here on the locked edk2 and LLVM 21 instead of its
    # default Mu_Basecore checkout; the strings of the binary match the published one's) and DarwinBoot.efi (edk2's BaseTools first)
    unixnu_efi(args)
    if not (ROOT / 'sources/edk2/BaseTools/Source/C/bin/GenFw').exists():
        run('make', '-C', ROOT / 'sources/edk2/BaseTools', f'-j{args.jobs}', stdout=subprocess.DEVNULL)
    run(sys.executable, ROOT / 'scripts/build-darwinboot.py', stdout=subprocess.DEVNULL)
    print('sources ready')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='step', required=True)
    sub.add_parser('host').set_defaults(func=host)
    step = sub.add_parser('toolchain')
    step.add_argument('--jobs', type=int, default=os.cpu_count())
    step.set_defaults(func=toolchain)
    step = sub.add_parser('sources')
    step.add_argument('--jobs', type=int, default=os.cpu_count())
    step.set_defaults(func=sources)
    step = sub.add_parser('x12377')
    step.add_argument('--jobs', type=int, default=os.cpu_count())
    step.set_defaults(func=x12377)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
