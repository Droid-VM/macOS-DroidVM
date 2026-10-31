#!/usr/bin/env bash
# DroidVMDisplay (overlay/kext/DroidVMDisplay, described by overlay/kext/DroidVMDisplay.json; objects in
# out/x12377/native-kexts/DroidVMDisplay) against macOS 27's IOMobileFramebuffer/IOMobileFramebufferLegacy: its
# IOMobileFramebufferABI.h is regenerated from the 27 collection (scripts/gen-iomfb-abi.py out/kc/kc27.bin) and must come out unchanged.
set -eu
K27=$(cd "$(dirname "$0")" && pwd); M=$(dirname "$K27"); D=$M/overlay/kext/DroidVMDisplay
python3 $M/scripts/gen-iomfb-abi.py $M/out/kc/kc27.bin $D/IOMobileFramebufferABI.h
git -C $M diff --quiet -- $D/IOMobileFramebufferABI.h || { echo "$D/IOMobileFramebufferABI.h changed: the 27 collection's ABI moved"; exit 1; }
cd $M
python3 scripts/build-native-kext.py DroidVMDisplay $D/DroidVMDisplay.cpp overlay/kext/NativeKextGlue.cpp -I $D --obj k27-obj
