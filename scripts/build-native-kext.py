#!/usr/bin/env python3
"""Compile a driver as a relocatable arm64e kext object against the xnu-12377 build (same flags as the kernel's IOPlatformExpert.cpo).

    build-native-kext.py NAME SOURCE.cpp [SOURCE.cpp ...] [-I DIR ...] [--obj-link ios-obj-e]

Objects go to out/x12377/native-kexts/NAME/. scripts/kc-build.py --native links them into the kernel collection (the driver refers to
classes of kexts of the collection, so it cannot be linked into the kernel).
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
X = ROOT / 'out/x12377'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('name')
parser.add_argument('sources', nargs='+')
parser.add_argument('-I', dest='includes', action='append', default=[])
parser.add_argument('-D', dest='defines', action='append', default=[], help='NAME[=VALUE], or U:NAME to undefine')
parser.add_argument('--obj', default='e-obj', help='kernel object tree under out/x12377/build/xnu')
args = parser.parse_args()
tree = X / 'build/xnu' / args.obj / 'DEVELOPMENT_ARM64_BCM2837'
record = json.JSONDecoder().raw_decode((tree / 'iokit/DEVELOPMENT/IOPlatformExpert.cpo.json').read_text())[0]
out = X / 'native-kexts' / args.name
out.mkdir(parents=True, exist_ok=True)
objects = []
for source in args.sources:
    source = Path(source).resolve()
    destination = out / (source.stem + '.o')
    command, arguments, index = [], record['arguments'], 0
    while index < len(arguments):
        value = arguments[index]
        if value == record['file']:
            command.append(str(source))
        elif value == '-o':
            command += ['-o', str(destination)]
            index += 1
        elif value in ('-MF', '-MJ', '-MT', '-MQ'):
            index += 1
        elif value == '-Xclang' and arguments[index + 1].startswith('-W'):
            index += 1
        elif value not in ('-MD', '-MMD', '-MP', '-g') and not value.startswith('-W'):
            command.append(value)
        index += 1
    for include in args.includes:
        command += ['-I', include]
    for define in args.defines:
        command += ['-U', define[2:]] if define.startswith('U:') else ['-D', define]
    command += ['-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', '-Wno-c99-designator', '-Wno-reorder-init-list',
                '-Wno-deprecated-enum-enum-conversion', '-Wno-unnecessary-virtual-specifier', '-Wno-missing-designated-field-initializers']
    env = dict(os.environ, CCC_OVERRIDE_OPTIONS='+-Wno-error=missing-designated-field-initializers')
    result = subprocess.run(command, cwd=record['directory'], capture_output=True, text=True, env=env)
    if result.returncode:
        sys.exit(result.stdout + result.stderr)
    objects.append(str(destination))
(out / 'objects.json').write_text(json.dumps(objects, indent=1) + '\n')
print(f'{args.name}: {len(objects)} object(s) in {out}')
