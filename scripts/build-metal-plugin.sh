#!/usr/bin/env bash
# Build the macOS Metal plugin, out/metal/plugin/NativeAdrenoMetal.bundle: overlay/metal/NativeAdrenoMetalPlugin.mm, UniXNU's native Metal frontend
# and bridge (scripts/build-metal-bridge-macos.py) and Turnip beside it (scripts/build-turnip-macos.py), then stage it with metal-probe
# (scripts/build-metal-probe.sh builds that) for a boot: MACOS_DATA_SEED=out/metal/stage/scratch-data.img
# MACOS_TRUSTCACHE=out/metal/stage/kernel.macho.trustcache, stderr-log=1.
#   build-metal-plugin.sh [--no-deps]     --no-deps: reuse the built Turnip and bridge
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "${1:-}" != --no-deps ]; then
  python3 scripts/build-turnip-macos.py
  python3 scripts/build-metal-bridge-macos.py
fi
U=sources/UniXNU/drivers/NativeMetal
O=out/metal/plugin
B=$O/NativeAdrenoMetal.bundle/Contents
rm -rf $O/NativeAdrenoMetal.bundle
mkdir -p "$B/MacOS"
CXX=(/usr/lib/llvm-21/bin/clang++ -target arm64e-apple-macos14.0 -isysroot toolchains/sdks/MacOSX26.1.sdk -fobjc-arc -O2 -std=c++17
     -Wno-deprecated-declarations -c -x objective-c++ -I $U)
"${CXX[@]}" overlay/metal/NativeAdrenoMetalPlugin.mm -o $O/plugin.o
"${CXX[@]}" $U/NativeBridgeMetalFrontend.mm -o $O/frontend.o
python3 scripts/apple-ld.py -bundle -dead_strip -o $B/MacOS/NativeAdrenoMetal $O/plugin.o $O/frontend.o out/metal/bridge/libnative_metal_bridge.a \
  -framework Foundation -framework Metal -framework IOSurface -framework IOKit -framework CoreFoundation -framework IOGPU \
  -lobjc -lc++ -lSystem -liconv 2>&1 | grep -v "was built for newer" || true
cp out/metal/mesa-tu/src/freedreno/vulkan/libvulkan_freedreno.dylib $B/MacOS/
python3 - "$B/Info.plist" <<'EOF'
import plistlib, sys
open(sys.argv[1], 'wb').write(plistlib.dumps(dict(
    CFBundleIdentifier='org.droidvm.NativeAdrenoMetal', CFBundleExecutable='NativeAdrenoMetal', CFBundlePackageType='BNDL',
    CFBundleVersion='1', CFBundleShortVersionString='1', NSPrincipalClass='NativeAdrenoMetalDevice',
    CFBundleSupportedPlatforms=['MacOSX'], LSMinimumSystemVersion='14.0'), fmt=plistlib.FMT_XML))
EOF
[ -x out/metal/probe/metal-probe ] || bash scripts/build-metal-probe.sh
python3 scripts/stage-gpu-plugin.py --probe out/metal/probe/metal-probe ${STAGE_ARGS:-} $O/NativeAdrenoMetal.bundle
