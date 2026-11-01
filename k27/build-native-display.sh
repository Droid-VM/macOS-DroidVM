#!/usr/bin/env bash
# DroidVMDisplay (overlay/kext/DroidVMDisplay, described by overlay/kext/DroidVMDisplay.json; objects in
# out/x12377/native-kexts/DroidVMDisplay) against macOS 27's IOMobileFramebuffer/IOMobileFramebufferLegacy: its
# IOMobileFramebufferABI.h is regenerated from the 27 collection (scripts/gen-iomfb-abi.py out/kc/kc27.bin) and must come out unchanged.
# The kext also carries the DroidVM board's virtio-gpu transport and 3D contexts (UniXNU-droidvm package/DroidVMVirtioGpu.{h,cpp} and
# DroidVMVirtioGpu3D.cpp at VGPU_REF, exported to out/k27/src/DroidVMVirtioGpu), whose buffers come from one contiguous allocation
# (DROIDVM_VIRTIO_GPU_DYNAMIC: a native kext's __DATA has no room for 8 MiB), with patches/droidvm-display. Their user ABI, DroidVMVirtgpuABI.h, is NativeAdreno's:
# run scripts/build-droidvm-gpu.py first (it exports NativeAdreno to out/x12377/src-gpu).
set -eu
K27=$(cd "$(dirname "$0")" && pwd); M=$(dirname "$K27"); D=$M/overlay/kext/DroidVMDisplay
VGPU_REF=59ec0a814ea407f0f635af0ceb30d5147414ee15   # Droid-VM/UniXNU-droidvm wip/hackintosh, 2026-11-02
ABI=$M/out/x12377/src-gpu/drivers/NativeAdreno
[ -f $ABI/DroidVMVirtgpuABI.h ] || { echo "no $ABI/DroidVMVirtgpuABI.h: run scripts/build-droidvm-gpu.py first"; exit 1; }
python3 $M/scripts/gen-iomfb-abi.py $M/out/kc/kc27.bin $D/IOMobileFramebufferABI.h
git -C $M diff --quiet -- $D/IOMobileFramebufferABI.h || { echo "$D/IOMobileFramebufferABI.h changed: the 27 collection's ABI moved"; exit 1; }
V=$M/out/k27/src/DroidVMVirtioGpu; mkdir -p $V
for name in DroidVMVirtioGpu.h DroidVMVirtioGpu.cpp DroidVMVirtioGpu3D.cpp; do
  git -C $M/sources/UniXNU-droidvm show $VGPU_REF:package/$name > $V/$name
done
for patch in $M/patches/droidvm-display/*.patch; do patch -p1 -s --batch -d $V -i $patch || { echo "$patch does not apply"; exit 1; }; done
cd $M
python3 scripts/build-native-kext.py DroidVMDisplay $D/DroidVMDisplay.cpp $V/DroidVMVirtioGpu.cpp $V/DroidVMVirtioGpu3D.cpp overlay/kext/NativeKextGlue.cpp \
  -I $D -I $V -I $ABI -D DROIDVM_VIRTIO_GPU_DYNAMIC=1 --obj k27-obj
