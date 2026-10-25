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
# The frontend with the render server's IOSurface use counts (Droid-VM/UniXNU 9eb0d75, build-adreno-metal-plugin.py): Apple's GPU driver
# counts a surface in use (IOSurfaceIncrementUseCount) while a GPU resource is made of it, and an app's Core Animation draws into a
# backing store in place, or recycles it for another layer, only while it is not in use. With nothing counted, WindowServer composed
# surfaces being redrawn (SecurityAgent's password field came out as broken wedges). Only the render server counts: an app's own
# textures (its drawables) would look in use forever.
python3 - $U/NativeBridgeMetalFrontend.mm $O/frontend.mm <<'PY'
import sys
s = open(sys.argv[1]).read()
for old, new in [
    ('@property(nonatomic) NSUInteger heapOffset;\n@end\n@implementation NBBuffer',
     '@property(nonatomic) NSUInteger heapOffset;\n@property(nonatomic) BOOL counted;   // its surface counted in use (countUse)\n'
     '- (void)countUse;\n@end\n'
     '// The render server counts the surfaces it textures in use while the textures live (countUse).\n'
     'static const bool gCountsSurfaceUse=!strcmp(getprogname(),"WindowServer");\n@implementation NBBuffer'),
    ('- (void)dealloc {nmb_texture_release(_handle);if(_surface)CFRelease(_surface);}\n',
     '- (void)dealloc {nmb_texture_release(_handle);if(_surface){if(_counted)IOSurfaceDecrementUseCount(_surface);CFRelease(_surface);}}\n'
     '- (void)countUse {if(_surface && !_counted && gCountsSurfaceUse){IOSurfaceIncrementUseCount(_surface);_counted=YES;}}\n'),
    (' if(_surface)view.surface=(IOSurfaceRef)CFRetain(_surface);\n',
     ' if(_surface){view.surface=(IOSurfaceRef)CFRetain(_surface);[view countUse];}\n'),
    (' texture.surface=(IOSurfaceRef)CFRetain(surface);return (id<MTLTexture>)texture;\n',
     ' texture.surface=(IOSurfaceRef)CFRetain(surface);[texture countUse];return (id<MTLTexture>)texture;\n'),
]:
    assert s.count(old) == 1, old
    s = s.replace(old, new)
open(sys.argv[2], 'w').write(s)
PY
"${CXX[@]}" $O/frontend.mm -o $O/frontend.o
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
