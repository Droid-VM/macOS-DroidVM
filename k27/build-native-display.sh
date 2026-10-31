#!/usr/bin/env bash
# DroidVMDisplay for k27 (objects in out/x12377/native-kexts/k27-DroidVMDisplay, described by k27/kext/DroidVMDisplay.json): the same
# source against macOS 27's IOMobileFramebuffer/IOMobileFramebufferLegacy (k27/kext/DroidVMDisplay/IOMobileFramebufferABI.h, from
# scripts/gen-iomfb-abi.py out/kc/kc27.bin): 27 drops get/set_programfifo_blocked_state and get_diags_handler and adds task,
# genlock and LPR methods, which moves the slots. The source stays untouched: it is copied to out/k27/src next to that header.
set -eu
K27=$(cd "$(dirname "$0")" && pwd); M=$(dirname "$K27")
S=$M/out/k27/src/DroidVMDisplay; mkdir -p $S
python3 $M/scripts/gen-iomfb-abi.py $M/out/kc/kc27.bin $K27/kext/DroidVMDisplay/IOMobileFramebufferABI.h
cp $M/overlay/kext/DroidVMDisplay/DroidVMDisplay.cpp $K27/kext/DroidVMDisplay/IOMobileFramebufferABI.h $S/
# The offsets into IOMobileFramebufferLegacy and IOMFBSwapIORequest that the driver hard-codes, 26.5 -> 27, each from the same
# instruction of the same function in both collections (k27/offset-map.py; the function per offset in k27/TODO.md).
python3 - $S/DroidVMDisplay.cpp <<'PY'
import re, sys
p = sys.argv[1]; s = open(p).read()
CONST = {'kCurrentSwap': (6032, 6720), 'kSwapQueueFirst': (6040, 6728), 'kSwapQueueLast': (6048, 6736),
         'kDisplayWidth': (6400, 7152), 'kDisplayHeight': (6404, 7156), 'kSystemPowerState': (6428, 7180),
         'kAPIPowerState': (6432, 7184), 'kHardwarePowered': (6436, 7188), 'kSwapInfoHeld': (6902, 7634),
         'kSwapLayers': (824, 984), 'kSwapDropReasons': (844, 1004), 'kSwapInfoA': (752, 912), 'kSwapInfoB': (816, 976),
         'kSwapMainSurface': (2752, 2944), 'kSwapNext': (3192, 3384), 'kSwapPrev': (3200, 3392)}
for name, (old, new) in CONST.items():
    pattern = r'(static constexpr size_t %s = )%d;' % (name, old)
    assert len(re.findall(pattern, s)) == 1, name
    s = re.sub(pattern, r'\g<1>%d;' % new, s)
# 27's family takes 27's 1760-byte swap record itself: converting it to 26.5's 1416 bytes fails the dispatch size check (0xe00002c2)
replaces = [('virt_set_external_method_hook(convertSwapRecord);', '(void)convertSwapRecord;   // k27: no conversion')]
replaces += [('at<uint32_t>(this, 6412)', 'at<uint32_t>(this, 7164)'), ('at<uint32_t>(swap, 820)', 'at<uint32_t>(swap, 980)')]
for old, new in replaces:
    assert old in s, old
    s = s.replace(old, new)
open(p, 'w').write(s)
PY
cd $M
python3 scripts/build-native-kext.py k27-DroidVMDisplay $S/DroidVMDisplay.cpp overlay/kext/NativeKextGlue.cpp -I $S -I $M/overlay/kext/DroidVMDisplay --obj k27-obj
