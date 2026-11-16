#!/usr/bin/env python3
"""Prepare the pinned, patched Darling loader for the AppleClang Docker image."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

DEVICE = Path(__file__).resolve().parents[1]
COMMIT = json.loads((DEVICE / 'linux/appleclang-sources.json').read_text())['darling']['commit']
SUBMODULES = ('architecture', 'cctools', 'xnu', 'darlingserver')


def run(*args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def prepare(context, cache):
    source = cache / 'darling-mldr-source'
    if not source.exists():
        run('git', 'clone', '--filter=blob:none', '--no-checkout',
            'https://github.com/darlinghq/darling.git', source)
        run('git', '-C', source, 'sparse-checkout', 'set', 'src/startup/mldr',
            'basic-headers', 'Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/usr/include')
        run('git', '-C', source, 'checkout', '--detach', COMMIT)
    head = run('git', '-C', source, 'rev-parse', 'HEAD', capture_output=True, text=True).stdout.strip()
    if head != COMMIT:
        raise ValueError(f'Unexpected Darling source commit: {head}')
    run('git', '-C', source, 'diff', '--exit-code', 'HEAD')
    run('git', '-C', source, 'submodule', 'update', '--init', '--depth', '1',
        *('src/external/' + name for name in SUBMODULES))
    for name in SUBMODULES:
        run('git', '-C', source / 'src/external' / name, 'diff', '--exit-code', 'HEAD')
    destination = context / 'darling-mldr'
    if destination.exists():
        shutil.rmtree(destination)
    # Resolve the SDK's symlink headers. Unused headers from other submodules
    # are absent; a required missing header will fail the C compilation.
    def absent(directory, names):
        return [name for name in names if not (Path(directory) / name).exists()]
    shutil.copytree(source / 'src/startup/mldr', destination / 'src/startup/mldr', ignore=absent)
    server = source / 'src/external/darlingserver'
    shutil.copytree(server / 'include', destination / 'server/include')
    patch = DEVICE / 'linux/darling-patches/darling-mldr-address-space.patch'
    run('patch', '-p1', '-i', patch, cwd=destination)
    build = destination / 'build'
    for name in ('include/darlingserver', 'internal-include/darlingserver', 'src'):
        (build / name).mkdir(parents=True, exist_ok=True)
    run('python3', server / 'scripts/generate-rpc-wrappers.py',
        build / 'include/darlingserver/rpc.h', build / 'internal-include/darlingserver/rpc.internal.h',
        build / 'src/rpc.c', '"../include/darlingserver/rpc.h"')
    (build / 'darling-config.h').write_text('#define SYSTEM_ROOT "/Volumes/SystemRoot"\n')
    shutil.copy2(source / 'src/startup/rtsig.c', destination / 'rtsig.c')
    shutil.copy2(DEVICE / 'linux/build-darling-mldr.sh', destination / 'build.sh')
    record = {'darling_commit': COMMIT, 'patch_sha256': hashlib.sha256(patch.read_bytes()).hexdigest()}
    (destination / 'source.json').write_text(json.dumps(record, indent=2) + '\n')
