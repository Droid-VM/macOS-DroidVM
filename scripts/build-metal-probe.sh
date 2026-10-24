#!/usr/bin/env bash
# Build the Metal plugin probe (overlay/metal/MetalProbePlugin.mm as out/metal/probe/NativeAdrenoMetal.bundle) and metal-probe, then stage
# them for a boot: MACOS_DATA_SEED=out/metal/stage/scratch-data.img MACOS_TRUSTCACHE=out/metal/stage/kernel.macho.trustcache, stderr-log=1.
set -euo pipefail
cd "$(dirname "$0")/.."
O=out/metal/probe
B=$O/NativeAdrenoMetal.bundle/Contents
mkdir -p "$B/MacOS"
CXX=(/usr/lib/llvm-21/bin/clang++ -target arm64e-apple-macos14.0 -isysroot toolchains/sdks/MacOSX26.1.sdk -fobjc-arc -O2 -Wall -c -x objective-c++)
"${CXX[@]}" overlay/metal/MetalProbePlugin.mm -o $O/probe.o
"${CXX[@]}" overlay/metal/metal-probe.mm -o $O/metal-probe.o
python3 scripts/apple-ld.py -bundle -o $B/MacOS/NativeAdrenoMetal $O/probe.o -framework Foundation -framework IOKit -framework IOGPU -lobjc -lSystem -lc++
python3 scripts/apple-ld.py -execute -o $O/metal-probe $O/metal-probe.o -framework Foundation -framework Metal -lobjc -lSystem -lc++
python3 - "$B/Info.plist" <<'EOF'
import plistlib, sys
open(sys.argv[1], 'wb').write(plistlib.dumps(dict(
    CFBundleIdentifier='org.droidvm.NativeAdrenoMetal', CFBundleExecutable='NativeAdrenoMetal', CFBundlePackageType='BNDL',
    CFBundleVersion='1', CFBundleShortVersionString='1', NSPrincipalClass='NativeAdrenoMetalDevice',
    CFBundleSupportedPlatforms=['MacOSX'], LSMinimumSystemVersion='14.0'), fmt=plistlib.FMT_XML))
EOF
python3 scripts/stage-gpu-plugin.py --probe $O/metal-probe $O/NativeAdrenoMetal.bundle
