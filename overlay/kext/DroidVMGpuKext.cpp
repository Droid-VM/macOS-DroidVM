// SPDX-License-Identifier: BSD-2-Clause-Patent
// DroidVMGpu (UniXNU-droidvm package/DroidVMGpu.cpp, which only publishes NativeAdreno for the virtio GPU's 3D) as a kext of the
// collection. On the iOS board the late display probe calls sheng_gpu_power_probe(); here IOResources matches DroidVMGpuStarter (no
// device of its own: crosvm's droidvm-gpu is gone from the VM), whose start() makes that call, which publishes from a thread (start
// runs inside IOResources' matching and must not wait). The macOS accelerator is AGXAccelerator below, an ordinary subclass of
// IOGraphicsFamily's IOAccelerator, matching the published service.
#include <IOKit/IOService.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOMemoryDescriptor.h>
#include <IOKit/IOUserClient.h>
#include <IOKit/graphics/IOAccelerator.h>

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

extern "C" IOReturn native_adreno_new_user_client(IOService *, task_t, void *, UInt32, OSDictionary *, IOUserClient **, unsigned);
extern "C" void native_adreno_note_property_read(const char *);
extern "C" void proc_selfname(char *, int);

// The registry-visible accelerator for Metal's discovery (Metal.framework's MTLIOAccelServiceGlobalContext watches
// IOServiceMatching("IOAccelerator"); IOGPU's +[IOGPUMetalDevice registerAcceleratorService:] loads <MetalPluginName>.bundle from the first
// of /Library/GPUBundles and /System/Library/Extensions that libsystem_sandbox's gpu_bundle_find_trusted accepts, and takes its
// MetalPluginClassName only if that subclasses IOGPUMetalDevice). Its personality matches the published
// NativeAdrenoGpu service and carries MetalPluginName / MetalPluginClassName, as AppleParavirtGPU's does on vma2. Named after the Apple
// accelerator, as on iOS, so sandbox profiles that name the class accept the plugin's open; opens go to NativeAdreno's user client.
class AGXAccelerator : public IOAccelerator {
    OSDeclareDefaultStructors(AGXAccelerator)
public:
    bool start(IOService *provider) override;
    IOReturn newUserClient(task_t owningTask, void *securityID, UInt32 type, OSDictionary *properties, IOUserClient **handler) override;
    OSObject *copyProperty(const OSSymbol *key) const override;
    OSObject *copyProperty(const OSString *key) const override;
    OSObject *copyProperty(const char *key) const override;
};

OSDefineMetaClassAndStructors(AGXAccelerator, IOAccelerator)

bool AGXAccelerator::start(IOService *provider)
{
    if (!IOAccelerator::start(provider)) return false;
    registerService();
    IOLog("droidvm-gpu: Metal accelerator on %s\n", provider->getName());
    return true;
}

IOReturn AGXAccelerator::newUserClient(task_t owningTask, void *securityID, UInt32 type, OSDictionary *properties, IOUserClient **handler)
{
    unsigned limit = 40;   // sheng-gpu-metal-opens: connections ever granted to the plugin (0 = unlimited)
    PE_parse_boot_argn("sheng-gpu-metal-opens", &limit, sizeof(limit));
    IOReturn status = native_adreno_new_user_client(this, owningTask, securityID, type, properties, handler, limit);
    static unsigned logged;
    if (logged < 32) {
        logged++;
        char name[20] = {};
        proc_selfname(name, sizeof(name));
        IOLog("droidvm-gpu: %s opens the accelerator, type %#x: %#x\n", name, unsigned(type), status);
    }
    return status;
}

static void notePropertyRead(const char *key)
{
    native_adreno_note_property_read(key);
    static unsigned logged;
    if (key && !strcmp(key, "MetalPluginName") && logged < 16) {
        logged++;
        char name[20] = {};
        proc_selfname(name, sizeof(name));
        IOLog("droidvm-gpu: %s reads MetalPluginName\n", name);
    }
}

OSObject *AGXAccelerator::copyProperty(const OSSymbol *key) const
{
    notePropertyRead(key ? key->getCStringNoCopy() : nullptr);
    return IORegistryEntry::copyProperty(key);
}

OSObject *AGXAccelerator::copyProperty(const OSString *key) const
{
    notePropertyRead(key ? key->getCStringNoCopy() : nullptr);
    return IORegistryEntry::copyProperty(key);
}

OSObject *AGXAccelerator::copyProperty(const char *key) const
{
    notePropertyRead(key);
    return IORegistryEntry::copyProperty(key);
}
