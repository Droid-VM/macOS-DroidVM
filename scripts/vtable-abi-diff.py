#!/usr/bin/env python3
"""Compare C++ vtable layouts of classes in a source-built xnu kernel with the kernel entry of an MH_FILESET kernelcache.

    vtable-abi-diff.py KERNEL.macho KERNELCACHE.decompressed [CLASS ...]

Prints, per class, the slot count in both and the first slots whose symbol differs. Padding slots (macOS kexts expect
APPLE_KEXT_VTABLE_PADDING) show up as extra reserved methods in the macOS-target kernel.
"""
import bisect
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fileset_kc  # noqa: E402

DEFAULT = ['OSObject', 'OSMetaClassBase', 'IORegistryEntry', 'IOService', 'IOUserClient', 'IOMemoryDescriptor',
           'IOBufferMemoryDescriptor', 'OSDictionary', 'OSArray', 'IOWorkLoop', 'IOCommandGate', 'IOEventSource',
           'IOInterruptEventSource', 'IOPlatformExpert', 'IOMemoryMap', 'OSSet', 'OSString', 'OSNumber', 'IODMACommand']


def macho_symbols(data, base_off=0):
    magic, cpu, sub, kind, count, size = struct.unpack_from('<6I', data, base_off)
    off = base_off + 32
    segments, symtab = [], None
    for _ in range(count):
        cmd, length = struct.unpack_from('<II', data, off)
        if cmd == 0x19:
            name = data[off + 8:off + 24].split(b'\0')[0].decode()
            va, vmsize, fileoff, filesize = struct.unpack_from('<4Q', data, off + 24)
            segments.append((name, va, vmsize, fileoff, filesize))
        elif cmd == 2:
            symtab = struct.unpack_from('<4I', data, off + 8)
        off += length
    symoff, nsyms, stroff, strsize = symtab
    strings = data[stroff:stroff + strsize]
    syms = {}
    for i in range(nsyms):
        strx, kind_, sect, desc, value = struct.unpack_from('<IBBHQ', data, symoff + i * 16)
        if kind_ & 0x0e == 0x0e and value:
            syms[strings[strx:strings.find(b'\0', strx)].decode(errors='replace')] = value
    return segments, syms


def vt_slots(data, segments, vt_va, nslots_max, resolve):
    def foff(va):
        for _, sva, vsz, fo, fs in segments:
            if sva <= va < sva + fs:
                return fo + va - sva
        return None
    out = []
    for i in range(nslots_max):
        fo = foff(vt_va + 8 * i)
        if fo is None:
            break
        out.append(resolve(vt_va + 8 * i, struct.unpack_from('<Q', data, fo)[0]))
    return out


def main():
    kernel = Path(sys.argv[1]).read_bytes()
    kc = fileset_kc.Kernelcache(Path(sys.argv[2]).read_bytes())
    classes = sys.argv[3:] or DEFAULT
    segs, syms = macho_symbols(kernel)
    rev = sorted((v, k) for k, v in syms.items())
    addrs = [v for v, _ in rev]

    def name_of(va):
        i = bisect.bisect_right(addrs, va) - 1
        return rev[i][1] if i >= 0 and va - rev[i][0] < 0x10000 else hex(va)

    entry = kc.macho('com.apple.kernel')
    ksyms = {n: v for n, k, s, d, v in kc.symbols(entry) if k & 0x0e == 0x0e and v}
    krev = sorted((v, k) for k, v in ksyms.items())
    kaddrs = [v for v, _ in krev]
    sites = {}
    for site, raw, target, *_ in kc.chained_sites():
        sites[site] = target

    def kname_of(va):
        i = bisect.bisect_right(kaddrs, va) - 1
        return krev[i][1] if i >= 0 and va - krev[i][0] < 0x10000 else hex(va)

    for cls in classes:
        sym = f'__ZTV{len(cls)}{cls}'
        if sym not in syms or sym not in ksyms:
            print(f'{cls}: missing ({sym in syms=}, {sym in ksyms=})')
            continue
        # vtable length: up to the next symbol of the same image
        def length(addrs_, va):
            i = bisect.bisect_right(addrs_, va)
            return (addrs_[i] - va) // 8 if i < len(addrs_) else 0
        ours = vt_slots(kernel, segs, syms[sym], length(addrs, syms[sym]), lambda site, raw: name_of(raw))
        ref = []
        for i in range(length(kaddrs, ksyms[sym])):
            site = ksyms[sym] + 8 * i
            ref.append(kname_of(sites[site]) if site in sites else '?')
        def norm(x):
            return re.sub(r'D[01]Ev$', 'DxEv', x)
        diff = [(i, a, b) for i, (a, b) in enumerate(zip(ours, ref)) if i >= 2 and norm(a) != norm(b)]
        print(f'{cls}: slots ours {len(ours)} kc {len(ref)} differing {len(diff)} first {diff[:2]}')


main()
