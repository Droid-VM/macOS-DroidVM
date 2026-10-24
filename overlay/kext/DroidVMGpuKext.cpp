// SPDX-License-Identifier: BSD-2-Clause-Patent
// DroidVMGpu (UniXNU-droidvm package/DroidVMGpu.cpp) as a kext of the collection. On the iOS board the late display probe calls
// sheng_gpu_power_probe(); here the IOPlatformDevice of /arm-io/gpu (compatible "droidvm,gpu") matches DroidVMGpuStarter, whose
// start() makes that call (droidvm-gpu=1 still gates it). The iOS AGXAccelerator (droidvm-gpu-metal=1) is not built: its builder
// binds addresses of the iOS IOAcceleratorES, so publishMetal() finds no accelerator and stops at its first stage.
#include <IOKit/IOService.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOMemoryDescriptor.h>

extern "C" void sheng_gpu_power_probe(void);

extern "C" {
void native_adreno_accelerator_static_init(void) __asm__("__GLOBAL__sub_I_NativeAdrenoAccelerator.cpp");
void native_adreno_accelerator_static_init(void) {}
IOService *native_adreno_accelerator_allocate(void) { return nullptr; }
unsigned native_adreno_accelerator_instance_size(void) { return 0; }
// The GOP scanout hand-off (NativeMobileDisplay's NativeGOPPresenter on iOS): none until the macOS display driver provides it.
IOMemoryDescriptor *native_gop_handoff_memory(void) { return nullptr; }
IOReturn native_gop_handoff_call(uint32_t, task_t, const void *, size_t, void *, size_t) { return kIOReturnUnsupported; }
// The boot log export of the iOS board's rig (weak there): nothing stores the pieces.
int boot_log_export_put(uint32_t, uint32_t, uint32_t, const void *, uint32_t) { return 0; }
}

class DroidVMGpuStarter : public IOService {
    OSDeclareDefaultStructors(DroidVMGpuStarter)
public:
    bool start(IOService *provider) override;
};

OSDefineMetaClassAndStructors(DroidVMGpuStarter, IOService)

bool DroidVMGpuStarter::start(IOService *provider)
{
    if (!IOService::start(provider)) return false;
    static bool started;
    if (!started) {
        started = true;
        IOLog("droidvm-gpu: kext matched %s\n", provider->getName());
        sheng_gpu_power_probe();
    }
    registerService();
    return true;
}
