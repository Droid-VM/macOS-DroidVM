#!/usr/bin/env python3
"""The one entry from the built pieces to what runs on the phone: every switch, kernel argument and step of the product is in
configs/product-NAME.json (default k27), and each step runs the existing script for it with that environment.

  product.py env                       print the configuration's environment (eval it to run a script by hand with the product's switches)
  product.py inputs [--output DIR]     Apple's files, from the IPSWs: the configuration's "inputs"  -> artifacts/TAG, kc.source
  product.py disk DIR [--inputs DIR]   a new install's system disk (sudo)     make-macos-disk.py     -> DIR/{data-store.img,disk.json}
  product.py kernel                    the kernel                       k27/build-kernel27.sh        -> kc.kernel
  product.py kexts                     the board's native kexts         the configuration's "kexts"  -> out/x12377/native-kexts
  product.py kc                        the kernel collection            k27/try.sh (K27_NO_BOOT=1)   -> kc.output
  product.py gpu [--deps]              the Metal plugin (--deps: Turnip and the bridge first)        -> gpu.bundle
  product.py boot [--also-trust FILE]  trust cache and boot disk, from nothing                       -> boot.output/{boot.img,manifest.json}
  product.py build                     kc, gpu, boot
  product.py full                      kernel, kexts, kc, gpu --deps, boot (the bridge beside the other steps)
  product.py verify [BOOT_IMG]         compare boot.output/boot.img with another boot disk (default: the phone's), payload by payload
  product.py install-plugin GUEST      put gpu.bundle into the running guest (ssh USER@HOST; MACOS_GUEST_PASSWORD) when it differs
  product.py deploy                    push boot.img and swap it in (the one before stays as boot.img.prev); the next start boots it
  product.py status                    what the manifest says was built, and whether the phone's boot disk is that one

Nothing here patches an image: the trust cache is Apple's (boot.base_trustcache) plus one module holding the CDHashes of the files
of gpu.bundle as they were built (linker-signed), and the boot disk is made new by droidvm-app.py's build_boot. The plugin on the
guest's Data volume must be that bundle (install-plugin); --also-trust adds the CDHash of a file that is not (a guest still holding
an older or re-signed plugin boots with Metal until install-plugin has run).

inputs downloads only the members the configuration names (HTTP ranges of each IPSW, checked against Apple's manifest), decrypts
the AEA ones (ipsw, or $IPSW: its key comes from Apple), bundles the trust caches and unpacks the kernel collection; what is
there already is skipped, and each step's seconds go to inputs-times.json. --output DIR (inside the repository) puts all of it
there instead, the kernel collection included, and touches nothing else.

disk makes a disk for a new VM (new volume UUIDs each time); the VM in use keeps the one it was installed with, whose disk.json
(artifacts/TAG/disk) names the root the boot disk looks for. Putting a new disk on the phone is droidvm-app.py install, then prepare.

Not steps here: the source trees (prepare-sources.py) and the VM's registration (droidvm-app.py prepare). REPO-LAYOUT.md has the whole path.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import shlex
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def load_config(name):
    config = json.loads((ROOT / f'configs/product-{name}.json').read_text())
    env = dict(config['env'], MACOS_KERNEL=str(ROOT / config['kc']['output']))
    return config, env


def run(command, env, **more):
    """One of the existing scripts, in the repository's root with the product's environment."""
    print('+', command, flush=True)
    start = time.monotonic()
    subprocess.run(command, shell=True, check=True, cwd=ROOT, env=dict(os.environ, **env, **more))
    print(f'  {time.monotonic() - start:.1f} s', flush=True)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        while block := stream.read(1 << 24):
            digest.update(block)
    return digest.hexdigest()


def inputs(config, env, output):
    """Apple's files of the product, each made once: fetch, decrypt, bundle, unpack."""
    spec = config['inputs']
    out = (ROOT / output).resolve() if output else ROOT / f'artifacts/{config["tag"]}'
    collection = out / 'kc27.bin' if output else ROOT / config['kc']['source']
    trust = out / 'boot/kernel.macho.trustcache'
    ipsw = os.environ.get('IPSW', 'ipsw')
    out.mkdir(parents=True, exist_ok=True)
    times_path = out / 'inputs-times.json'
    times = json.loads(times_path.read_text()) if times_path.exists() else {}

    def step(name, target, action):
        if target.exists():
            print(f'have  {target.relative_to(ROOT)}')
            return
        start = time.monotonic()
        action()
        if not target.exists():
            raise SystemExit(f'{name}: {target} was not made')
        times[name] = round(time.monotonic() - start, 1)
        times_path.write_text(json.dumps(times, indent=1) + '\n')
        print(f'{times[name]:8.1f} s  {name}')

    def decrypt(encrypted, target):
        key = subprocess.run([ipsw, 'fw', 'aea', '--key', str(encrypted)], check=True, capture_output=True, text=True).stdout.split()[-1]
        with tempfile.TemporaryDirectory(dir=target.parent) as scratch:
            subprocess.run([ipsw, 'fw', 'aea', '-b', key, '-o', scratch, str(encrypted)], check=True, capture_output=True)
            plain, = Path(scratch).iterdir()
            plain.replace(target)
        encrypted.unlink()

    for source in spec['ipsws']:
        inventory = out / source['inventory']
        step(f'inventory {source["inventory"]}', inventory / 'identities.json',
             lambda: run(f'python3 scripts/macos-inputs.py --profile {source["profile"]} --output {inventory.relative_to(ROOT)}', env))
        for member in source['members']:
            target = out / member['to']
            entry = [i for i in json.loads((inventory / 'identities.json').read_text())['identities']
                     if i['device_class'] == source['identity'] and i['variant'] == 'macOS Customer' and i['restore_behavior'] == 'Erase']
            fetched = target.parent / Path(entry[0]['components'][member['component']]['path']).name if len(entry) == 1 else None
            if fetched is None:
                raise SystemExit(f'{source["profile"]}: identity {source["identity"]} is not there exactly once')

            def fetch(member=member, fetched=fetched, target=target):
                target.parent.mkdir(parents=True, exist_ok=True)
                if not fetched.exists():   # a member whose decryption was interrupted is not fetched again
                    run(f'python3 scripts/macos-fetch-member.py {shlex.quote(member["component"])} --profile {source["profile"]} '
                        f'--inventory {(inventory / "identities.json").relative_to(ROOT)} --identity {source["identity"]} '
                        f'--output-dir {target.parent.relative_to(ROOT)} --jobs 8', env)
                if not member.get('aea') and fetched != target:
                    fetched.replace(target)
            if member.get('aea'):
                step(f'fetch {member["component"]}', fetched if not target.exists() else target, fetch)
                step(f'decrypt {member["component"]}', target, lambda: decrypt(fetched, target))
            else:
                step(f'fetch {member["component"]}', target, fetch)
    trust.parent.mkdir(parents=True, exist_ok=True)
    collection.parent.mkdir(parents=True, exist_ok=True)
    step('trust bundle', trust, lambda: run('python3 scripts/make-trust-bundle.py ' + ' '.join(str(out / name) for name in spec['trust_bundle'])
                                            + f' {trust}', env))
    step('kernel collection', collection, lambda: subprocess.run(
        [ipsw, 'img4', 'im4p', 'extract', '-o', str(collection), str(out / spec['kernel_collection'])], check=True, capture_output=True))
    print(f'{out.relative_to(ROOT)}: {sum(times.values()):.0f} s in all the steps timed')


def kc(config, env):
    run('bash k27/try.sh 0', env, K27_NO_BOOT='1')
    output = ROOT / config['kc']['output']
    print(f'{output}: {sha256(output)[:16]}')


def gpu(config, env, deps):
    if deps:
        run(config['gpu']['turnip'], env)
        run(config['gpu']['bridge'], env)
    run(config['gpu']['plugin'], env)


def bundle_hashes(config, stage):
    bundle = ROOT / config['gpu']['bundle']
    hashes = {str(f.relative_to(bundle)): h.hex() for f in sorted(bundle.rglob('*')) if f.is_file() and (h := stage.cdhash(f))}
    if not hashes:
        raise SystemExit(f'{bundle}: no signed Mach-O (product.py gpu)')
    return hashes


def boot(config, env, also_trust):
    os.environ.update(env)
    sys.path.insert(0, str(ROOT / 'scripts'))
    stage = load(ROOT / 'scripts/stage-gpu-plugin.py', 'stage_gpu_plugin')   # cdhash, trust_bundle
    out = ROOT / config['boot']['output']
    out.mkdir(parents=True, exist_ok=True)
    hashes = bundle_hashes(config, stage)
    extra = {str(path): stage.cdhash(Path(path)).hex() for path in also_trust}
    trust = out / 'kernel.macho.trustcache'
    trust.write_bytes(stage.trust_bundle([bytes.fromhex(h) for h in [*hashes.values(), *extra.values()]],
                                         (ROOT / config['boot']['base_trustcache']).read_bytes()))
    os.environ['MACOS_TRUSTCACHE'] = str(trust)
    os.environ['MACOS_DATA_SEED'] = str(ROOT / config['boot']['seed'])
    app = load(ROOT / 'scripts/droidvm-app.py', 'droidvm_app')
    image, line = app.build_boot(argparse.Namespace(kernel_arg=list(config['kernel_args'])), local=out / 'disk')
    final = out / 'boot.img'
    image.replace(final)
    (out / 'disk').rmdir()
    kernel = ROOT / config['kc']['output']
    manifest = {
        'product': config['name'], 'tag': config['tag'],
        'commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'dirty': bool(subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=no'], text=True).strip()),
        'env': env and {k: v for k, v in env.items() if k != 'MACOS_KERNEL'},
        'kernel_args': line,
        'kc': sha256(kernel),
        'trusted': hashes, 'also_trusted': extra,
        'trustcache': sha256(trust),
        'boot_img': sha256(final),
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    print(f'{final}: {manifest["boot_img"][:16]}\nkernel args: {line}\ntrusted: ' + ' '.join(f'{n}={h}' for n, h in {**hashes, **extra}.items()))


def adt_properties(data):
    """An Apple device tree as {path/property: value}."""
    result = {}

    def node(at, path):
        properties, children = struct.unpack_from('<II', data, at)
        at += 8
        own, name = [], '?'
        for _ in range(properties):
            key = data[at:at + 32].split(b'\0')[0].decode()
            size = struct.unpack_from('<I', data, at + 32)[0] & 0x7fffffff
            value = data[at + 36:at + 36 + size]
            if key == 'name':
                name = value.split(b'\0')[0].decode()
            own.append((key, value))
            at += 36 + (size + 3 & ~3)
        here = f'{path}/{name}' if path else name
        for key, value in own:
            result[f'{here}:{key}'] = value
        for _ in range(children):
            at = node(at, here)
        return at

    node(0, '')
    return result


def trust_modules(data):
    count, = struct.unpack_from('<I', data)
    starts = struct.unpack_from(f'<{count}I', data, 4)
    return [data[start:end] for start, end in zip(starts, list(starts[1:]) + [len(data)])]


def module_hashes(module):
    count, = struct.unpack_from('<I', module, 20)
    return {module[24 + 24 * i:44 + 24 * i].hex() for i in range(count)}


def extract(image, directory):
    subprocess.run(['mcopy', '-n', '-s', '-i', str(image), '::/EFI', str(directory)], check=True, capture_output=True,
                   env=dict(os.environ, MTOOLS_SKIP_CHECK='1'))
    return {str(f.relative_to(directory)): f for f in sorted(Path(directory).rglob('*')) if f.is_file()}


def verify(config, env, other):
    """0 when the two boot disks boot the same thing: the same kernel, loaders and seed, the same kernel arguments, and device trees
    that differ only where each build draws random bytes. Trust caches are compared by what they trust."""
    out = ROOT / config['boot']['output']
    with tempfile.TemporaryDirectory(dir=out) as scratch:
        scratch = Path(scratch)
        if other is None:
            other = scratch / 'phone.img'
            app = product_app(env)
            app.adb('pull', app.BOOT, str(other), timeout=900)
        mine, theirs = extract(out / 'boot.img', scratch / 'a'), extract(other, scratch / 'b')
        different = 0
        for name in sorted(set(mine) | set(theirs)):
            if name not in mine or name not in theirs:
                print(f'only in {"ours" if name in mine else "theirs"}: {name}')
                different += 1
                continue
            a, b = mine[name].read_bytes(), theirs[name].read_bytes()
            if a == b:
                print(f'same       {name}')
            elif name.endswith('.adt'):
                x, y = adt_properties(a), adt_properties(b)
                keys = [k for k in sorted(set(x) | set(y)) if x.get(k) != y.get(k)]
                random = [k for k in keys if k in x and k in y and len(x[k]) == len(y[k]) and k.split(':')[1] in
                          ('random-seed', 'boot-nonce', 'kaslr-seed', 'nonce-seeds', 'random-data')]
                print(f'{"same*" if keys == random else "DIFFERENT"}  {name}  (random per build: {", ".join(random) or "none"})')
                for key in keys:
                    if key not in random:
                        print(f'    {key}: ours {x.get(key, b"")[:24].hex() or "-"} theirs {y.get(key, b"")[:24].hex() or "-"}')
                        different += 1
            elif name.endswith('.trustcache'):
                x, y = trust_modules(a), trust_modules(b)
                ours = set().union(*[module_hashes(m) for m in x if m not in y] or [set()])
                others = set().union(*[module_hashes(m) for m in y if m not in x] or [set()])
                print(f'trust      {name}: {len(x)} modules ours, {len(y)} theirs; only ours {sorted(ours - others)}, '
                      f'only theirs {len(others - ours)} CDHashes')
            elif name.endswith('.toml'):
                def arguments(text):
                    return [line for line in text.decode().splitlines() if line.startswith('args = ')][0][8:-1].split()
                x, y = arguments(a), arguments(b)
                rest = a.decode().replace(' '.join(x), '') == b.decode().replace(' '.join(y), '')
                same = rest and set(x) == set(y)
                print(f'{"same*" if same else "DIFFERENT"}  {name}  only ours: {[v for v in x if v not in y]}  only theirs: {[v for v in y if v not in x]}'
                      f'  repeated: ours {sorted({v for v in x if x.count(v) > 1})} theirs {sorted({v for v in y if y.count(v) > 1})}')
                different += not same
            else:
                print(f'DIFFERENT  {name}')
                different += 1
    print('boots the same' if not different else f'{different} differences')
    return different


def product_app(env):
    os.environ.update(env)
    sys.path.insert(0, str(ROOT / 'scripts'))
    return sys.modules.get('droidvm_app') or load(ROOT / 'scripts/droidvm-app.py', 'droidvm_app')


def read_manifest(config):
    path = ROOT / config['boot']['output'] / 'manifest.json'
    if not path.exists():
        raise SystemExit(f'{path}: product.py boot first')
    return json.loads(path.read_text())


def deploy(config, env):
    manifest = read_manifest(config)
    image = ROOT / config['boot']['output'] / 'boot.img'
    if sha256(image) != manifest['boot_img']:
        raise SystemExit(f'{image} is not the one of manifest.json')
    app = product_app(env)
    new = app.BOOT + '.new'
    app.adb('push', str(image), new, timeout=900)
    app.fix_owner(new)
    if app.sh(f'sha256sum {new}').split()[0] != manifest['boot_img']:
        raise SystemExit(f'{new}: the push went wrong')
    # a running crosvm keeps the file it opened: the rename takes effect at the VM's next start
    app.sh(f'if [ -e {app.BOOT} ]; then mv -f {app.BOOT} {app.BOOT}.prev; fi && mv {new} {app.BOOT} && sync')
    # what was deployed, beside it: a boot writes to the disk's file system (not to a payload), so its hash only holds until then
    app.adb('push', str(ROOT / config['boot']['output'] / 'manifest.json'), app.BOOT + '.manifest.json', timeout=60)
    print(f'{app.BOOT}: {manifest["boot_img"][:16]} (the one before: {app.BOOT}.prev); it boots at the next start')


def status(config, env):
    manifest = read_manifest(config)
    print(json.dumps({k: manifest[k] for k in ('product', 'tag', 'commit', 'dirty', 'kc', 'trusted', 'also_trusted', 'boot_img')}, indent=1))
    app = product_app(env)
    remote = app.sh(f'sha256sum {app.BOOT}', check=False).split()
    deployed = app.sh(f'cat {app.BOOT}.manifest.json', check=False)
    deployed = json.loads(deployed).get('boot_img') if deployed.strip() else None
    if remote and remote[0] == manifest['boot_img']:
        print('phone: this boot disk, not booted yet')
    elif deployed == manifest['boot_img']:
        print('phone: this boot disk was deployed; it has been written since (a boot does that; product.py verify compares the payloads)')
    else:
        print(f'phone: another boot disk (deployed: {deployed[:16] if deployed else "not by product.py"})')


def install_plugin(config, guest):
    """The bundle as built, into the running guest, unless it is there already. The files are replaced by renaming, so a process
    that has the old plugin mapped keeps it until it restarts; the boot disk must trust the new one (boot, deploy) before a restart."""
    bundle = ROOT / config['gpu']['bundle']
    target = config['gpu']['guest_path']
    password = os.environ.get('MACOS_GUEST_PASSWORD')
    if password is None:
        raise SystemExit('MACOS_GUEST_PASSWORD: the guest user\'s password (sudo)')
    ssh = ['sshpass', '-e', 'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null', '-o', 'LogLevel=ERROR',
           '-o', 'ConnectTimeout=8', guest]
    environment = dict(os.environ, SSHPASS=password)
    files = [f for f in sorted(bundle.rglob('*')) if f.is_file()]
    local = {str(f.relative_to(bundle)): sha256(f) for f in files}
    listing = subprocess.run(ssh + [f'cd {shlex.quote(target)} 2>/dev/null && find . -type f -exec shasum -a 256 {{}} +'],
                             capture_output=True, text=True, env=environment, check=True).stdout
    remote = {line.split(None, 1)[1].strip()[2:]: line.split()[0] for line in listing.splitlines() if line.strip()}
    if remote == local:
        print(f'{guest}:{target} is the bundle built')
        return
    staging = '/private/var/tmp/product-plugin'
    subprocess.run(ssh + [f'rm -rf {staging} && mkdir -p {staging}'], env=environment, check=True)
    archive = subprocess.run(['tar', '-C', str(bundle.parent), '-cf', '-', bundle.name], capture_output=True, check=True).stdout
    subprocess.run(ssh + [f'tar -C {staging} -xf -'], input=archive, env=environment, check=True)
    name = shlex.quote(bundle.name)
    sudo = f'echo {shlex.quote(password)} | sudo -S -p ""'
    previous = f'/private/var/tmp/{name}.prev'   # the same volume (a rename), outside the directory Metal searches
    for step in (f'chown -R 0:0 {staging}/{name} && chmod -R go-w,a+rX {staging}/{name}',
                 f'rm -rf {previous}',
                 f'sh -c "if [ -e {shlex.quote(target)} ]; then mv {shlex.quote(target)} {previous}; fi; '
                 f'mv {staging}/{name} {shlex.quote(target)}"'):
        subprocess.run(ssh + [f'{sudo} {step}'], env=environment, check=True)
    print(f'{guest}:{target} replaced ({len(local)} files; the one before: {previous}); restart the guest once the boot disk trusts it')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--product', default=os.environ.get('MACOS_PRODUCT', 'k27'))
    sub = parser.add_subparsers(dest='cmd', required=True)
    for name in ('env', 'kernel', 'kexts', 'kc', 'build', 'full', 'deploy', 'status'):
        sub.add_parser(name)
    sub.add_parser('inputs').add_argument('--output', metavar='DIR')
    disk = sub.add_parser('disk')
    disk.add_argument('dir')
    disk.add_argument('--inputs', metavar='DIR', help="inputs --output's directory")
    sub.add_parser('gpu').add_argument('--deps', action='store_true')
    sub.add_parser('boot').add_argument('--also-trust', action='append', default=[], metavar='FILE')
    sub.add_parser('verify').add_argument('image', nargs='?', type=Path)
    sub.add_parser('install-plugin').add_argument('guest')
    args = parser.parse_args()
    config, env = load_config(args.product)
    if args.cmd == 'env':
        print('\n'.join(f'export {k}={shlex.quote(v)}' for k, v in env.items()))
    elif args.cmd == 'inputs':
        inputs(config, env, args.output)
    elif args.cmd == 'disk':
        start = time.monotonic()
        run(f'python3 scripts/make-macos-disk.py {shlex.quote(args.dir)}', env,
            **({'MACOS_ARTIFACTS': str((ROOT / args.inputs).resolve())} if args.inputs else {}))
        print(f'{time.monotonic() - start:.0f} s')
    elif args.cmd == 'kernel':
        run('bash k27/build-kernel27.sh', env)
    elif args.cmd == 'kexts':
        for command in config['kexts']:
            run(command, env)
    elif args.cmd == 'kc':
        kc(config, env)
    elif args.cmd == 'gpu':
        gpu(config, env, args.deps)
    elif args.cmd == 'boot':
        boot(config, env, args.also_trust)
    elif args.cmd == 'build':
        kc(config, env)
        gpu(config, env, False)
        boot(config, env, [])
    elif args.cmd == 'full':
        # The bridge (7 minutes, its last 3 one fat-LTO unit on one core) needs nothing the other steps make: it builds beside them,
        # its output in out/metal/bridge/build.log as always.
        start = time.monotonic()
        print('+ (beside the rest)', config['gpu']['bridge'], flush=True)
        bridge = subprocess.Popen(config['gpu']['bridge'], shell=True, cwd=ROOT, env=dict(os.environ, **env),
                                  stdout=open(ROOT / config['boot']['output'] / 'bridge.out', 'w') if (ROOT / config['boot']['output']).is_dir()
                                  else subprocess.DEVNULL, stderr=subprocess.STDOUT)
        try:
            run('bash k27/build-kernel27.sh', env)
            for command in config['kexts']:
                run(command, env)
            kc(config, env)
            run(config['gpu']['turnip'], env)
        except BaseException:
            bridge.terminate()
            raise
        if bridge.wait():
            raise SystemExit(f'the bridge failed ({bridge.returncode}): {config["boot"]["output"]}/bridge.out')
        print(f'  bridge done at {time.monotonic() - start:.1f} s', flush=True)
        run(config['gpu']['plugin'], env)
        boot(config, env, [])
    elif args.cmd == 'verify':
        raise SystemExit(1 if verify(config, env, args.image) else 0)
    elif args.cmd == 'install-plugin':
        install_plugin(config, args.guest)
    elif args.cmd == 'deploy':
        deploy(config, env)
    elif args.cmd == 'status':
        status(config, env)


if __name__ == '__main__':
    main()
