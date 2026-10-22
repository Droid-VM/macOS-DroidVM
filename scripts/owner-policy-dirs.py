#!/usr/bin/env python3
"""Lay out the owner root policies in the form UniXNU scripts/build-verified-root-probe.py reads.

    owner-policy-dirs.py INPUTS TREE [ios|macos]

INPUTS is the decrypted release asset root-policies/verified-root-inputs.tar.enc (scripts/make-virt-root.py on the Linux
host: os.manifest.bin, systemos.manifest.bin, trusted-key.bin, os.samples.bin, inputs.json). TREE is the unixnu build tree;
this writes TREE/build/verified-root-os/ and TREE/build/verified-root-systemos/ (manifest.bin, trusted-key.bin,
verification.json, and original-samples.bin for the OS), which build-owner-os-policy.py / build-owner-systemos-policy.py
write on macOS with hdiutil. The manifests cover the unchanged images (the OS one expanded from its UDIF member), were made
with kits/VerifiedRoot/tools/manifest.py over every block and signed with the owner key, their signatures checked with
openssl; NativeVirtioBlock then verified every block it read on a full QEMU/KVM boot to SpringBoard.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOTS = {
    # iPadOS 21H461: the OS member expanded, the Cryptex1,SystemOS member as is.
    'ios': {'os': ('e5634d04a8ac35f024845f583394e0a35deb26a04cb0c00286a8674e25a9a4f2', 1483785),
            'systemos': ('b4908cde41d23e6bc05e6af51a2c9eeb00cf0f863a6a18b1600c96a3fd70414f', 806400)},
}

inputs, tree = map(Path, sys.argv[1:3])
if len(sys.argv) > 3 and sys.argv[3] == 'macos':
    # macOS 23G93: the locally built OS disk and SystemOS disk (macos-root-pins.py), not upstream's converted images.
    import importlib.util
    spec = importlib.util.spec_from_file_location('pins', Path(__file__).with_name('macos-root-pins.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    EXPECTED = {name: (pin['image_sha256'], pin['blocks_verified']) for name, pin in module.load().items()}
else:
    EXPECTED = ROOTS[sys.argv[3] if len(sys.argv) > 3 else 'ios']
records = json.loads((inputs / 'inputs.json').read_text())
key = (inputs / 'trusted-key.bin').read_bytes()
key_sha256 = hashlib.sha256(key).hexdigest()
for name, (digest, blocks) in EXPECTED.items():
    record = records[name]
    if record['image_sha256'] != digest or record['block_count'] != blocks or record['trusted_key_sha256'] != key_sha256:
        raise SystemExit(f'{name}: the policy does not describe the expected original image under this anchor')
    out = tree / 'build' / f'verified-root-{name}'
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(inputs / f'{name}.manifest.bin', out / 'manifest.bin')
    (out / 'trusted-key.bin').write_bytes(key)
    report = dict(image_bytes=record['image_bytes'], blocks_verified=record['block_count'], image_sha256=digest,
                  volume_uuid=record['volume_uuid'], generation=record['generation'], trusted_key_sha256=key_sha256,
                  real_c_signature_and_block_verification=True, original_image_modified=False, host_only=True,
                  boot_root_authenticated=False, hardware_tested=False,
                  source='make-virt-root.py on Linux: manifest.py over every block, openssl signature check; '
                         'every block read verified by NativeVirtioBlock on a QEMU/KVM boot')
    if name == 'os':
        report.update(actual_sample_indices=record['sample_indices'], actual_sample_lengths=record['sample_lengths'])
        shutil.copyfile(inputs / 'os.samples.bin', out / 'original-samples.bin')
    (out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{out}: {blocks} blocks, image {digest[:16]}')
