#!/usr/bin/env bash
# Build the macOS Metal plugin, out/metal/plugin/NativeAdrenoMetal.bundle: overlay/metal/NativeAdrenoMetalPlugin.mm, UniXNU's native Metal frontend
# and bridge (scripts/build-metal-bridge-macos.py) and Turnip beside it (scripts/build-turnip-macos.py). scripts/product.py takes it from there.
#   build-metal-plugin.sh [--no-deps]     --no-deps: reuse the built Turnip and bridge
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "${1:-}" != --no-deps ]; then
  python3 scripts/build-turnip-macos.py
  python3 scripts/build-metal-bridge-macos.py
fi
# NATIVE_METAL_SOURCE selects the integrated frontend and the matching bridge sources.
U=${NATIVE_METAL_SOURCE:-sources/UniXNU/drivers/NativeMetal}
O=out/metal/plugin
B=$O/NativeAdrenoMetal.bundle/Contents
rm -rf $O/NativeAdrenoMetal.bundle
mkdir -p "$B/MacOS"
CXX=(/usr/lib/llvm-21/bin/clang++ -target arm64e-apple-macos14.0 -isysroot toolchains/sdks/MacOSX26.1.sdk -fobjc-arc -O2 -std=c++17
     -Wno-deprecated-declarations -c -x objective-c++ -I $U)
"${CXX[@]}" overlay/metal/NativeAdrenoMetalPlugin.mm -o $O/plugin.o
# The frontend as it is: NativeMetal wip/hackintosh (af958ac, 43f78ae) took in what this script used to patch into it (XR10 for
# WindowServer only, 4:2:0 planes read in place, surfaces counted in use from commit to completion, large YCbCr surfaces refused).
python3 - $U/NativeBridgeMetalFrontend.mm $O/frontend.mm <<'PY'
import sys
s = open(sys.argv[1]).read()
# NMB_FRAME_ROWS=1 (diagnostics, research/debug-2026-10-27): WindowServer's telemetry table every 20 s without NATIVE_METAL_TIMING in
# its launchd job, and each K row (a commit) with its GPU time (GPUEndTime - GPUStartTime) and its encoding (command buffer made to commit).
import os
if os.environ.get('NMB_FRAME_ROWS') == '1':
    for old, new in [
        (' if(!getenv("NATIVE_METAL_TIMING"))return;\n',
         ' if(!getenv("NATIVE_METAL_TIMING") && strcmp(getprogname(),"WindowServer"))return;\n'),
        ('struct CommitRecord {uint64_t committedUs=0,callbackUs=0,ageUs=0;',
         'struct CommitRecord {uint64_t committedUs=0,callbackUs=0,ageUs=0,gpuUs=0;'),
        (' {\n  const uint64_t took=nowUs()-commandBuffer.committedUs;\n',
         ' {\n  const uint64_t took=nowUs()-commandBuffer.committedUs;\n'
         '  const double gpuSeconds=[commandBuffer GPUEndTime]-[commandBuffer GPUStartTime];\n'),
        ('  if(r.index==commandBuffer.commitIndex) {\n   r.callbackUs=took;\n',
         '  if(r.index==commandBuffer.commitIndex) {\n   r.callbackUs=took;r.gpuUs=gpuSeconds>0?(uint64_t)(gpuSeconds*1e6):0;\n'),
        ('   row("K%u t=%llu.%03llus rp%u dr%u kpx%llu cs%u bl%u ctc=%lluus",',
         '   row("K%u t=%llu.%03llus rp%u dr%u kpx%llu cs%u bl%u ctc=%lluus gpu=%lluus enc=%lluus",'),
        ('(ull)(r.work.pixels>>10),r.work.dispatches,r.work.blits,(ull)r.callbackUs);',
         '(ull)(r.work.pixels>>10),r.work.dispatches,r.work.blits,(ull)r.callbackUs,(ull)r.gpuUs,(ull)r.ageUs);'),
    ]:
        assert s.count(old) == 1, old
        s = s.replace(old, new)
open(sys.argv[2], 'w').write(s)
PY
# NMB_TRACE=1: the frontend's bridge calls go through tools/m2vsim's recorder, which the boot argument nmb-trace=1 turns on in
# WindowServer (a trace for tools/m2vsim's replay on the host).
TRACE=()
if [ "${NMB_TRACE:-0}" = 1 ]; then
  python3 tools/m2vsim/gen_trace.py $U/bridge/NativeMetalObjects.h $O/trace
  TRACE=(-include $O/trace/nmb_trace_redirect.h)
  "${CXX[@]}" -x c++ -I $O/trace -I tools/m2vsim tools/m2vsim/trace_record.cpp -o $O/trace_record.o
fi
"${CXX[@]}" "${TRACE[@]}" $O/frontend.mm -o $O/frontend.o
# NMB_LATENCY=1 (diagnostics): WindowServer's frame latency rows and update-thread samples (research/debug-2026-10-28/WSLatency.mm).
LATENCY=()
if [ "${NMB_LATENCY:-0}" = 1 ]; then
  "${CXX[@]}" research/debug-2026-10-28/WSLatency.mm -o $O/latency.o
  LATENCY=($O/latency.o)
fi
python3 scripts/apple-ld.py -bundle -dead_strip -o $B/MacOS/NativeAdrenoMetal $O/plugin.o $O/frontend.o ${TRACE:+$O/trace_record.o} "${LATENCY[@]}" \
  out/metal/bridge/libnative_metal_bridge.a \
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
# The build the Shader Cache app (scripts/build-shader-cache-app.py) compares its last run with: a plugin or Turnip built otherwise
# shows the system shader cache as needing an update.
mkdir -p "$B/Resources"
python3 - "$B" <<'EOF'
import hashlib, json, sys
from pathlib import Path
contents = Path(sys.argv[1])
digest = hashlib.sha256()
for name in ('NativeAdrenoMetal', 'libvulkan_freedreno.dylib'):
    digest.update((contents / 'MacOS' / name).read_bytes())
(contents / 'Resources/gpu-build.json').write_text(json.dumps({'metal_source_sha256': digest.hexdigest()}) + '\n')
EOF
# The bundle only: scripts/product.py makes the trust cache and boot disk from it and puts it into the guest (install-plugin).
# STAGE=1 (the seed-and-overlay Data model, before the single-container disk): also stage it into a Data seed with metal-probe.
# Without STAGE_ARGS=--base/--store that makes a new seed, which resets such a VM's Data.
[ "${STAGE:-}" = 1 ] || exit 0
[ -x out/metal/probe/metal-probe ] || bash scripts/build-metal-probe.sh
python3 scripts/stage-gpu-plugin.py --probe out/metal/probe/metal-probe ${STAGE_ARGS:-} $O/NativeAdrenoMetal.bundle
