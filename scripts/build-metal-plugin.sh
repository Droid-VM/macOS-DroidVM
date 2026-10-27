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
    ('@property(nonatomic) NSUInteger heapOffset;\n@end\n// A no-copy import keeps its pages',
     '@property(nonatomic) NSUInteger heapOffset;\n@property(nonatomic) BOOL counted;   // its surface counted in use (countUse)\n'
     '- (void)countUse;\n@end\n'
     '// The render server counts the surfaces it textures in use while the textures live (countUse).\n'
     'static const bool gCountsSurfaceUse=!strcmp(getprogname(),"WindowServer");\n// A no-copy import keeps its pages'),
    ('- (void)dealloc {nmb_texture_release(_handle);if(_surface)CFRelease(_surface);}\n',
     '- (void)dealloc {nmb_texture_release(_handle);if(_surface){if(_counted)IOSurfaceDecrementUseCount(_surface);CFRelease(_surface);}}\n'
     '- (void)countUse {if(_surface && !_counted && gCountsSurfaceUse){IOSurfaceIncrementUseCount(_surface);_counted=YES;}}\n'),
    (' if(_surface)view.surface=(IOSurfaceRef)CFRetain(_surface);\n',
     ' if(_surface){view.surface=(IOSurfaceRef)CFRetain(_surface);[view countUse];}\n'),
    ('texture.surface=(IOSurfaceRef)CFRetain(surface);return (id<MTLTexture>)texture;\n',
     'texture.surface=(IOSurfaceRef)CFRetain(surface);[texture countUse];return (id<MTLTexture>)texture;\n'),
    # A texture the heap has no room for is made on the device instead. Core Animation sizes a heap from heapTextureSizeAndAlign...:
    # SecurityAgent's user list (with a user account) asked a 128 KiB heap holding 65 KiB for a 235x89 texture the runtime placed in
    # more than the rest, and its login UI never showed (WindowServer kept the black transition frames).
    (' if(!handle){NBLOG(@"native-metal: heap texture refused: %@",lastError());return nil;}\n',
     ' if(!handle){uint64_t answer[2]={0,0};nmb_device_heap_texture_size_and_align(gDevice,&descriptor,answer);\n'
     '  NBLOG(@"native-metal: heap texture answered size %llu align %llu, heap %llu used %llu; %lux%lu format %lu mips %lu usage %lx '
     'offset %llx: %@; made on the device",answer[0],answer[1],nmb_heap_size(_handle),nmb_heap_used_size(_handle),(unsigned long)d.width,'
     '(unsigned long)d.height,(unsigned long)d.pixelFormat,(unsigned long)d.mipmapLevelCount,(unsigned long)d.usage,(unsigned long long)offset,'
     'lastError());\n'
     '  handle=nmb_texture_new(gDevice,&descriptor);if(!handle){NBLOG(@"native-metal: texture refused: %@",lastError());return nil;}}\n'),
    (' NBHeap *heap=[NBHeap new];heap.handle=handle;',
     ' NBLOG(@"native-metal: heap %lu bytes type %ld options %lx -> %llu",(unsigned long)d.size,(long)d.type,(unsigned long)d.resourceOptions,'
     'nmb_heap_size(handle));\n NBHeap *heap=[NBHeap new];heap.handle=handle;'),
    # The runtime converts a two-plane YCbCr texture on the CPU at every encoder that uses it (planes copied to staging, then a
    # dispatch): WindowServer's 4096x2160 wallpaper frames (YCBCR8_444_2P) took the 4 GiB guest into jetsam. Above 1 Mpx it is
    # refused, and the server draws the wallpaper its other way; the small backdrop samples (512x512) are made.
    (' NmbTextureDescriptor descriptor;if(!buffer || !textureDescriptor(d,&descriptor))return nil;\n const uint64_t base=(uintptr_t)IOSurfaceGetBaseAddress(surface),',
     ' NmbTextureDescriptor descriptor;if(!buffer || !textureDescriptor(d,&descriptor))return nil;\n'
     ' if(d.pixelFormat>=500 && d.pixelFormat<600 && (uint64_t)d.width*d.height>1024*1024){\n'
     '  static std::atomic<unsigned> refusals;   // the server asks again at every frame\n'
     '  if(refusals++<4)NBLOG(@"native-metal: surface texture refused: %lux%lu YCbCr format %lu converts on the CPU",(unsigned long)d.width,'
     '(unsigned long)d.height,(unsigned long)d.pixelFormat);\n'
     '  return nil;}\n'
     ' const uint64_t base=(uintptr_t)IOSurfaceGetBaseAddress(surface),'),
    # Core Animation makes a texture of each window's surface at every frame and drops it when the frame completes, so the weak import
    # table lost the import between frames: each frame imported every surface again and freed the last import (Turnip allocate and
    # free, kernel calls), most of the render server's busy samples in a window drag. Imports used in the last second stay held.
    ('static NBBuffer *surfaceBuffer(IOSurfaceRef surface,void *base,size_t bytes) {\n',
     '#include <map>\n#include <tuple>\n'
     'struct HeldImport {NBBuffer *buffer;uint64_t usedUs;};\n'
     'static std::map<std::tuple<uint64_t,uint64_t,uint64_t>,HeldImport> gHeldImports;   // under gSurfaceImportLock\n'
     'static void holdImport(uint64_t identity,uint64_t address,uint64_t bytes,NBBuffer *buffer) {\n'
     ' const uint64_t now=nowUs();gHeldImports[{identity,address,bytes}]={buffer,now};\n'
     ' for(auto it=gHeldImports.begin();it!=gHeldImports.end();)it=now-it->second.usedUs>1000000?gHeldImports.erase(it):std::next(it);\n'
     ' while(gHeldImports.size()>64) {\n'
     '  auto oldest=gHeldImports.begin();\n'
     '  for(auto it=gHeldImports.begin();it!=gHeldImports.end();++it)if(it->second.usedUs<oldest->second.usedUs)oldest=it;\n'
     '  gHeldImports.erase(oldest);\n'
     ' }\n'
     '}\n'
     'static NBBuffer *surfaceBuffer(IOSurfaceRef surface,void *base,size_t bytes) {\n'),
    (' if(buffer)return buffer;\n',
     ' if(buffer){holdImport(value.identity,value.address,value.bytes,buffer);return buffer;}\n'),
    ('  [gSurfaceImports setObject:buffer forKey:key];\n }\n return buffer;\n',
     '  [gSurfaceImports setObject:buffer forKey:key];\n  holdImport(value.identity,value.address,value.bytes,buffer);\n }\n return buffer;\n'),
]:
    assert s.count(old) == 1, old
    s = s.replace(old, new)
open(sys.argv[2], 'w').write(s)
PY
"${CXX[@]}" $O/frontend.mm -o $O/frontend.o
python3 scripts/apple-ld.py -bundle -dead_strip -o $B/MacOS/NativeAdrenoMetal $O/plugin.o $O/frontend.o out/metal/bridge/libnative_metal_bridge.a \
  -framework Foundation -framework Metal -framework IOSurface -framework IOKit -framework CoreFoundation -framework IOGPU \
  -lobjc -lc++ -lSystem -liconv 2>&1 | { grep -v "was built for newer" || true; }   # a failed link fails the build (pipefail)
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
