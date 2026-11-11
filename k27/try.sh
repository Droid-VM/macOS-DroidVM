#!/usr/bin/env bash
# Build the KC from out/k27/kernel-k27.macho and kc27's kexts, boot it once.
#   k27/try.sh SECONDS BOOTARGS... [-- BUNDLE_ID...]      (switches: NATIVE / MACOS_DISPLAY / MACOS_GPU / MACOS_VIDEO / MACOS_AUDIO)
# The kernel symbols go to out/rig/kc-k27.nm, where rig-dmesg.py (and so kc-panic.sh) looks for those of out/k27/kc-k27.bin.
# rootauth=0 always: 27's APFS answers FSIOC_KERNEL_ROOTAUTH by validating the sealed root (26.5's let CSR_ALLOW_UNAUTHENTICATED_ROOT
# through), which fails without a boot manifest ("rootvp not authenticated after mounting").
# panic-spin=1 (k27 kernel) keeps a panicked VM from restarting, so its panic text can still be read.
cd "$(dirname "$0")/.."
SECS=$1; shift; ARGS=(rootauth=0); while [ $# -gt 0 ] && [ "$1" != -- ]; do ARGS+=("$1"); shift; done; shift
# + the legacy DiskImages driver (IOHDIXController) and its backing stores: hdiutil and DiskImages.framework attach through it
# ("DI_kextExists: cannot find IOHDIXController object" -> attach failed, Device not configured). Their space is clear of the
# k27 kernel (tmpfs, by contrast, lies inside its __TEXT_EXEC).
DI_KEXTS="com.apple.driver.DiskImages com.apple.driver.DiskImages.FileBackingStore com.apple.driver.DiskImages.KernelBacked com.apple.driver.DiskImages.RAMBackingStore com.apple.driver.DiskImages.ReadWriteDiskImage com.apple.driver.DiskImages.UDIFDiskImage"
[ $# -gt 0 ] || set -- $(cat configs/kc-keep.txt) $([ "${K27_DI:-1}" = 1 ] && echo $DI_KEXTS)   # hdiutil's IOHDIXController; K27_DI=0 leaves them out
# MACOS_PCIE=1: Apple's PCIe bridge and virtio drivers on crosvm's virtio-pci, MSI through DroidVMGicMsi (docs/k27-vmapple-pcie-msi-plan.md)
[ "${MACOS_PCIE:-}" = 1 ] && set -- "$@" com.apple.driver.AppleVirtualPlatform com.apple.driver.AppleVirtIO
export MACOS_LP_SIP0=${MACOS_LP_SIP0-0x2}
export MACOS_BOOT_MANIFEST_HASH=${MACOS_BOOT_MANIFEST_HASH-1}   # /chosen/boot-manifest-hash, which 27's Image4 needs (scripts/run-macos-vm.py)
NATIVE=${NATIVE-overlay/kext/NativeVirtioBlock.json overlay/kext/NativeAES.json overlay/kext/NativeRamBlock.json}   # NativeAES: k27/build-native-aes.sh
[ "${MACOS_DISPLAY:-}" = 1 ] && NATIVE="$NATIVE overlay/kext/ARMPlatformStandIn.json overlay/kext/DroidVMDisplay.json overlay/kext/DroidVMEthernet.json overlay/kext/DroidVMInput.json"
[ "${MACOS_GPU:-}" = 1 ] && NATIVE="$NATIVE overlay/kext/DroidVMGpu.json"
[ "${MACOS_VIDEO:-}" = 1 ] && NATIVE="$NATIVE overlay/kext/DroidVMVideo.json"   # k27/build-native-video.sh
[ "${MACOS_AUDIO:-}" = 1 ] && NATIVE="$NATIVE overlay/kext/DroidVMAudio.json"   # k27/build-native-audio.sh
[ "${MACOS_PCIE:-}" = 1 ] && NATIVE="$NATIVE overlay/kext/DroidVMGicMsi.json"   # scripts/build-native-kext.py DroidVMGicMsi overlay/kext/DroidVMGicMsi.cpp overlay/kext/NativeKextGlue.cpp --obj k27-obj
K=out/k27/kernel-k27.macho; KC=out/k27/kc-k27.bin; export MACOS_KERNEL=$PWD/$KC
mkdir -p out/rig; llvm-nm -n --defined-only $K > out/rig/kc-k27.nm
python3 k27/kc-build27.py out/kc/kc27.bin $K $KC --keep "$@" ${NATIVE:+--native $NATIVE} > out/k27/kc-build.log 2>&1
rc=$?; grep -E "Unresolv|Error|not defined|lack|wrote|Traceback|vtable slot|conflict" out/k27/kc-build.log | cut -c1-300
[ "$rc" = 0 ] || { echo "kc-build27 failed ($rc), not booted"; exit 1; }
[ -n "${K27_NO_BOOT:-}" ] && exit 0
sleep 12
for try in 1 2 3; do
  DMESG_LINES=3000 MACOS_KERNEL=$PWD/$KC timeout $((SECS + 300)) scripts/xnu12377-smoke.sh $SECS "${ARGS[@]}" > /tmp/smoke.out 2>&1
  grep -q "failed to start VM" /tmp/smoke.out || break
  sleep 30
done
cp /tmp/xnu12377-serial.log out/k27/last-serial.log 2>/dev/null
scripts/kc-panic.sh 6000 | grep -a -v "PC=0x0000000000000000" | head -${PANIC_LINES:-110}
grep -a -v "FIPSPOST\|DebuggerXCall\|magazine" /tmp/smoke.out | tail -${TAIL:-20} | cut -c1-220
