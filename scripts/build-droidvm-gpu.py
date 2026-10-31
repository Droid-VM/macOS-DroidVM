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
# with twelve the later ones failed to open the GPU), each other window 1 GiB, 24 GiB of the VBO's 64 GiB (at 256 MiB the icon agent's
# CoreImage textures ran out of addresses and System Settings showed blank icons); and
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
                          '    {0x20000000ull,0x40000000ull},' + ','.join('{%#xull,0x40000000ull}' % (0x60000000 + i * 0x40000000)
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
# removeMappingForDescriptor hands back a retained map, which dropViews never released: the user PTEs outlived clientClose. An exiting
# task closes its connections before its address space goes (task_terminate_internal: ipc_space_terminate, then the map), so releaseAll
# freed BO pages a user mapping still held and pmap_assert_free panicked the exit. The pool hid it (its pages never go back to the VM);
# without one (droidvm-gpu-pool-mib=0) the first exit of a GPU client panicked, a frozen guest on screen.
leak = '        while(removeMappingForDescriptor(view))native_adreno_metal_diag.forced_unmaps=native_adreno_metal_diag.forced_unmaps+1;\n'
if publish.count(leak) != 1:
    sys.exit(f'{scope["staged"]}: dropViews changed')
publish = publish.replace(leak,
    '        while(IOMemoryMap *map=removeMappingForDescriptor(view)) {   /* build-droidvm-gpu.py: unmap and drop the retained map */\n'
    '            map->unmap();map->release();\n'
    '            native_adreno_metal_diag.forced_unmaps=native_adreno_metal_diag.forced_unmaps+1;\n'
    '        }\n')
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
# The mapping table's lookups: a submission looked each IB's buffer up (describe) and held each distinct one (find), every lookup a scan of
# the 8192 slots, then walked all of them for the write-combine and cache upkeep (two or three submissions a WindowServer frame). The walks
# stop at the highest slot used (map() raises it), and a handle's lookup tries the slot it was last found in first: 11 us less a
# submission in a window drag (kc282/kc283).
LOOP = '    for (size_t i = 0; i < NativeAdrenoVmMaxObjects; ++i) {\n'
if board.count(LOOP) != 5:
    sys.exit('kits/droidvm/DroidVMGpu.cpp: the mapping walks changed')
board = board.replace(LOOP, '    for (size_t i = 0; i < gMappingEnd; ++i) {\n')
for old, new in [('Binding *gBindings;   // NativeAdrenoVm::attach allocates it\n',
                  'Binding *gBindings;   // NativeAdrenoVm::attach allocates it\n'
                  'size_t gMappingEnd;   // slots past it were never used since attach\n'
                  'uint16_t gHandleSlots[4096];   // by handle: the slot it was last found in (a hint, checked)\n'),
                 ('    capacity_ = max_spans;\n', '    capacity_ = max_spans;\n    gMappingEnd = 0;\n'),
                 ('    if (!handle || !mappings_) return nullptr;\n'
                  '    for (size_t i = 0; i < NativeAdrenoVmMaxObjects; ++i)\n'
                  '        if (mappings_[i].memory && mappings_[i].handle == handle) return &mappings_[i];\n',
                  '    if (!handle || !mappings_) return nullptr;\n'
                  '    uint16_t &hint = gHandleSlots[handle % 4096];\n'
                  '    if (hint < gMappingEnd && mappings_[hint].memory && mappings_[hint].handle == handle) return &mappings_[hint];\n'
                  '    for (size_t i = 0; i < gMappingEnd; ++i)\n'
                  '        if (mappings_[i].memory && mappings_[i].handle == handle) {\n'
                  '            hint = static_cast<uint16_t>(i);\n'
                  '            return &mappings_[i];\n'
                  '        }\n'),
                 ('    *handle = mappings_[index].handle;\n',
                  '    *handle = mappings_[index].handle;\n'
                  '    if (index >= gMappingEnd) gMappingEnd = index + 1;\n'
                  '    gHandleSlots[*handle % 4096] = static_cast<uint16_t>(index);\n'),
                 ('    for (size_t m = 0; mappings_ && m < NativeAdrenoVmMaxObjects; ++m)\n'
                  '        if (mappings_[m].memory && mappings_[m].handle == handle) {\n'
                  '            *iova = mappings_[m].iova;\n'
                  '            *bytes = mappings_[m].memory->bytes();\n'
                  '            *permissions = mappings_[m].permissions;\n'
                  '            return kIOReturnSuccess;\n'
                  '        }\n',
                  '    if (const Mapping *m = const_cast<NativeAdrenoVm *>(this)->find(handle)) {\n'
                  '        *iova = m->iova;\n'
                  '        *bytes = m->memory->bytes();\n'
                  '        *permissions = m->permissions;\n'
                  '        return kIOReturnSuccess;\n'
                  '    }\n')]:
    if board.count(old) != 1:
        sys.exit('kits/droidvm/DroidVMGpu.cpp: the mapping lookups changed: ' + old[:60])
    board = board.replace(old, new)
# Without the pool (droidvm-gpu-pool-mib=0, every BO imported on its own): whether the host's KGSL imports guest pages IO-coherent
# was only learned from the pool's import. A page of its own asks it now. And with write combining off (droidvm-gpu-wc=0) the GPU's
# own BOs are cacheable on the CPU side too, so the GPU maps them write-back coherent as it does imports (NativeAdrenoUserClient.cpp)
# and the device reports cached coherent memory, which Turnip maps write-back (build-turnip-macos.py) instead of write-combined.
for old, new in [
        ('    native_adreno_io_coherent = gPoolObject && gPoolCoherent ? 1 : 0;\n',
         '    native_adreno_io_coherent = gPoolObject && gPoolCoherent ? 1 : 0;\n'
         '    if (!gPoolObject) {\n'
         '        NativeAdrenoMemory probe;\n'
         '        if (!probe.allocate(4096, output_bits, true, 4096, false) && probe.spanCount() == 1) {\n'
         '            const droidvm_gpu_range range = {probe.spans()[0].physical, 4096};\n'
         '            uint32_t object = 0;\n'
         '            bool coherent = false;\n'
         '            if (!importRanges(&range, 1, DROIDVM_GPU_IMPORT_COHERENT, &object, &coherent)) {\n'
         '                (void)freeObject(object);\n'
         '                native_adreno_io_coherent = coherent ? 1 : 0;\n'
         '            }\n'
         '        }\n'
         '        (void)probe.release();\n'
         '        IOLog("droidvm-gpu: without a pool, imports are %s; BOs %s\\n", native_adreno_io_coherent ? "IO-coherent" : "not coherent",\n'
         '              native_adreno_wc_enabled ? "write-combined" : "cacheable");\n'
         '    }\n'),
        ('info.highest_bank_bit ? info.highest_bank_bit : 16, 6, 1, 4, NativeAdrenoDeviceClientIova, 0};\n',
         'info.highest_bank_bit ? info.highest_bank_bit : 16, 6, 1, 4,\n'
         '                   uint32_t(NativeAdrenoDeviceClientIova | (!native_adreno_wc_enabled && native_adreno_io_coherent ? NativeAdrenoDeviceCachedCoherent : 0)), 0};\n')]:
    if board.count(old) != 1:
        sys.exit('kits/droidvm/DroidVMGpu.cpp: the coherence setup changed: ' + old[:60])
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
# An allocation the pool cannot hold falls back to IOBufferMemoryDescriptor with the GPU's physical mask, which XNU serves through
# vm_page_find_contiguous: with the guest's memory fragmented each 64 MiB request scanned all 1.2 million pages, ran zone_gc and
# found none, and the icon agent's first login retried one five times a second (the whole guest stalled). A BO that need not be
# contiguous takes any pages there (no physical mask, so no contiguous search); a contiguous fallback that failed refuses the same
# size or larger at once for two seconds, one that succeeds at that size again ending it. Only contiguous ones: a large BO tries a
# contiguous run first (NativeAdrenoUserClient prefer_contiguous) and then scattered pages, which the backoff must not refuse.
old = ('    descriptor_=IOBufferMemoryDescriptor::inTaskWithPhysicalMask(kernel_task,options,bytes,(limit-1)&~UINT64_C(4095));\n'
       '    if(!descriptor_)return kIOReturnNoMemory;\n')
if memory.count(old) != 1:
    sys.exit('NativeAdrenoMemory.cpp: the allocation fallback changed')
memory = memory.replace(old,
    '    static uint64_t fallback_failed_at,fallback_failed_bytes;   /* build-droidvm-gpu.py: back off a failing fallback */\n'
    '    const uint64_t fallback_now=mach_absolute_time();\n'
    '    uint64_t fallback_backoff=0;nanoseconds_to_absolutetime(2000000000ull,&fallback_backoff);\n'
    '    if(contiguous && native_adreno_pool_only)return kIOReturnNoMemory;   /* a contiguous run preferred, not required: from the pool or none */\n'
    '    if(contiguous && fallback_failed_bytes && bytes>=fallback_failed_bytes && fallback_now-fallback_failed_at<fallback_backoff)return kIOReturnNoMemory;\n'
    '    /* A BO that need not be contiguous takes any pages (the loop below still refuses one past the GPU\'s reach). */\n'
    '    descriptor_=contiguous?IOBufferMemoryDescriptor::inTaskWithPhysicalMask(kernel_task,options,bytes,(limit-1)&~UINT64_C(4095)):\n'
    '        IOBufferMemoryDescriptor::inTaskWithOptions(kernel_task,options,bytes,4096);\n'
    '    if(!descriptor_) {\n'
    '        if(contiguous) {\n'
    '            if(!fallback_failed_bytes || bytes<fallback_failed_bytes || fallback_now-fallback_failed_at>=fallback_backoff)fallback_failed_bytes=bytes;\n'
    '            fallback_failed_at=fallback_now;\n'
    '        }\n'
    '        return kIOReturnNoMemory;\n'
    '    }\n'
    '    if(contiguous && bytes>=fallback_failed_bytes)fallback_failed_bytes=0;\n')
memory = memory.replace('#include <kern/task.h>\n', '#include <kern/task.h>\n#include <kern/clock.h>\n', 1)
# User BOs outside the pool take pages from the VM with no kernel mapping (when the CPU views are not write-combined). An
# IOBufferMemoryDescriptor maps its buffer into the kernel's DATA_SHARED range, 1.5 GiB for every kext: without a pool the GPU's
# kernel tag peaked at 973 MiB at a first login, kmem_alloc_guard answered KERN_NO_SPACE even for 4 MiB with physical memory to
# spare, WindowServer asserted on the refused textures and the session went back to the lock screen. The GPU reaches the pages
# through their spans, the client through its physical-range view; the kernel cleans and invalidates them through the physical
# aperture (maintainImported), and zeroes them as it hands them out (KMA_ZERO).
header = adreno / 'NativeAdrenoMemory.h'
text = header.read_text()
for old, new in [('    void *mapping_=nullptr;\n', '    void *mapping_=nullptr;\n    void *pages_=nullptr;   /* vm_page list of an unmapped BO (allocateUnmapped) */\n'),
                 ('    IOReturn maintainImported(size_t offset,size_t bytes,NativeAdrenoCacheOperation);\n',
                  '    IOReturn maintainImported(size_t offset,size_t bytes,NativeAdrenoCacheOperation);\n'
                  '    IOReturn allocateUnmapped(size_t bytes,uint64_t limit);\n'),
                 ('    bool backed() const {return descriptor_ || imported_ || pooled_;}\n',
                  '    bool backed() const {return descriptor_ || imported_ || pooled_ || pages_;}\n')]:
    if text.count(new) != 1:   # the export is kept between runs: an earlier run's edit stays
        if text.count(old) != 1:
            sys.exit(f'{header}: {old.strip()} changed')
        text = text.replace(old, new)
header.write_text(text)
for old, new in [
    # the scattered path of a user BO, after the pool had no room
    ('    IOOptionBits options=static_cast<IOOptionBits>(kIODirectionInOut)|static_cast<IOOptionBits>(kIOMemoryMapperNone);\n',
     '    if(pooled && !contiguous && !native_adreno_wc_enabled)return allocateUnmapped(bytes,limit);\n'
     '    IOOptionBits options=static_cast<IOOptionBits>(kIODirectionInOut)|static_cast<IOOptionBits>(kIOMemoryMapperNone);\n'),
    ('    if(descriptor_) {\n        if(prepared_) {\n            native_adreno_trace_stage=31;\n',
     '    if(pages_) {\n'
     '        vm_page_free_list(static_cast<vm_page_t>(pages_),false);pages_=nullptr;\n'
     '        if(prepared_) {prepared_=false;native_adreno_pinned_bytes[1]=native_adreno_pinned_bytes[1]-bytes_;}\n'
     '    }\n'
     '    if(descriptor_) {\n        if(prepared_) {\n            native_adreno_trace_stage=31;\n'),
    ('    if(imported_)return maintainImported(offset,bytes,writes?NativeAdrenoCleanInvalidate:NativeAdrenoClean);\n',
     '    if(imported_ || pages_)return maintainImported(offset,bytes,writes?NativeAdrenoCleanInvalidate:NativeAdrenoClean);\n'),
    ('    if(imported_)return maintainImported(offset,bytes,NativeAdrenoCleanInvalidate);\n',
     '    if(imported_ || pages_)return maintainImported(offset,bytes,NativeAdrenoCleanInvalidate);\n'),
    ('IOReturn NativeAdrenoMemory::makeWriteCombined()\n',
     'IOReturn NativeAdrenoMemory::allocateUnmapped(size_t bytes,uint64_t limit)\n'
     '{\n'
     '    vm_page_t list=nullptr;\n'
     '    if(vm_page_alloc_list(bytes/4096,0x80 /* KMA_ZERO */,&list)!=KERN_SUCCESS)return kIOReturnNoMemory;\n'
     '    pages_=list;bytes_=bytes;prepared_=true;\n'
     '    native_adreno_pinned_bytes[1]=native_adreno_pinned_bytes[1]+bytes;\n'
     '    IOReturn status=kIOReturnNoMemory;\n'
     '    span_capacity_=bytes/4096;\n'
     '    spans_=IONewData(NativeAdrenoPhysicalSpan,span_capacity_);\n'
     '    if(!spans_)goto failed;\n'
     '    {\n'
     '        size_t offset=0;\n'
     '        for(vm_page_t page=list;page;page=*reinterpret_cast<vm_page_t *>(page),offset+=4096) {   /* vmp_snext, the first word */\n'
     '            const uint64_t physical=uint64_t(vm_page_get_phys_page(page))<<12;\n'
     '            if(offset>=bytes || !physical || physical>=limit || 4096>limit-physical) {status=kIOReturnUnsupported;goto failed;}\n'
     '            if(span_count_ && physical==spans_[span_count_-1].physical+spans_[span_count_-1].bytes)spans_[span_count_-1].bytes+=4096;\n'
     '            else spans_[span_count_++]={offset,physical,4096};\n'
     '        }\n'
     '        if(offset!=bytes) {status=kIOReturnInternalError;goto failed;}\n'
     '    }\n'
     '    /* The zeroes went through the cacheable aperture: to the point of coherency before a device that does not snoop sees them. */\n'
     '    status=maintainImported(0,bytes,NativeAdrenoClean);\n'
     '    if(status)goto failed;\n'
     '    native_adreno_pool_stats[5]=native_adreno_pool_stats[5]+1;native_adreno_pool_stats[6]=native_adreno_pool_stats[6]+(uint32_t)span_count_;\n'
     '    return kIOReturnSuccess;\n'
     'failed:\n'
     '    (void)release();return status;\n'
     '}\n'
     'IOReturn NativeAdrenoMemory::makeWriteCombined()\n'),
    ('#include <kern/clock.h>\n',
     '#include <kern/clock.h>\n'
     'extern "C" {\n'
     'extern volatile uint32_t native_adreno_wc_enabled;\n'
     '/* XNU\'s own page allocator (vm_pageout_xnu.h): wired pages in no object, linked through vmp_snext; vm_page_free_list(list, false) takes them back. */\n'
     'typedef struct vm_page *vm_page_t;\n'
     'kern_return_t vm_page_alloc_list(vm_size_t page_count,uint32_t kma_flags,vm_page_t *list);\n'
     'void vm_page_free_list(vm_page_t list,bool prepare_object);\n'
     'ppnum_t vm_page_get_phys_page(vm_page_t page);\n'
     '}\n')]:
    if memory.count(old) != 1:
        sys.exit(f'NativeAdrenoMemory.cpp: {old.strip()[:60]} changed')
    memory = memory.replace(old, new)
memory = memory.replace('extern "C" {volatile uint32_t native_adreno_pool_stats[8];',
                        'extern "C" {bool native_adreno_pool_only;}   /* set around a preferred contiguous try (NativeAdrenoUserClient.cpp) */\n'
                        'extern "C" {volatile uint32_t native_adreno_pool_stats[8];', 1)
# A large BO that need not be contiguous tries one contiguous run first (fewer GPU spans) and then scattered pages. That first try
# takes the pool's run only: outside the pool it was the contiguous search above, which with the pool full ran every two seconds.
client = scope.get('staged_client', adreno / 'NativeAdrenoUserClient.cpp').read_text()
old = '        status=entry->memory.allocate((size_t)request->bytes,output_bits_,true,(size_t)request->bytes,true);\n'
if client.count(old) != 1:
    sys.exit('NativeAdrenoUserClient.cpp: the preferred contiguous try changed')
client = client.replace(old, '        native_adreno_pool_only=true;\n' + old + '        native_adreno_pool_only=false;\n')
client = 'extern "C" {extern bool native_adreno_pool_only;}\n' + client
old = '    const bool coherent=entry->memory.imported() && native_adreno_io_coherent;\n'
if client.count(old) != 1:
    sys.exit('NativeAdrenoUserClient.cpp: the coherent mapping test changed')
client = client.replace(old, '    const bool coherent=(entry->memory.imported() || !native_adreno_wc_enabled) && native_adreno_io_coherent;\n')
scope['staged_client'] = scope['staged'].parent / 'NativeAdrenoUserClient.cpp'
scope['staged_client'].write_text(client)
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
submit = (adreno / 'NativeAdrenoSubmit.cpp').read_text()
# DROIDVM_GPU_SUBMIT_TIMES=1 (diagnostics, research/debug-2026-10-28): where a submission's kernel call goes, logged every 2000 of them in
# microseconds a submission: hold (validate, retire, hold the BOs), wc (write-combine re-assertion and audit), publish (cache maintenance,
# TLB), peek (the IB log), ring (the host round trip), and the slowest round trip.
if os.environ.get('DROIDVM_GPU_SUBMIT_TIMES') == '1':
    for old, new in [('#include <IOKit/IOLib.h>\n',
                      '#include <IOKit/IOLib.h>\n#include <kern/clock.h>\n'
                      'static uint64_t gSubmitTimes[7];   // submissions, then the phases\' and the slowest round trip\'s ticks\n'),
                     ('    IOReturn swept=retireCompleted();\n', '    const uint64_t t0=mach_absolute_time();\n    IOReturn swept=retireCompleted();\n'),
                     ('    uint32_t value=0;\n    /* int-070', '    const uint64_t t1=mach_absolute_time();\n    uint32_t value=0;\n    /* int-070'),
                     ('    (void)vm_->sampleWord(buffers[0].iova,&cached,&before);\n',
                      '    const uint64_t t2=mach_absolute_time();\n    (void)vm_->sampleWord(buffers[0].iova,&cached,&before);\n'),
                     ('    {\n        const uint32_t slot=native_adreno_ib_log_count&3;',
                      '    const uint64_t t3=mach_absolute_time();\n    {\n        const uint32_t slot=native_adreno_ib_log_count&3;'),
                     ('    status=ring_->submitFramed(words,word_count,&value);\n',
                      '    const uint64_t t4=mach_absolute_time();\n    status=ring_->submitFramed(words,word_count,&value);\n'
                      '    {\n        const uint64_t t5=mach_absolute_time();\n'
                      '        gSubmitTimes[0]++;gSubmitTimes[1]+=t1-t0;gSubmitTimes[2]+=t2-t1;gSubmitTimes[3]+=t3-t2;gSubmitTimes[4]+=t4-t3;\n'
                      '        gSubmitTimes[5]+=t5-t4;if(t5-t4>gSubmitTimes[6])gSubmitTimes[6]=t5-t4;\n'
                      '        if(gSubmitTimes[0]==2000) {\n'
                      '            uint64_t us[6];for(unsigned i=0;i<6;i++){absolutetime_to_nanoseconds(gSubmitTimes[1+i],&us[i]);us[i]/=i<5?2000*1000/10:1000;}\n'
                      '            IOLog("droidvm-gpu: submit x0.1us hold %llu wc %llu publish %llu peek %llu ring %llu, slowest ring %llu us\\n",'
                      'us[0],us[1],us[2],us[3],us[4],us[5]);\n'
                      '            for(auto &t:gSubmitTimes)t=0;\n'
                      '        }\n    }\n')]:
        if submit.count(old) != 1:
            sys.exit('NativeAdrenoSubmit.cpp: the submit timing no longer applies: ' + old[:60])
        submit = submit.replace(old, new)
# A submission released the jobs that had completed by asking the host for each one still in flight whether it had (DroidVMGpu.cpp's
# observeFence: a DROIDVM_GPU_OP_RETIRED round trip per job). It now releases those the ring has already seen complete (the waits on
# them, which also release theirs) and asks the host only when every job slot is taken; an unmap still sweeps with the host first
# (NativeAdrenoUserClient.cpp). In a window drag a submission's kernel call before the ring went from 86 to 8 us, WindowServer's update
# from 6.2 to 5.2 ms and its input to GPU end from 14.7 to 13.4 ms (medians, kc282/kc283 to kc284).
for old, new in [('    IOReturn swept=retireCompleted();\n    if(swept)return swept;\n    Job *job=free();\n    if(!job)return kIOReturnBusy;\n',
                  '    for(auto &done:jobs_)\n'
                  '        if(done.active && ring_->completedFence()-done.fence<0x80000000u) {\n'
                  '            const IOReturn status=release(done);\n'
                  '            if(status)return status;\n'
                  '            ++stats_.completed;\n'
                  '        }\n'
                  '    Job *job=free();\n'
                  '    if(!job) {\n'
                  '        const IOReturn swept=retireCompleted();\n'
                  '        if(swept)return swept;\n'
                  '        job=free();\n'
                  '    }\n'
                  '    if(!job)return kIOReturnBusy;\n')]:
    if submit.count(old) != 1:
        sys.exit('NativeAdrenoSubmit.cpp: the submission sweep changed')
    submit = submit.replace(old, new)
staged_submit = scope['staged'].parent / 'NativeAdrenoSubmit.cpp'
staged_submit.write_text(submit)
sources = [staged_submit, staged_memory, adreno / 'NativeAdrenoCpu.cpp',
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
