#!/usr/bin/env bash
# Rebuild the KC from the current kernel with the given kept kexts and boot it once: kc-try.sh SECONDS BOOTARGS... [-- BUNDLE_ID...]
#   without bundle IDs the kept kexts are configs/kc-keep.txt; NATIVE defaults to the native kexts of the launchd bring-up
cd "$(dirname "$0")/.."
SECS=$1; shift; ARGS=(); while [ $# -gt 0 ] && [ "$1" != -- ]; do ARGS+=("$1"); shift; done; shift
[ $# -gt 0 ] || set -- $(cat configs/kc-keep.txt)
export MACOS_LP_SIP0=${MACOS_LP_SIP0-0x2}   # CSR_ALLOW_UNRESTRICTED_FS: the dyld cache has no SF_RESTRICTED (temporary, docs/xnu-12377-port.md)
NATIVE=${NATIVE-overlay/kext/NativeVirtioBlock.json overlay/kext/NativeAES.json overlay/kext/NativeRamBlock.json}
K=out/x12377/kernel12377e-osx-kc.macho; KC=out/x12377/kc12377e-m2.bin
llvm-nm -n --defined-only $K > out/rig/kc12377e-m2.nm
python3 scripts/kc-build.py out/kc/kc265.bin $K $KC --keep "$@" ${NATIVE:+--native $NATIVE} 2>&1 | grep -E "Unresolv|Error|not defined|wrote|Traceback" | cut -c1-300 || exit 1
sleep 12
for try in 1 2 3; do
  DMESG_LINES=3000 MACOS_KERNEL=$PWD/$KC timeout 400 scripts/xnu12377-smoke.sh $SECS "${ARGS[@]}" > /tmp/smoke.out 2>&1
  grep -q "failed to start VM" /tmp/smoke.out || break   # the previous VM is still shutting down
  sleep 30
done
scripts/kc-panic.sh 500
grep -a -v "FIPSPOST\|DebuggerXCall\|magazine" /tmp/smoke.out | tail -${TAIL:-20} | cut -c1-220
