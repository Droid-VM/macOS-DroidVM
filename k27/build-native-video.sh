#!/usr/bin/env bash
# DroidVMVideo (overlay/kext/DroidVMVideo, described by overlay/kext/DroidVMVideo.json; objects in out/x12377/native-kexts/DroidVMVideo):
# the DroidVM board's VideoToolbox paravirtualization over virtio-media, UniXNU-droidvm package/DroidVMVirtioMedia.c,
# DroidVMVTParavirt.cpp, DroidVMVTHost.cpp and their headers at VT_REF, exported to out/k27/src/DroidVMVideo, with patches/droidvm-video.
# Its buffers come from one contiguous allocation (DROIDVM_DEVICE_DYNAMIC: a native kext's __DATA has no room for them).
set -eu
K27=$(cd "$(dirname "$0")" && pwd); M=$(dirname "$K27"); D=$M/overlay/kext/DroidVMVideo
VT_REF=fab4fb1   # Droid-VM/UniXNU-droidvm wip/hackintosh, 2026-11-02
V=$M/out/k27/src/DroidVMVideo; rm -rf $V; mkdir -p $V
for name in DroidVMVirtioMedia.c DroidVMVTParavirt.cpp DroidVMVTHost.cpp DroidVMVTWire.h DroidVMDmaRegion.h; do
  git -C $M/sources/UniXNU-droidvm show $VT_REF:package/$name > $V/$name
done
for patch in $M/patches/droidvm-video/*.patch; do patch -p1 -s --batch -d $V -i $patch || { echo "$patch does not apply"; exit 1; }; done
cd $M
python3 scripts/build-native-kext.py DroidVMVideo $D/DroidVMVideo.cpp $V/DroidVMVirtioMedia.c $V/DroidVMVTParavirt.cpp $V/DroidVMVTHost.cpp \
  overlay/kext/NativeKextGlue.cpp -I $V -D DROIDVM_NATIVE_KEXT=1 -D DROIDVM_DEVICE_DYNAMIC=1 --obj k27-obj --c-recipe osfmk/DEVELOPMENT/startup.o.json
