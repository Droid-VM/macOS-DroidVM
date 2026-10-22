#!/usr/bin/env python3
"""Create and independently verify a local owner policy; no encrypted CI inputs required."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / 'sources/UniXNU/kits/VerifiedRoot'


def local(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('inputs and outputs must be inside macos')
    return path


def run(*args):
    subprocess.run([str(a) for a in args], check=True, capture_output=True)


def main(args):
    image, keys, output = map(local, (args.image, args.key_dir, args.output))
    if not image.is_file() or image.stat().st_size <= 0:
        raise ValueError('image must be a nonempty regular file')
    if args.generation <= 0 or output.exists():
        raise ValueError('generation must be positive and output must not exist')
    run(sys.executable, ROOT / 'scripts/prepare-sources.py', '--check')
    keys.mkdir(mode=0o700, parents=True, exist_ok=True)
    if keys.stat().st_mode & 0o077:
        raise ValueError('key directory must have mode 0700')
    private, public = keys / 'owner.pem', keys / 'owner-public.pem'
    if not private.exists():
        if public.exists():
            raise ValueError('public key exists without private key; refusing to replace identity')
        fd = os.open(private, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        run('openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:3072', '-out', private)
        run('openssl', 'pkey', '-in', private, '-pubout', '-out', public)
    if private.stat().st_mode & 0o077 or not public.is_file():
        raise ValueError('require private key mode 0600 and matching public key')
    spec = importlib.util.spec_from_file_location('manifest', KIT / 'tools/manifest.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with image.open('rb') as stream:
        record = module.make(stream, image.stat().st_size, private, public,
                             args.volume_uuid, args.generation, output)
    library = output / 'verified-root.so'
    run('cc', '-shared', '-fPIC', '-std=c11', '-Wall', '-Wextra', '-Werror',
        '-I', KIT / 'include', KIT / 'src/verified_root.c',
        KIT / 'tests/openssl_provider.c', '-lcrypto', '-o', library)
    run(sys.executable, KIT / 'tools/verify_image.py', '--library', library,
        '--manifest', output / 'manifest.bin', '--trusted-key', output / 'trusted-key.bin',
        '--image', image, '--volume-uuid', args.volume_uuid, '--minimum-generation', args.generation,
        '--output', output / 'verification.json')
    report = json.loads((output / 'verification.json').read_text())
    # The verifier proves bytes under the owner key, not that the disk is unmodified Apple software.
    report.pop('original_image_modified', None)
    report.update(image=str(image.relative_to(ROOT)), image_origin=args.image_origin,
                  apple_trust_chain_verified=False, apfs_uuid_independently_verified=False,
                  manifest_sha256=hashlib.sha256((output / 'manifest.bin').read_bytes()).hexdigest())
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    record.pop('image_modified', None)
    record['image_origin'] = args.image_origin
    (output / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f'Owner signature and {report["blocks_verified"]} blocks verified; host-only: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--volume-uuid', type=uuid.UUID, required=True)
    parser.add_argument('--generation', type=int, default=1)
    parser.add_argument('--key-dir', default='out/owner/keys')
    parser.add_argument('--output', required=True)
    parser.add_argument('--image-origin', required=True, choices=['diagnostic', 'transformed', 'apple-member'])
    main(parser.parse_args())
