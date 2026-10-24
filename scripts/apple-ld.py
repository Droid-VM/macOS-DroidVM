#!/usr/bin/env python3
"""Apple's ld-classic (Command Line Tools 15.3) for arm64e user space, run in the Darling container of the Linux toolchain.

    apple-ld.py install          extract usr/bin/ld-classic from the CLTools package into the container's tools
    apple-ld.py LDFLAGS...       link (arm64e, macOS 14.0 / SDK 26.1, -F overlay/metal/frameworks)

Neither of the Linux linkers does: cctools-port's ld64-711 has no TAPI (no .tbd), and ld64.lld has no arm64e authenticated pointer
relocations. ld (ld-prime) needs a newer libc++ than Darling's; ld-classic does not. Paths are host paths under the workspace."""
import json
import lzma
import os
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN = ROOT / 'toolchains/linux'
TOOLS = TOOLCHAIN / 'appleclang/apple-tools/Library/Developer/CommandLineTools/usr'
DARLING_TOOLS = '/Volumes/SystemRoot/opt/apple/Library/Developer/CommandLineTools/usr'
SDK = ROOT / 'toolchains/sdks/MacOSX26.1.sdk'
MEMBER = './Library/Developer/CommandLineTools/usr/bin/ld-classic'


def install():
    config = json.loads((TOOLCHAIN / 'bin/linux-toolchain.json').read_text())['appleclang']['sources']['apple']
    package = TOOLCHAIN / 'appleclang' / config['file']   # the CLTools package the toolchain's clang came from (sha256 in the config)
    stream = package.open('rb')
    stream.seek(config['payload_offset'])
    if stream.read(4) != b'pbzx':
        raise SystemExit(f'{package}: no pbzx payload at {config["payload_offset"]}')
    stream.read(8)
    end = config['payload_offset'] + config['payload_length']

    def chunks():   # pbzx: (flags, size, data) chunks, xz-compressed or stored
        while stream.tell() < end:
            _, size = struct.unpack('>QQ', stream.read(16))
            data = stream.read(size)
            yield lzma.decompress(data) if data[:6] == b'\xfd7zXZ\x00' else data

    source, buffer = chunks(), b''

    def take(count):
        nonlocal buffer
        while len(buffer) < count:
            buffer += next(source)
        data, buffer = buffer[:count], buffer[count:]
        return data

    while True:   # odc cpio
        header = take(76)
        assert header[:6] == b'070707', header[:6]
        mode, name_size, size = int(header[18:24], 8), int(header[59:65], 8), int(header[65:76], 8)
        name = take(name_size)[:-1].decode()
        if name == 'TRAILER!!!':
            raise SystemExit(f'{MEMBER} is not in {package}')
        data = take(size)
        if name == MEMBER:
            target = TOOLS / 'bin/ld-classic'
            target.write_bytes(data)
            target.chmod(mode & 0o777)
            print(f'{target}: {len(data)} bytes')
            return


def link(arguments):
    if not (TOOLS / 'bin/ld-classic').is_file():
        install()
    container = json.loads((TOOLCHAIN / 'bin/linux-toolchain.json').read_text())['appleclang']['container']
    subprocess.run(['docker', 'start', container], check=True, stdout=subprocess.DEVNULL)
    darling = lambda path: '/Volumes/SystemRoot' + str(Path(path).resolve())   # noqa: E731
    command = [f'{DARLING_TOOLS}/bin/ld-classic', '-arch', 'arm64e', '-platform_version', 'macos', '14.0', '26.1',
               '-syslibroot', darling(SDK), '-F', darling(ROOT / 'overlay/metal/frameworks'), *arguments]
    # Darling's shell takes one command line: quote every argument; Darling's /usr/lib lacks libcodedirectory, the CLT's has it
    script = f'cd {darling(os.getcwd())} && DYLD_LIBRARY_PATH={DARLING_TOOLS}/lib exec ' + ' '.join(
        "'" + a.replace("'", "'\\''") + "'" for a in command)
    result = subprocess.run(['docker', 'exec', '-i', container, 'darling', 'shell', '/bin/bash', '--noprofile', '--norc', '-c', script],
                            capture_output=True, text=True, timeout=600)
    sys.stderr.write(''.join(l for l in (result.stdout + result.stderr).splitlines(True) if 'rlimit' not in l))
    output = arguments[arguments.index('-o') + 1] if '-o' in arguments else None
    if result.returncode or (output and not Path(output).is_file()):
        raise SystemExit(f'ld-classic failed ({result.returncode})')


if __name__ == '__main__':
    if sys.argv[1:] == ['install']:
        install()
    else:
        link(sys.argv[1:])
