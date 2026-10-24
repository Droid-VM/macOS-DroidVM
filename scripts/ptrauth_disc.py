#!/usr/bin/env python3
"""ptrauth_string_discriminator (clang's stable SipHash-2-4 of a string, as getPointerAuthStableSipHash): ptrauth_disc.py STRING..."""
import struct
import sys

KEY = bytes([0xb5, 0xd4, 0xc9, 0xeb, 0x79, 0x10, 0x4a, 0x79, 0x6f, 0xec, 0x8b, 0x1b, 0x42, 0x87, 0x81, 0xd4])
M = (1 << 64) - 1


def rotl(x, b):
    return ((x << b) | (x >> (64 - b))) & M


def siphash24(key, data):
    k0, k1 = struct.unpack('<QQ', key)
    v0, v1, v2, v3 = k0 ^ 0x736f6d6570736575, k1 ^ 0x646f72616e646f6d, k0 ^ 0x6c7967656e657261, k1 ^ 0x7465646279746573

    def rounds(n):
        nonlocal v0, v1, v2, v3
        for _ in range(n):
            v0 = (v0 + v1) & M; v1 = rotl(v1, 13); v1 ^= v0; v0 = rotl(v0, 32)
            v2 = (v2 + v3) & M; v3 = rotl(v3, 16); v3 ^= v2
            v0 = (v0 + v3) & M; v3 = rotl(v3, 21); v3 ^= v0
            v2 = (v2 + v1) & M; v1 = rotl(v1, 17); v1 ^= v2; v2 = rotl(v2, 32)
    tail = len(data) % 8
    for i in range(0, len(data) - tail, 8):
        m, = struct.unpack_from('<Q', data, i)
        v3 ^= m; rounds(2); v0 ^= m
    b = (len(data) & 0xff) << 56
    for i, byte in enumerate(data[len(data) - tail:]):
        b |= byte << (8 * i)
    v3 ^= b; rounds(2); v0 ^= b
    v2 ^= 0xff; rounds(4)
    return v0 ^ v1 ^ v2 ^ v3


def discriminator(text):
    return siphash24(KEY, text.encode()) % 0xffff + 1


if __name__ == '__main__':
    for s in sys.argv[1:]:
        print(f'{discriminator(s):#06x} {s}')
