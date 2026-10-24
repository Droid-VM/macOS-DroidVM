#!/usr/bin/env python3
"""Print the XNU message buffer (struct msgbuf at _msgbufp) of the macOS VM running on the phone, from the host side.

Adapted from ios tools/rig/{peek,dmesg}.py (ios commit 9a1e72d). The kernel is mapped linearly from DarwinBoot's hand-off
(KERNEL_VA -> KERNEL_PA, the console line "DARWINBOOT: ARM64 va= pa=" of the run's serial.log); other kernel addresses (the heap,
e.g. a msgbuf= buffer) are translated through the kernel pmap's tables (kernel_pmap_store's root, 4 KiB granule, 39-bit L1 root).
Guest PA -> host address goes through the crosvm_guest memfd mapping whose file offset is PA - 0x80000000. Needs root on the phone (su).

  rig-dmesg.py SERIAL_LOG [--serial ADB_SERIAL]
  rig-dmesg.py --peek SYMBOL|va:HEX|0xPA [LENGTH] SERIAL_LOG
  rig-dmesg.py --poke SYMBOL BYTE SERIAL_LOG
"""
import argparse
import os
import re
import shlex
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('MACOS_KERNEL', ROOT / 'out/linux/reference/droidvm/kernel/kernel.macho'))
MEMFD_GUEST_BASE = 0x80000000
KERNELCACHE_SPAN = 0x6000000   # the fileset kernelcache the hand-off maps linearly


class Phone:
    def __init__(self, serial, serial_log):
        self.serial = serial
        match = None
        for match in re.finditer(r'DARWINBOOT: ARM64 va=0x([0-9A-Fa-f]+) pa=0x([0-9A-Fa-f]+)', Path(serial_log).read_text(errors='replace')):   # the last boot of an appended log
            pass
        if not match:
            raise SystemExit('no DarwinBoot hand-off line in the serial log')
        self.kernel_va, self.kernel_pa = int(match.group(1), 16), int(match.group(2), 16)
        nm = ROOT / 'out/rig' / (KERNEL.stem + '.nm')
        if not nm.exists() or nm.stat().st_mtime < KERNEL.stat().st_mtime:
            nm.parent.mkdir(parents=True, exist_ok=True)
            nm.write_text(subprocess.check_output(['llvm-nm', '-n', '--defined-only', str(KERNEL)], text=True))
        self.nm = nm

    def adb(self, command):
        return subprocess.run(['adb'] + (['-s', self.serial] if self.serial else []) + ['shell', 'su -c ' + shlex.quote(command)],
                              capture_output=True, timeout=120).stdout

    def maps(self):
        pid = self.adb("for p in $(pidof crosvm crosvm-mmio); do tr '\\0' ' ' < /proc/$p/cmdline | grep -q 'virtio-mmio-block' && echo $p; done").split()
        if not pid:
            raise SystemExit('no running crosvm with virtio-mmio-block (the VM is not up; start it with --keep)')
        pid = pid[0].decode()
        result = []
        for line in self.adb(f'grep crosvm_guest /proc/{pid}/maps').decode().splitlines():
            span, _, offset = line.split()[:3]
            start, end = (int(x, 16) for x in span.split('-'))
            result.append((int(offset, 16) + MEMFD_GUEST_BASE, end - start, start))
        return pid, result

    def symbol(self, name):
        for line in open(self.nm):
            parts = line.split()
            if len(parts) == 3 and parts[2] in (name, '_' + name):
                return int(parts[0], 16)
        raise SystemExit(f'no symbol {name}')

    def poke(self, target, value):
        va = int(target[3:], 16) if target.startswith('va:') else self.symbol(target)
        pa = va - self.kernel_va + self.kernel_pa
        pid, maps = self.maps()
        for guest, size, host in maps:
            if guest <= pa < guest + size:
                address = host + pa - guest
                break
        else:
            raise SystemExit(f'guest PA {pa:#x} is not in a crosvm_guest mapping')
        self.adb(f"printf '\\x{value:02x}' | dd of=/proc/{pid}/mem bs=1 seek={address} count=1 conv=notrunc 2>&1")

    def translate(self, va):
        """Kernel VA -> guest PA: linear for the kernelcache, else a walk of the kernel pmap (L1 -> L2 -> L3, 4 KiB pages)."""
        if 0 <= va - self.kernel_va < KERNELCACHE_SPAN:
            return va - self.kernel_va + self.kernel_pa
        if not hasattr(self, 'root'):
            self.root = struct.unpack('<Q', self.read('va:%x' % (self.symbol('kernel_pmap_store') + 8), 8)[1])[0]   # pmap.ttep
        table = self.root
        for level, shift in ((1, 30), (2, 21), (3, 12)):
            entry = struct.unpack('<Q', self.read('%#x' % (table + ((va >> shift) & 0x1ff) * 8), 8)[1])[0]
            if not entry & 1:
                raise SystemExit(f'va {va:#x}: level {level} entry {entry:#x} is invalid')
            address = entry & 0x0000fffffffff000
            if level == 3 or not entry & 2:   # a page, or a block at level 1/2
                return (address & ~((1 << shift) - 1)) | (va & ((1 << shift) - 1))
            table = address

    def read(self, target, length):
        if target.startswith('va:') and not 0 <= int(target[3:], 16) - self.kernel_va < KERNELCACHE_SPAN:
            va, data = int(target[3:], 16), b''   # not linear: page by page
            while len(data) < length:
                chunk = min(length - len(data), 0x1000 - (va + len(data)) % 0x1000)
                data += self.read('%#x' % self.translate(va + len(data)), chunk)[1]
            return self.translate(va), data
        if target.startswith('0x'):
            pa = int(target, 16)
        else:
            va = int(target[3:], 16) if target.startswith('va:') else self.symbol(target)
            pa = va - self.kernel_va + self.kernel_pa
        pid, maps = self.maps()
        for guest, size, host in maps:
            if guest <= pa and pa + length <= guest + size:
                address = host + pa - guest
                break
        else:
            raise SystemExit(f'guest PA {pa:#x}+{length:#x} is not in a crosvm_guest mapping')
        data = self.adb(f'dd if=/proc/{pid}/mem bs=1 skip={address} count={length} 2>/dev/null')
        return pa, data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('serial_log')
    parser.add_argument('--serial')
    parser.add_argument('--peek')
    parser.add_argument('--poke', nargs=2, metavar=('SYMBOL', 'BYTE'), help='write one byte to a kernel symbol of the running VM')
    parser.add_argument('length', nargs='?', type=lambda v: int(v, 0), default=64)
    args = parser.parse_args()
    phone = Phone(args.serial, args.serial_log)
    if args.poke:
        phone.poke(args.poke[0], int(args.poke[1], 0))
        return
    if args.peek:
        pa, data = phone.read(args.peek, args.length)
        for index in range(0, len(data), 16):
            chunk = data[index:index + 16]
            print(f'{pa + index:#x}: {chunk.hex(" ")}  {"".join(chr(c) if 32 <= c < 127 else "." for c in chunk)}')
        return
    _, pointer = phone.read('msgbufp', 8)
    msgbuf = struct.unpack('<Q', pointer)[0]
    _, head = phone.read(f'va:{msgbuf:x}', 24)
    magic, size, bufx, bufr, bufc = struct.unpack('<iiiiQ', head)
    print(f'msgbuf @ {msgbuf:#x}: magic {magic:#x} size {size} bufx {bufx} bufr {bufr} bufc {bufc:#x}', file=sys.stderr)
    _, data = phone.read(f'va:{bufc:x}', size)
    text = data[bufx:] + data[:bufx]
    sys.stdout.write(text.replace(b'\0', b'').decode(errors='replace'))


if __name__ == '__main__':
    main()
