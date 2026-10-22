#!/usr/bin/env python3
"""Prepare and build a reference kernel in an isolated Linux tree (not a bootable macOS image)."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out/linux'
UNIXNU = OUT / 'UniXNU'
DEVICE = OUT / 'device-reference'
BUILD = OUT / 'reference'
TREE = BUILD / 'droidvm/tree'
TC = ROOT / 'toolchains/linux'
COMPAT = ROOT / 'compat'


def run(*command, **kwargs):
    print('+', ' '.join(map(str, command)), flush=True)
    subprocess.run([str(x) for x in command], check=True, **kwargs)


def environment():
    env = dict(os.environ)
    for name, path in [('TMPDIR', OUT / 'tmp'), ('XDG_CACHE_HOME', OUT / 'cache')]:
        path.mkdir(parents=True, exist_ok=True)
        env[name] = str(path)
    env.update(GUNYAH_APPLE_TARGET='arm64-apple-ios17.0', GUNYAH_LINUX_BIN=str(TC / 'bin'))
    env['LZFSE_LIB'] = str(OUT / 'liblzfse.so')
    env['PATH'] = os.pathsep.join(map(str, [COMPAT / 'droidvm-linux/shims', TC / 'bin',
                                         TC / 'host-deps/usr/bin', '/usr/lib/llvm-21/bin', env['PATH']]))
    env['PYTHONPATH'] = os.pathsep.join(map(str, [COMPAT / 'droidvm-linux/pyhook', TC / 'python-deps']))
    return env


def unixnu(*args, env):
    run(sys.executable, UNIXNU / 'unixnu', *args, '-D', DEVICE, '--out', BUILD, cwd=UNIXNU, env=env)


def apply(target, patch):
    reverse = subprocess.run(['git', '-C', str(target), 'apply', '--reverse', '--check', str(patch)], capture_output=True)
    if reverse.returncode:
        run('git', '-C', target, 'apply', '--check', patch)
        run('git', '-C', target, 'apply', patch)


def prepare():
    run(sys.executable, ROOT / 'scripts/prepare-sources.py', '--check')
    env = environment()
    src = ROOT / 'sources/lzfse/src'
    run('cc', '-O2', '-shared', '-fPIC', '-I', src,
        *(src / name for name in ('lzfse_decode.c', 'lzfse_decode_base.c', 'lzfse_fse.c', 'lzvn_decode_base.c')),
        '-o', OUT / 'liblzfse.so', env=env)
    if not UNIXNU.exists():
        shutil.copytree(ROOT / 'sources/UniXNU', UNIXNU, symlinks=True)
    if not DEVICE.exists():
        shutil.copytree(ROOT / 'sources/UniXNU-droidvm', DEVICE, symlinks=True)
        run(sys.executable, ROOT / 'scripts/make-reference-device.py', DEVICE, 'droidvm_defconfig')
    for patch in sorted((COMPAT / 'xnu-linux/linux/project-patches').glob('*.patch')):
        apply(UNIXNU, patch)
    run(sys.executable, COMPAT / 'droidvm-linux/bootstrap-skip-checks.py', UNIXNU / 'scripts/build-xnu-4k-baseline.sh')
    firehose = ('#!/usr/bin/env bash\nset -euo pipefail\n'
                'exec python3 "$GUNYAH_LINUX_DEVICE/scripts/build-firehose-linux.py" '
                '--tree "$(cd "$(dirname "$0")/.." && pwd)"\n')
    (UNIXNU / 'scripts/build-firehose.sh').write_text(firehose)
    unixnu('defconfig', 'droidvm_defconfig', env=env)
    unixnu('fetch', env=env)
    # The bare `tree` command intentionally omits refer/ dependencies. Assemble
    # with the kernel's reference set without attempting a link/prelink first.
    run(sys.executable, '-c',
        'import sys; sys.path.insert(0, sys.argv.pop(1)); '
        'from unixnu.cli import Context, parser, prepare; '
        'prepare(Context(parser().parse_args(sys.argv[1:])), ("kernel",))',
        UNIXNU / 'scripts', 'tree', '-D', DEVICE, '--out', BUILD, cwd=UNIXNU, env=env)
    work = TREE / '.cache/xnu-work'
    if not work.exists():
        run('git', 'clone', '--no-hardlinks', TREE / 'refer/xnu', work)
        for directory in (TREE / 'patches/xnu', TREE / 'kits/NativePrelink/patches'):
            for patch in sorted(directory.glob('*.patch')):
                apply(work, patch)
    cache = TREE / '.cache/sources'
    cache.mkdir(parents=True, exist_ok=True)
    for key, path, tag in (
        ('xnu-driverkit-10063.121.3', 'iokit/DriverKit', 'xnu-10063.121.3'),
        ('xnu-driverkit-crypto-10063.121.3', 'iokit/DriverKit/crypto', 'xnu-10063.121.3'),
        ('xnu-trustcache-8796.101.5', 'EXTERNAL_HEADERS/TrustCache', 'xnu-8796.101.5'),
    ):
        data = subprocess.check_output(['gh', 'api', f'repos/apple-oss-distributions/xnu/contents/{path}?ref={tag}'])
        json.loads(data)
        (cache / f'{key}.json').write_bytes(data)
    run(sys.executable, COMPAT / 'droidvm-linux/seed_headers.py', TREE, env=env)
    sys.path.insert(0, str(COMPAT / 'xnu-linux/scripts'))
    spec = importlib.util.spec_from_file_location('linux_adapter', COMPAT / 'xnu-linux/scripts/build-linux.py')
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    _, overrides = adapter.prepare(TREE, TC, TC / 'host-deps', TC / 'bin/target-iig')
    (OUT / 'linux-env.json').write_text(json.dumps(overrides, indent=2) + '\n')
    print('Prepared reference tree; full macOS root/owner policies are separate inputs')


def build(jobs):
    if jobs < 1:
        raise ValueError('jobs must be positive')
    env = environment()
    overrides = json.loads((OUT / 'linux-env.json').read_text())
    env.update({k: v for k, v in overrides.items() if k not in ('PATH', 'PYTHONPATH')})
    unixnu('build', 'kernel', '-j', str(jobs), env=env)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'build'])
    parser.add_argument('-j', '--jobs', type=int, default=8)
    args = parser.parse_args()
    prepare() if args.command == 'prepare' else build(args.jobs)
