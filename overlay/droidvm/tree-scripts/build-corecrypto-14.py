#!/usr/bin/env python3
"""Compile the pinned 2023 crypto provider internally for ABI verification.

Apple source, generated headers and objects remain ignored. This does not
register the provider, produce a certified module or demonstrate a kernel boot.
"""
import concurrent.futures
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from xnu_symbols import kernel_names
SOURCE = ROOT / 'refer/corecrypto-2023'
REVISION = '11fba65b12d8830630e248dfa8344caf8b065f26'
OUT = ROOT / 'build/corecrypto-2023'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--namespace', action='store_true', help='Isolate provider globals from XNU crypto wrappers')
args = parser.parse_args()


def names(path, mode):
    text = subprocess.check_output(['xcrun', 'nm', '-g', mode, '-j', path], text=True)
    return {line.strip() for line in text.splitlines() if line.startswith('_')}


if subprocess.check_output(['git', '-C', SOURCE, 'rev-parse', 'HEAD'], text=True).strip() != REVISION:
    raise SystemExit('Unexpected corecrypto source revision')
if subprocess.check_output(['git', '-C', SOURCE, 'status', '--porcelain'], text=True):
    raise SystemExit('The crypto reference must stay immutable')
OUT.mkdir(parents=True, exist_ok=True)
subprocess.run(['plutil', '-convert', 'json', '-o', OUT / 'project.json',
                SOURCE / 'corecrypto.xcodeproj/project.pbxproj'], check=True)
project = json.loads((OUT / 'project.json').read_text())
objects = project['objects']
parents = {child: key for key, value in objects.items() for child in value.get('children', [])}


def resolve(key):
    entry = objects[key]
    path = entry.get('path', '')
    if entry.get('sourceTree') == 'SOURCE_ROOT' or key not in parents:
        return SOURCE / path
    if entry.get('sourceTree') != '<group>':
        raise ValueError(f'Unsupported source tree: {entry}')
    return resolve(parents[key]) / path


target = next(value for value in objects.values() if value.get('isa') == 'PBXNativeTarget'
              and value.get('name') == 'corecrypto_kext')
phase = next(objects[key] for key in target['buildPhases'] if objects[key]['isa'] == 'PBXSourcesBuildPhase')
sources = [resolve(objects[key]['fileRef']) for key in phase['files']
           if objects[objects[key]['fileRef']].get('path', '').endswith('.c')]
for source in sources:
    if not source.is_file() or not source.resolve().is_relative_to(SOURCE.resolve()):
        raise SystemExit(f'Missing or unexpected source path: {source}')
include = OUT / 'include/corecrypto'
include.mkdir(parents=True, exist_ok=True)
for header in SOURCE.glob('*/corecrypto/*.h'):
    link = include / header.name
    if link.exists() and link.resolve() != header.resolve():
        raise SystemExit(f'Conflicting header: {header.name}')
    if not link.exists():
        link.symlink_to(header)
sdk = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path'], text=True).strip()
framework = ROOT / '.cache/fakeroot/System/Library/Frameworks/Kernel.framework/Versions/A'
command = ['xcrun', '--sdk', 'iphoneos', 'clang', '-target', 'arm64-apple-ios17.0', '-isysroot', sdk,
           '-mkernel', '-ffreestanding', '-fno-builtin', '-fno-stack-check', '-std=gnu99', '-fblocks', '-O2',
           '-fno-vectorize', '-fno-slp-vectorize', '-mno-implicit-float',
           '-DKERNEL=1', '-DKERNEL_PRIVATE=1', '-DBUILDKERNEL=1', '-DCC_USE_ASM=0', '-DNDEBUG=1',
           '-DCC_DISABLE_RSAKEYGEN=1', '-Wno-deprecated-declarations', '-Wno-incompatible-library-redeclaration',
           '-I' + str(include.parent), '-I' + str(framework / 'PrivateHeaders'), '-I' + str(framework / 'Headers')]
for folder in sorted({h.parent for h in SOURCE.rglob('*.h') if 'test' not in str(h.relative_to(SOURCE)).lower()}):
    command.extend(['-I', str(folder)])
variant = '-namespaced' if args.namespace else ''
if args.namespace:
    plain = OUT / 'libcorecrypto_kernel_noasm.a'
    if not plain.is_file():
        raise SystemExit('Build the plain provider once before creating its namespace')
    collisions = sorted(names(plain, '-U') & kernel_names(ROOT))
    if any(not name[1:].isidentifier() for name in collisions):
        raise SystemExit('A colliding symbol cannot be namespaced with a C identifier')
    header = OUT / 'namespace.h'
    header.write_text(''.join(f'#define {name[1:]} cc14_{name[1:]}\n' for name in collisions))
    command.extend(['-include', str(header)])
(OUT / f'compile-command{variant}.json').write_text(json.dumps(command, indent=2) + '\n')
object_dir = OUT / f'objects{variant}'
object_dir.mkdir(exist_ok=True)


# The sources are an immutable reference checkout, so an object whose compile command and source bytes are unchanged is reused
# (this project's overlay; the upstream script recompiles every source on each kernel build).
COMMAND_DIGEST = hashlib.sha256(json.dumps([str(part) for part in command]).encode()).hexdigest()


def compile_one(source):
    relative = str(source.relative_to(SOURCE))
    name = hashlib.sha256(relative.encode()).hexdigest()[:12] + '-' + source.stem
    destination = object_dir / (name + '.o')
    stamp = object_dir / (name + '.stamp')
    digest = hashlib.sha256(COMMAND_DIGEST.encode() + source.read_bytes()).hexdigest()
    if destination.is_file() and stamp.is_file() and stamp.read_text() == digest and (object_dir / (name + '.log')).is_file():
        return {'source': relative, 'object': destination.name, 'exit_code': 0, 'diagnostic': None}
    destination.unlink(missing_ok=True)
    result = subprocess.run([*command, '-c', source, '-o', destination], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    (object_dir / (name + '.log')).write_text(result.stdout)
    if result.returncode == 0:
        stamp.write_text(digest)
    return {'source': relative, 'object': destination.name, 'exit_code': result.returncode,
            'diagnostic': result.stdout[-2500:] if result.returncode else None}


with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
    results = list(executor.map(compile_one, sources))
failed = [result for result in results if result['exit_code']]
report = {'source_url': 'https://github.com/ONLYA/corecrypto-2023', 'source_revision': REVISION,
          'provenance': 'Third-party source snapshot; not authenticated against an Apple archive',
          'module_version': '14.0', 'target': 'arm64-apple-ios17.0', 'assembly_enabled': False,
          'compiled_sources': len(results), 'failures': len(failed), 'objects': results,
          'kernel_provider_registered': False, 'crypto_selftests_passed': False}
(OUT / f'build-report{variant}.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'{len(results)} kernel C sources; {len(failed)} failures', flush=True)
for result in failed[:8]:
    print(result['source'], result['diagnostic'], flush=True)
if failed:
    sys.exit(1)
for result in results:
    data = (object_dir / result['object']).read_bytes()
    magic, cpu, subtype, kind, count, size = struct.unpack_from('<6I', data)
    if (magic, cpu, subtype, kind) != (0xfeedfacf, 0x100000c, 0, 1):
        raise SystemExit(f'Wrong object architecture: {result["object"]}')
    offset = 32
    deployment = None
    for _ in range(count):
        cmd, length = struct.unpack_from('<II', data, offset)
        if cmd == 0x32:
            deployment = struct.unpack_from('<II', data, offset + 8)
        offset += length
    if deployment != (2, 0x110000):
        raise SystemExit(f'Wrong deployment: {result["object"]}: {deployment}')
archive = OUT / f'libcorecrypto_kernel_noasm{variant}.a'
archive.unlink(missing_ok=True)
subprocess.run(['xcrun', 'ar', 'rcs', archive, *[object_dir / result['object'] for result in results]], check=True)
defined = names(archive, '-U')
undefined = names(archive, '-u') - defined
kernel_exports = kernel_names(ROOT)
survey = {'unresolved_external_names': sorted(undefined), 'missing_kernel_names': sorted(undefined - kernel_exports),
          'duplicate_kernel_names': sorted(defined & kernel_exports), 'provider_registered': False,
          'abi_compatibility_proven': False}
(OUT / f'link-survey{variant}.json').write_text(json.dumps(survey, indent=2) + '\n')
report['object_architecture_and_deployment_audited'] = len(results)
report['archive_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
report['namespace_isolated'] = args.namespace
(OUT / f'build-report{variant}.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'Internal unregistered provider archive: {archive.name}')
print(f'External names absent from kernel: {survey["missing_kernel_names"]}')
print(f'Globals shared with kernel: {len(survey["duplicate_kernel_names"])}; initialization and intact selftests are still required')
