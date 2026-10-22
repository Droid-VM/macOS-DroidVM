#!/usr/bin/env python3
"""Audit the local reference candidate, without borrowing upstream runtime evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('linux_build', ROOT / 'scripts/build-linux.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
TREE = build.TREE


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'audit source changed: expected one {old!r}')
    return text.replace(old, new)


def main():
    subprocess.run([sys.executable, ROOT / 'scripts/prepare-sources.py', '--check'], check=True)
    candidate = TREE.parent / 'kernel/kernel.macho'
    plan = json.loads(candidate.with_suffix('.json').read_text())
    if hashlib.sha256(candidate.read_bytes()).hexdigest() != plan['candidate_sha256']:
        raise ValueError('candidate hash differs from prelink report')
    env = build.environment()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    sources = {
        'audit-storage-interface-static.py': ROOT / 'sources/UniXNU-droidvm/scripts/audit-storage-interface-static.py',
        'audit-mobile-graphics-legacy.py': ROOT / 'sources/UniXNU/scripts/audit-mobile-graphics-legacy.py',
    }
    provenance = {}
    for name, source in sources.items():
        text = source.read_text()
        provenance[name] = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        if name.startswith('audit-storage'):
            text = replace_once(text, 'live_metadata_checked=False, live_native_4k=True,',
                                'live_metadata_checked=False, live_native_4k=False,')
        else:
            start = text.index("runtime=ROOT/'build/darwinboot-owner-hvf-mobile-graphics-legacy-class/gdb-stop.json'")
            end = text.index('out.write_text(', start)
            # Keep every executable/vtable static check above this section. There
            # is no local gdb-stop observation, so do not seed an upstream hash.
            text = text[:start] + (
                "out=ROOT/'build/display-analysis/mobile-graphics-legacy-abi.json'\n"
                "out.parent.mkdir(parents=True,exist_ok=True)\nruntime_sha=None\n") + text[end:]
            text = replace_once(text, 'legacy_instance_bytes=0x18a0,',
                                'legacy_instance_bytes_assumed=0x18a0,live_metadata_checked=False,')
        target = TREE / 'scripts' / name
        target.write_text(text)
        provenance[name]['adapted_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
    prelink = TREE / 'build/native-prelink'
    prelink.mkdir(parents=True, exist_ok=True)
    for suffix in ('.macho', '.json'):
        link = prelink / ('native-owner-ufs-cpu-desktop-local-candidate' + suffix)
        expected = candidate.with_suffix(suffix)
        if link.is_symlink():
            if link.resolve() != expected.resolve():
                raise ValueError(f'unexpected candidate link: {link}')
        elif link.exists():
            raise ValueError(f'refusing to replace {link}')
        else:
            link.symlink_to(expected)
    for name in sources:
        subprocess.run([sys.executable, TREE / 'scripts' / name], cwd=TREE, env=env, check=True)
    raw = TREE / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped.noctf'
    subprocess.run([sys.executable, TREE / 'scripts/audit-xnu-kernel.py', raw], cwd=TREE, env=env, check=True)
    storage = json.loads((TREE / 'build/storage-abi/interface-audit.json').read_text())
    display = json.loads((TREE / 'build/display-analysis/mobile-graphics-legacy-abi.json').read_text())
    result = {
        'candidate_sha256': plan['candidate_sha256'], 'scope': 'static-original-iPadOS-families-only',
        'storage_slots': storage['method_slots'], 'storage_kernel_bindings': storage['kernel_bindings'],
        'display_slots': display['legacy_virtual_entries'], 'display_abstract_slots': display['abstract_slots'],
        'static_checks_passed': True, 'live_metadata_checked': False,
        'macos_userclient_abi_verified': False, 'boot_qualified': False, 'auditors': provenance,
    }
    (build.OUT / 'reference-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
