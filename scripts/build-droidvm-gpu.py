#!/usr/bin/env python3
"""Build DroidVMGpu (crosvm --droidvm-gpu, the host's KGSL) as a native kext of the collection: overlay/kext/DroidVMGpu.json.

    build-droidvm-gpu.py

The sources are those of UniXNU-droidvm's scripts/build-droidvm-gpu.py at REF (by the wire, below):
NativeAdreno's user client, IOKit surface, execbuf and memory with the PM4 encoder, the hardware classes (NativeAdrenoVm/Ring/Timer)
from package/DroidVMGpu.cpp. NativeAdreno, AdrenoPM4 and ArmSmmu4K are the commits UniXNU's wip/droidvm pins. They are exported to
out/x12377/src-gpu laid out as a UniXNU tree, and that script runs there up to its compile step, so its staged edits (of
NativeAdrenoPublish.cpp, and NativeAdrenoUserClient.cpp or NativeAdrenoMemory.cpp) are used as they are. overlay/kext/DroidVMGpuKext.cpp starts the device.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'out/x12377/src-gpu'
UNIXNU = ROOT / 'sources/UniXNU'
DROIDVM = ROOT / 'sources/UniXNU-droidvm'
# The guest side must speak the wire of the phone's crosvm (DROIDVM_GPU_WIRE): 1 is the App's crosvm of 2026-10-22 (external/crosvm
# drm-droidvm-mmio 7d1e255; UniXNU-droidvm bf7fc44 with NativeAdreno 805c7e4), 3 is crosvm's droidvm wip/virtio-mmio (UniXNU-droidvm
# wip/hackintosh with the NativeAdreno UniXNU wip/droidvm pins).
WIRE = os.environ.get('DROIDVM_GPU_WIRE', '1')
REF, ADRENO_PIN = {'1': ('bf7fc44', '805c7e4bfb7451eb6923f4a14dea8c657b9be7d2'),
                   '3': ('origin/wip/hackintosh', 'b686b9054f57d393c80195b82568a09f8ca106a2')}[WIRE]
PINS = {'drivers/NativeAdreno': ADRENO_PIN, 'kits/AdrenoPM4': '445f8fe6d115738352b9d78dc70af6d61aa7f62f',
        'kits/ArmSmmu4K': '4d0d6598b1a36aeec3de01091893fa6660e49388'}


def git_show(repo, ref, path):
    return subprocess.run(['git', '-C', str(repo), 'show', f'{ref}:{path}'], capture_output=True, check=True).stdout


def export():
    for path, commit in PINS.items():
        stamp = SRC / path / '.commit'
        if stamp.exists() and stamp.read_text() == commit:
            continue
        subprocess.run(['rm', '-rf', str(SRC / path)], check=True)
        (SRC / path).mkdir(parents=True)
        archive = subprocess.run(['git', '-C', str(UNIXNU / path), 'archive', commit], capture_output=True, check=True).stdout
        subprocess.run(['tar', '-x', '-C', str(SRC / path)], input=archive, check=True)
        stamp.write_text(commit)
    (SRC / 'kits/droidvm').mkdir(parents=True, exist_ok=True)
    for name in ('DroidVMGpu.cpp', 'DroidVMGpuWire.h'):
        (SRC / 'kits/droidvm' / name).write_bytes(git_show(DROIDVM, REF, f'package/{name}'))
    (SRC / 'scripts').mkdir(exist_ok=True)
    script = SRC / 'scripts/build-droidvm-gpu.py'
    script.write_bytes(git_show(DROIDVM, REF, 'scripts/build-droidvm-gpu.py'))
    return script


def stage(script):
    """Run the upstream script up to its compiles; returns its globals (staged, staged_memory, ADRENO, ROOT)."""
    text = script.read_text()
    cut = text.find('\ncxx = recipe(')
    if cut < 0:
        sys.exit(f'{script}: no compile step to stop at')
    scope = {'__file__': str(script), '__name__': 'droidvm_gpu_stage'}
    exec(compile(text[:cut], str(script), 'exec'), scope)
    return scope


scope = stage(export())
adreno = scope['ADRENO']
# macOS on top of the staged edits: the render server is WindowServer (iOS's is backboardd), which takes the large window of slot 0 and
# is not capped; 24 connections instead of six (after login WindowServer, loginwindow, SecurityAgent, the menu bar, wallpaper,
# notification and control centre agents, the input menu, the cursor service, the video decoder, Siri and the icon agent each keep one;
# with twelve the later ones failed to open the GPU), the added windows following the others at 256 MiB each, 6.75 GiB of the VBO's
# 128 GiB; and
# 32 opens per process name per boot instead of 8, since the login UI processes are relaunched with each WindowServer.
publish = scope['staged'].read_text()
for name in ('name_', 'opener'):
    old = f'strncmp({name},"backboardd",sizeof {name})'
    new = f'(strncmp({name},"backboardd",sizeof {name}) && strncmp({name},"WindowServer",sizeof {name}))'
    count = {'name_': 1, 'opener': 1}[name]
    if name == 'name_':
        old, new = '!' + old + ' && !g.slots[0]', '!' + new + ' && !g.slots[0]'
    if publish.count(old) != count:
        sys.exit(f'{scope["staged"]}: the render server test on {name} changed')
    publish = publish.replace(old, new)
cap = '(limit && limit<8?limit:8)'
windows = ('enum : unsigned {NativeAdrenoMaxClients=6};\n'
           'static const struct {uint64_t start,bytes;} kClientWindows[NativeAdrenoMaxClients]={\n'
           '    {0x20000000ull,0x40000000ull},{0x60000000ull,0x10000000ull},{0x70000000ull,0x10000000ull},\n'
           '    {0x80000000ull,0x10000000ull},{0x90000000ull,0x10000000ull},{0xa0000000ull,0x10000000ull}};')
if publish.count(cap) != 1 or publish.count(windows) != 1:
    sys.exit(f'{scope["staged"]}: the open cap or the six client windows changed')
publish = publish.replace(cap, '(limit && limit<32?limit:32)')
publish = publish.replace(windows, 'enum : unsigned {NativeAdrenoMaxClients=24};\n'
                          'static const struct {uint64_t start,bytes;} kClientWindows[NativeAdrenoMaxClients]={\n'
                          '    {0x20000000ull,0x40000000ull},' + ','.join('{%#xull,0x10000000ull}' % (0x60000000 + i * 0x10000000)
                                                                    for i in range(23)) + '};')
# Bring-up: a failed call names the process, the method, the status and the window's peak, and a connection's window peak is logged
# each 64 MiB it grows (WindowServer's command stream allocation failed after twenty minutes logged in, with nothing logged).
peak = ("                if(connection->core_->windowPeak()>>20>record->peak_mib)record->peak_mib=uint32_t(connection->core_->windowPeak()>>20);\n"
        "        IOLockUnlock(g.lock);\n")
record = 'struct NativeAdrenoClientRecord {'
if publish.count(record) != 1:
    sys.exit(f'{scope["staged"]}: the client record changed')
publish = publish.replace(record, 'extern "C" volatile uint32_t native_adreno_pool_stats[8];   // [3] pool MiB used, [4] its peak\n' + record)
if publish.count(peak) != 1:
    sys.exit(f'{scope["staged"]}: the window peak record changed')
publish = publish.replace(peak,
    "                if(connection->core_->windowPeak()>>20>record->peak_mib) {\n"
    "                    if((connection->core_->windowPeak()>>26)>(record->peak_mib>>6))IOLog(\"droidvm-gpu: %s window peak %llu MiB, pool %u MiB used, peak %u, pinned %llu+%llu MiB\\n\",connection->name_,connection->core_->windowPeak()>>20,native_adreno_pool_stats[3],native_adreno_pool_stats[4],native_adreno_pinned_bytes[0]>>20,native_adreno_pinned_bytes[1]>>20);\n"
    "                    record->peak_mib=uint32_t(connection->core_->windowPeak()>>20);\n"
    "                }\n"
    "        if(status && connection->live_ && !(method==NativeAdrenoMethodGetStatus && status==kIOReturnUnsupported)) {\n"
    "            static uint32_t logged;\n"
    "            if(logged<200) {++logged;IOLog(\"droidvm-gpu: %s call %u failed %#x, %lu objects, window peak %llu MiB, pool %u MiB used\\n\",connection->name_,method,status,(unsigned long)connection->core_->liveObjects(),connection->core_->windowPeak()>>20,native_adreno_pool_stats[3]);}\n"
    "        }\n"
    "        if(method==NativeAdrenoMethodBoAlloc && !status && connection->live_ && !(connection->core_->liveObjects()%128))\n"
    "            IOLog(\"droidvm-gpu: %s has %lu objects, pool %u MiB used\\n\",connection->name_,(unsigned long)connection->core_->liveObjects(),native_adreno_pool_stats[3]);\n"
    "        IOLockUnlock(g.lock);\n")
imported = '        const IOReturn status=live_?core_->importBo(&request,current_task(),&reply):kIOReturnNotReady;\n'
if publish.count(imported) != 1:
    sys.exit(f'{scope["staged"]}: the import call changed')
publish = publish.replace(imported, imported +
    '        if(live_ && (status || !(core_->liveObjects()%128)))IOLog("droidvm-gpu: %s import of %llu bytes: %#x, %lu objects, pool %u MiB used\\n",'
    'name_,(unsigned long long)request.bytes,status,(unsigned long)core_->liveObjects(),native_adreno_pool_stats[3]);\n')
# Object limits: 1024 live objects per client and 1024 GPU mappings across all of them. WindowServer, the login UI and the agents that
# draw ran out of mappings after ten or twenty minutes logged in (BoMap refused, Turnip's command stream allocation failed with
# VK_ERROR_OUT_OF_DEVICE_MEMORY and WindowServer wrote through the null stream). Every table is scanned linearly and allocated once.
views = 'enum {MaxViews=1024};'
if publish.count(views) != 1:
    sys.exit(f'{scope["staged"]}: the view cache changed')
publish = publish.replace(views, 'enum {MaxViews=4096};   /* NativeAdrenoClientMaxObjects (build-droidvm-gpu.py raises it) */')
for header, old, new in [(adreno / 'NativeAdrenoVm.h', 'NativeAdrenoVmMaxObjects=1024}', 'NativeAdrenoVmMaxObjects=8192}'),
                         (adreno / 'NativeAdrenoUserClient.h', 'NativeAdrenoClientMaxObjects=1024,', 'NativeAdrenoClientMaxObjects=4096,')]:
    text = header.read_text()
    if text.count(new) != 1:
        if text.count(old) != 1:
            sys.exit(f'{header}: the object limit changed')
        header.write_text(text.replace(old, new))
# Submissions of up to 64 command stream entries instead of 16 (the ABI's buffers, NativeAdrenoSubmit's framing and the wire's IBs; the
# phone's crosvm takes as many, droidvm_gpu.rs MAX_IBS): a WindowServer frame of about 107 entries took seven kernel calls, each a
# synchronous round trip to the host on the render server's main thread (13% of it in a window drag).
for path, old, new in [(adreno / 'NativeAdrenoABI.h', 'NativeAdrenoAbiMaxBuffers = 16,', 'NativeAdrenoAbiMaxBuffers = 64,'),
                       (adreno / 'NativeAdrenoABI.h', 'sizeof(NativeAdrenoAbiSubmit) == 416,', 'sizeof(NativeAdrenoAbiSubmit) == 32 + 24 * 64,'),
                       (adreno / 'NativeAdrenoSubmit.cpp', 'SubmitMaxBuffers=16,', 'SubmitMaxBuffers=64,'),
                       # a job's distinct buffers: at 16 a larger submission wrote past them into the next job, and a client's close
                       # then retired garbage handles and poisoned every client's GPU (kc249: WindowServer lost its device at login)
                       (adreno / 'NativeAdrenoSubmit.h', 'uint64_t handles[16]{};', 'uint64_t handles[64]{};'),
                       (SRC / 'kits/droidvm/DroidVMGpuWire.h', 'DROIDVM_GPU_MAX_IBS = 16,', 'DROIDVM_GPU_MAX_IBS = 64,')]:
    text = path.read_text()
    if text.count(new) != 1:
        if text.count(old) != 1:
            sys.exit(f'{path}: the submit limit changed')
        path.write_text(text.replace(old, new))
# The binding table, one row per GPU mapping, on the heap: at the raised mapping limit it would not fit the collection's room for a
# native kext's __DATA (kc-build: no room for a 0x3d730-byte __DATA).
board = (SRC / 'kits/droidvm/DroidVMGpu.cpp').read_text()
for old, new in [('Binding gBindings[NativeAdrenoVmMaxObjects];\n', 'Binding *gBindings;   // NativeAdrenoVm::attach allocates it\n'),
                 ('    mappings_ = IONewZeroData(Mapping, NativeAdrenoVmMaxObjects);\n    if (!mappings_) return kIOReturnNoMemory;\n',
                  '    mappings_ = IONewZeroData(Mapping, NativeAdrenoVmMaxObjects);\n    if (!mappings_) return kIOReturnNoMemory;\n'
                  '    if (!gBindings) gBindings = IONewZero(Binding, NativeAdrenoVmMaxObjects);\n'
                  '    if (!gBindings) {IODeleteData(mappings_, Mapping, NativeAdrenoVmMaxObjects); mappings_ = nullptr; return kIOReturnNoMemory;}\n')]:
    if board.count(old) != 1:
        sys.exit('kits/droidvm/DroidVMGpu.cpp: the binding table changed')
    board = board.replace(old, new)
staged_board = scope['staged'].parent / 'DroidVMGpu.cpp'
staged_board.write_text(board)
# Bring-up: memory pinned outside the pool, in bytes live: [0] imported (the owners' pages, wired while the GPU maps them), [1] allocated
# outside the pool. The logged lines show them beside the pool's use.
memory = scope.get('staged_memory', adreno / 'NativeAdrenoMemory.cpp').read_text()
for old, new in [('extern "C" {volatile uint32_t native_adreno_pool_stats[8];}',
                  'extern "C" {volatile uint32_t native_adreno_pool_stats[8];volatile uint64_t native_adreno_pinned_bytes[2];}'),
                 ('    prepared_=true;bytes_=bytes;\n    status=kIOReturnUnsupported;\n',
                  '    prepared_=true;bytes_=bytes;\n    native_adreno_pinned_bytes[0]=native_adreno_pinned_bytes[0]+bytes;\n    status=kIOReturnUnsupported;\n'),
                 ('            IOReturn status=imported_->complete();\n            if(status!=kIOReturnSuccess) {quarantined_=true;return status;}\n            prepared_=false;\n',
                  '            IOReturn status=imported_->complete();\n            if(status!=kIOReturnSuccess) {quarantined_=true;return status;}\n            prepared_=false;\n'
                  '            native_adreno_pinned_bytes[0]=native_adreno_pinned_bytes[0]-bytes_;\n'),
                 ('            if(status!=kIOReturnSuccess) {quarantined_=true;return status;}\n            prepared_=false;\n        }\n        native_adreno_trace_stage=33;\n',
                  '            if(status!=kIOReturnSuccess) {quarantined_=true;return status;}\n            prepared_=false;\n'
                  '            native_adreno_pinned_bytes[1]=native_adreno_pinned_bytes[1]-bytes_;\n        }\n        native_adreno_trace_stage=33;\n'),
                 ('    prepared_=true;bytes_=bytes;mapping_=descriptor_->getBytesNoCopy();\n',
                  '    prepared_=true;bytes_=bytes;mapping_=descriptor_->getBytesNoCopy();\n'
                  '    native_adreno_pinned_bytes[1]=native_adreno_pinned_bytes[1]+bytes;\n')]:
    if memory.count(old) != 1:
        sys.exit('NativeAdrenoMemory.cpp: the pinned-memory accounting no longer applies: ' + old[:60])
    memory = memory.replace(old, new)
staged_memory = scope['staged'].parent / 'NativeAdrenoMemory.cpp'
staged_memory.write_text(memory)
publish = publish.replace('extern "C" volatile uint32_t native_adreno_pool_stats[8];   // [3] pool MiB used, [4] its peak\n',
                          'extern "C" volatile uint32_t native_adreno_pool_stats[8];   // [3] pool MiB used, [4] its peak\n'
                          'extern "C" volatile uint64_t native_adreno_pinned_bytes[2];   // imported, outside the pool (NativeAdrenoMemory.cpp)\n')
publish = publish.replace('pool %u MiB used\\n",', 'pool %u MiB used, pinned %llu+%llu MiB\\n",')
publish = publish.replace(',native_adreno_pool_stats[3]);', ',native_adreno_pool_stats[3],native_adreno_pinned_bytes[0]>>20,native_adreno_pinned_bytes[1]>>20);')
closed = '                record->closes=record->closes+1;record->slot=0xff;\n'
if publish.count(closed) != 1:
    sys.exit(f'{scope["staged"]}: the close record changed')
publish = publish.replace(closed, closed + '                IOLog("droidvm-gpu: %s closed, pool %u MiB used, pinned %llu+%llu MiB\\n",name_,native_adreno_pool_stats[3],'
                          'native_adreno_pinned_bytes[0]>>20,native_adreno_pinned_bytes[1]>>20);\n')
scope['staged'].write_text(publish)
sources = [adreno / 'NativeAdrenoSubmit.cpp', staged_memory, adreno / 'NativeAdrenoCpu.cpp',
           scope.get('staged_client', adreno / 'NativeAdrenoUserClient.cpp'), scope['staged'], staged_board, SRC / 'kits/AdrenoPM4/AdrenoPM4.c',
           ROOT / 'overlay/kext/DroidVMGpuKext.cpp', ROOT / 'overlay/kext/NativeKextGlue.cpp']
# IOKit/graphics (AGXAccelerator's IOAccelerator) from the macOS SDK's Kernel.framework: toolchains/sdks/MacOSX26.1.sdk.tar.xz, extracted
GRAPHICS = ROOT / 'out/x12377/inc-gfx'
if not (GRAPHICS / 'IOKit/graphics').exists():
    (GRAPHICS / 'IOKit').mkdir(parents=True, exist_ok=True)
    (GRAPHICS / 'IOKit/graphics').symlink_to(ROOT / 'toolchains/sdks/MacOSX26.1.sdk/System/Library/Frameworks/Kernel.framework/Headers/IOKit/graphics')
includes = [adreno, SRC / 'kits/ArmSmmu4K', SRC / 'kits/AdrenoPM4', SRC / 'kits/droidvm', GRAPHICS]
print(f'droidvm-gpu: wire {WIRE} ({REF}, NativeAdreno {ADRENO_PIN[:7]})')
subprocess.run(['python3', str(ROOT / 'scripts/build-native-kext.py'), 'DroidVMGpu', *map(str, sources),
                *[f'-I{path}' for path in includes]], check=True)
