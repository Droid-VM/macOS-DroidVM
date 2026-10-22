#!/usr/bin/env python3
"""Start the isolated, pinned Darling runtime for this workspace."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TC = ROOT / 'toolchains/linux'
IMAGE = 'sha256:34c45909102c90bc2ae66c98e690d038f479255966c814b59d284004f0185dbf'
NAME = 'macos-appleclang'


def run(*args):
    return subprocess.check_output([str(x) for x in args], text=True).strip()


def main():
    path = TC / 'bin/linux-toolchain.json'
    config = json.loads(path.read_text())
    runtime = config['appleclang']['kernel_runtime']
    if hashlib.sha256(Path(runtime['path']).read_bytes()).hexdigest() != runtime['sha256']:
        raise ValueError('kernel compiler runtime hash mismatch')
    prefix = TC / 'darling-home'
    prefix.mkdir(exist_ok=True)
    mounts = {str(ROOT): str(ROOT), '/opt/apple': str(TC / 'appleclang/apple-tools'),
              '/home/builder': str(prefix)}
    exists = subprocess.run(['docker', 'inspect', NAME], capture_output=True)
    if exists.returncode:
        command = ['docker', 'run', '-d', '--name', NAME, '--cap-add', 'SYS_ADMIN',
                   '--cap-add', 'SYS_PTRACE', '--security-opt', 'seccomp=unconfined',
                   '--security-opt', 'apparmor=unconfined', '--ulimit', 'nofile=524288:524288']
        for target, source in mounts.items():
            command += ['--mount', f'type=bind,source={source},target={target}' +
                        (',readonly' if target == '/opt/apple' else '')]
        run(*command, IMAGE)
    info = json.loads(run('docker', 'inspect', NAME))[0]
    actual = {x['Destination']: x['Source'] for x in info['Mounts']}
    if info['Image'] != IMAGE or actual != mounts:
        raise ValueError('existing runtime does not match image/workspace; refusing to reuse it')
    if not info['State']['Running']:
        run('docker', 'start', NAME)
    shell = ['docker', 'exec', NAME, 'timeout', '60', 'darling', 'shell']
    run(*shell, '/bin/mkdir', '-p', ROOT.parent)
    run(*shell, '/bin/bash', '-c',
        'if [ -e "$1" ]; then [ "$(readlink "$1")" = "$2" ]; else ln -s "$2" "$1"; fi',
        'workspace-link', ROOT, '/Volumes/SystemRoot' + str(ROOT))
    mldr = json.loads(run('docker', 'exec', NAME, 'cat', '/usr/share/darling-mldr-source.json'))
    digest = run('docker', 'exec', NAME, 'sha256sum',
                 '/usr/libexec/darling/usr/libexec/darling/mldr').split()[0]
    if digest != config['appleclang']['mldr']['binary_sha256']:
        raise ValueError('Darling mldr binary differs from fixed reference')
    config['appleclang'].update(image_id=IMAGE, container=NAME, workspace=str(ROOT))
    path.write_text(json.dumps(config, indent=2) + '\n')
    (TC / 'runtime.json').write_text(json.dumps({
        'image': IMAGE, 'container': NAME, 'mounts': mounts, 'mldr': mldr,
        'mldr_sha256': digest}, indent=2) + '\n')
    sys.path.insert(0, str(ROOT / 'compat/xnu-linux/scripts'))
    from probe_xnu_compiler import probe
    result = probe(TC / 'bin', ROOT / 'out/linux/compiler-probe')
    if not result['ready']:
        raise ValueError('XNU compiler probe failed')
    print('Isolated runtime ready; XNU compiler extensions verified')


if __name__ == '__main__':
    main()
