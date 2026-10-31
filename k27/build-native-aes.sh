#!/usr/bin/env bash
# NativeAES for k27 (objects in out/x12377/native-kexts/NativeAES, described by overlay/kext/NativeAES.json): the UniXNU driver plus
# the device key selector 2212, with which macOS 27's AppleImage4 entangles the nonce slots it resets (_darwin_el2_entangle_nonce,
# "panic: encryption failed: 0xe00002c7" when the accelerator refuses it). The VM has no UID key; selector 2212 encrypts with a fixed
# software key (no secret: the nonces live in this VM only), the same on every boot. The source stays untouched: it is copied to
# out/k27/src and changed there.
set -eu
K27=$(cd "$(dirname "$0")" && pwd); M=$(dirname "$K27")
S=$M/out/k27/src; mkdir -p $S
cp $M/sources/UniXNU/drivers/NativeAES/NativeAES.cpp $S/NativeAES.cpp
python3 - $S/NativeAES.cpp <<'E'
import sys
p = sys.argv[1]; s = open(p).read()
def swap(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)
swap("  bool isKeySupported(unsigned selector) override { return selector == 0; }",
     "  bool isKeySupported(unsigned selector) override { return selector == 0 || selector == 2212; }")
swap("IOReturn NativeAES::performAES(IOMemoryDescriptor *input, IOMemoryDescriptor *output,",
     """// k27: the device key 2212 (macOS 27 AppleImage4's nonce entanglement) as a fixed software key of the requested size.
static bool k27DeviceKey(const IOAESKeyData *key, IOAESKeyData *out)
{
  if (key->selector != 2212) return false;
  out->bits = key->bits;
  out->selector = 0;
  for (unsigned i = 0; i < sizeof(out->bytes); i++) out->bytes[i] = static_cast<unsigned char>(0x5a ^ (i * 0x1d) ^ (key->selector >> (8 * (i & 1))));
  return true;
}

IOReturn NativeAES::performAES(IOMemoryDescriptor *input, IOMemoryDescriptor *output,""")
swap("""      (key->bits != 128 && key->bits != 192 && key->bits != 256)) return kIOReturnBadArgument;
  if (key->selector || (operation != IOAESEncrypt && operation != IOAESDecrypt)) {
    __atomic_fetch_add(&native_aes_unsupported_key, 1, __ATOMIC_RELAXED);""",
"""      (key->bits != 128 && key->bits != 192 && key->bits != 256)) return kIOReturnBadArgument;
  IOAESKeyData device;
  if (k27DeviceKey(key, &device)) key = &device;
  if (key->selector || (operation != IOAESEncrypt && operation != IOAESDecrypt)) {
    __atomic_fetch_add(&native_aes_unsupported_key, 1, __ATOMIC_RELAXED);""")
open(p, 'w').write(s)
E
cd $M
python3 scripts/build-native-kext.py NativeAES $S/NativeAES.cpp overlay/kext/NativeKextGlue.cpp -I $M/overlay/kext/NativeAES --obj k27-obj
