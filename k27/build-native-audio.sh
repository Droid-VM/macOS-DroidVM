#!/usr/bin/env bash
# DroidVMAudio (overlay/kext/DroidVMAudio, described by overlay/kext/DroidVMAudio.json; objects in out/x12377/native-kexts/DroidVMAudio):
# the DroidVM board's speaker and microphone (IOAudio2Devices) over virtio-snd, UniXNU-droidvm package/DroidVMAudio.cpp and
# DroidVMVirtioSnd.c at AUDIO_REF, exported to out/k27/src/DroidVMAudio, with patches/droidvm-audio.
# Its buffers come from one contiguous allocation (DROIDVM_DEVICE_DYNAMIC: a native kext's __DATA has no room for them).
set -eu
K27=$(cd "$(dirname "$0")" && pwd); M=$(dirname "$K27"); D=$M/overlay/kext/DroidVMAudio
AUDIO_REF=e29d087   # Droid-VM/UniXNU-droidvm wip/hackintosh, 2026-11-04 (audio itself from 1f57203, the iPadOS 27 board)
V=$M/out/k27/src/DroidVMAudio; rm -rf $V; mkdir -p $V
for name in DroidVMAudio.cpp DroidVMVirtioSnd.c DroidVMDmaRegion.h; do
  git -C $M/sources/UniXNU-droidvm show $AUDIO_REF:package/$name > $V/$name
done
for patch in $M/patches/droidvm-audio/*.patch; do patch -p1 -s --batch -d $V -i $patch || { echo "$patch does not apply"; exit 1; }; done
cd $M
python3 scripts/build-native-kext.py DroidVMAudio $D/DroidVMAudioStarter.cpp $V/DroidVMAudio.cpp $V/DroidVMVirtioSnd.c \
  overlay/kext/NativeKextGlue.cpp -I $V -D DROIDVM_NATIVE_KEXT=1 -D DROIDVM_DEVICE_DYNAMIC=1 --obj k27-obj --c-recipe osfmk/DEVELOPMENT/startup.o.json
