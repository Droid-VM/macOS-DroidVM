// SPDX-License-Identifier: BSD-2-Clause-Patent
// NativeAdrenoMetal for macOS: the Metal plugin of DroidVMGpu's AGXAccelerator. IOGPU's +[IOGPUMetalDevice registerAcceleratorService:] loads
// this bundle from /Library/GPUBundles, takes NativeAdrenoMetalDevice (it must subclass IOGPUMetalDevice) and registers what
// -initWithAcceleratorPort: returns with MTLAddDevice. That is UniXNU's native Metal frontend (drivers/NativeMetal/NativeBridgeMetalFrontend.mm:
// the metal2vulkan runtime on Turnip, beside this executable, on NativeAdreno's user client), one device per process. The iOS plugin's
// render-server machinery (status stream, display hand-off, pipeline packs) is not here. Reports go to stderr (the kernel's stderr-log=1).
#import <Foundation/Foundation.h>
#include <IOKit/IOKitLib.h>
#include <dlfcn.h>
#include <objc/runtime.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "NativeBridgeMetalFrontend.h"
#include "bridge/NativeMetalObjects.h"

@interface IOGPUMetalDevice : NSObject
@end

@interface NativeAdrenoMetalDevice : IOGPUMetalDevice
- (id)initWithAcceleratorPort:(io_service_t)port;
@end

static void missingSelector(const char *cls, const char *selector)
{
    fprintf(stderr, "NativeAdrenoMetal: %s: missing %s %s\n", getprogname(), cls, selector);
}

// Turnip travels beside this executable (Contents/MacOS/libvulkan_freedreno.dylib).
static bool turnipPath(char *path, size_t size)
{
    Dl_info info = {};
    if (!dladdr(reinterpret_cast<const void *>(&turnipPath), &info) || !info.dli_fname)
        return false;
    snprintf(path, size, "%s", info.dli_fname);
    char *slash = strrchr(path, '/');
    if (!slash)
        return false;
    snprintf(slash + 1, size - size_t(slash + 1 - path), "libvulkan_freedreno.dylib");
    return access(path, R_OK) == 0;
}

// What +[IOGPUMetalDevice registerAcceleratorService:] and its clients take from an IOGPUMetalDevice, which the frontend's device (an _MTLDevice)
// is not: registration hands it the accelerator's service object (-_setAcceleratorService:, kept like IOGPU's ivar), Metal's wrappers set
// themselves (-_setDeviceWrapper:, weak; -_deviceWrapper is the device itself without one, over _MTLDevice's nil, which made
// MTLCopyDeviceForRegistryID answer nil and VFX key its resource managers by nil). -acceleratorPort replaces _MTLDevice's 0: SkyLight
// composites with Metal only when the first device has a port (WSGetDefaultMetalAccelerator), else in software (CompositorSW).
static io_service_t gAcceleratorPort;
static id gAcceleratorService;
static __weak id gDeviceWrapper;

static void setAcceleratorService(id, SEL, id service) { gAcceleratorService = service; }
static io_service_t acceleratorPort(id, SEL) { return gAcceleratorPort; }
static void setDeviceWrapper(id, SEL, id wrapper) { gDeviceWrapper = wrapper; }
static id deviceWrapper(id self, SEL) { id wrapper = gDeviceWrapper; return wrapper ? wrapper : self; }
static BOOL isBuiltIn(id, SEL) { return YES; }
// IOGPUMetalDevice's answers about features this device has not got (no priority bands, background role, slot, peers, vertex amplification,
// detachable backings) and its resource-pool housekeeping, which has nothing to do here.
static BOOL no(id, SEL) { return NO; }
static uint64_t zero(id, SEL) { return 0; }
static uint32_t one(id, SEL) { return 1; }
static void nothing(id, SEL) {}
static void nothingWith(id, SEL, uint64_t) {}
static BOOL amplificationCount(id, SEL, NSUInteger count) { return count == 1; }
static uint64_t commandBufferArgumentsSize(id, SEL) { return 48; }   // IOGPU's
// Unified memory: two thirds of RAM, as Metal recommends on Apple GPUs.
static uint64_t workingSetSize(id, SEL) { return NSProcessInfo.processInfo.physicalMemory / 3 * 2; }

// Any other IOGPU method a client sends the device or a frontend object gets a stub answering 0 (nil, NO), named on stderr when it is
// resolved (once per class): a bring-up survey of what WindowServer and the rest take from a GPU, instead of one -doesNotRecognizeSelector:
// abort per boot. Only the selectors of the IOGPU class the object stands in for: -respondsToSelector: stays NO for everything a real IOGPU
// object does not answer either. Silent when called: WindowServer sends some for every texture of every frame.
static uint64_t stub(id, SEL) { return 0; }

// The frontend's classes (NativeBridgeMetalFrontend.mm) and the IOGPU class each stands in for; the device is any other class.
static Class referenceClass(Class cls)
{
    static const struct { const char *frontend, *iogpu; } classes[] = {
        {"NBBuffer", "IOGPUMetalBuffer"}, {"NBTexture", "IOGPUMetalTexture"}, {"NBHeap", "IOGPUMetalHeap"},
        {"NBQueue", "IOGPUMetalCommandQueue"}, {"NBCommandBuffer", "IOGPUMetalCommandBuffer"},
        {"NBComputeEncoder", "IOGPUMetalComputeCommandEncoder"}, {"NBRenderEncoder", "IOGPUMetalRenderCommandEncoder"},
        {"NBBlitEncoder", "IOGPUMetalBlitCommandEncoder"}, {"NBEncoder", "IOGPUMetalCommandEncoder"}, {"NBFence", "IOGPUMetalFence"},
        {"NBSharedEvent", "IOGPUMetalSharedEvent"}, {"NBEvent", "IOGPUMetalEvent"}, {"NBObject", nullptr},
    };
    for (Class c = cls; c; c = class_getSuperclass(c))
        for (const auto &entry : classes)
            if (!strcmp(class_getName(c), entry.frontend))
                return entry.iogpu ? objc_getClass(entry.iogpu) : nil;
    return objc_getClass("IOGPUMetalDevice");
}

static BOOL resolveStub(id cls, SEL, SEL selector)
{
    Class reference = referenceClass((Class)cls);
    Method method = reference ? class_getInstanceMethod(reference, selector) : nullptr;
    if (!method)
        return NO;
    fprintf(stderr, "NativeAdrenoMetal: %s: stubbed %s %s\n", getprogname(), class_getName((Class)cls), sel_getName(selector));
    return class_addMethod((Class)cls, selector, (IMP)stub, method_getTypeEncoding(method));
}

// IOGPUMetalCommandQueue's GPU priorities (MTLGPUPriority 0-5; IOGPU starts a queue at 1, its background priority at 2), on the frontend's
// queue (NBQueue): kept, nothing schedules by them here.
static char kPriorityKey, kBackgroundPriorityKey;
static NSUInteger priorityOf(id queue, const void *key, NSUInteger initial)
{
    NSNumber *value = objc_getAssociatedObject(queue, key);
    return value ? value.unsignedIntegerValue : initial;
}
static NSUInteger getGPUPriority(id self, SEL) { return priorityOf(self, &kPriorityKey, 1); }
static NSUInteger getBackgroundGPUPriority(id self, SEL) { return priorityOf(self, &kBackgroundPriorityKey, 2); }
static void setPriorities(id self, NSUInteger priority, NSUInteger background)
{
    objc_setAssociatedObject(self, &kPriorityKey, @(priority), OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    objc_setAssociatedObject(self, &kBackgroundPriorityKey, @(background), OBJC_ASSOCIATION_RETAIN_NONATOMIC);
}
static BOOL setGPUPriority(id self, SEL, NSUInteger priority)
{
    setPriorities(self, priority, getBackgroundGPUPriority(self, nullptr));
    return YES;
}
static BOOL setGPUPriorityOffset(id self, SEL, NSUInteger priority, NSUInteger) { return setGPUPriority(self, nullptr, priority); }
static BOOL setBothGPUPriorities(id self, SEL, NSUInteger priority, NSUInteger background)
{
    setPriorities(self, priority, background);
    return YES;
}

struct MethodSpec {
    const char *name;
    IMP imp;
    const char *types;
    bool override;   // also over a base class's answer
};

static void addMethods(Class cls, const MethodSpec *methods, size_t count)
{
    for (size_t i = 0; i < count; i++) {   // otherwise the base class's own answers stay
        SEL selector = sel_registerName(methods[i].name);
        if (methods[i].override || ![cls instancesRespondToSelector:selector])
            class_addMethod(cls, selector, methods[i].imp, methods[i].types);
    }
}

static void addIOGPUMethods(id device)
{
    static const MethodSpec deviceMethods[] = {
        {"_setAcceleratorService:", (IMP)setAcceleratorService, "v24@0:8@16", false},
        {"acceleratorPort", (IMP)acceleratorPort, "I16@0:8", true},
        {"_setDeviceWrapper:", (IMP)setDeviceWrapper, "v24@0:8@16", true},
        {"_deviceWrapper", (IMP)deviceWrapper, "@16@0:8", true},
        {"isBuiltIn", (IMP)isBuiltIn, "B16@0:8", false},
        {"supportPriorityBand", (IMP)no, "B16@0:8", false},
        {"supportsBackgroundAppRole", (IMP)no, "B16@0:8", false},
        {"isSlotted", (IMP)no, "B16@0:8", false},
        {"supportsResourceDetachBacking", (IMP)no, "B16@0:8", false},
        {"supportsVertexAmplification", (IMP)no, "B16@0:8", false},
        {"supportsVertexAmplificationCount:", (IMP)amplificationCount, "B24@0:8Q16", false},
        {"maxTransferRate", (IMP)zero, "Q16@0:8", false},
        {"location", (IMP)zero, "Q16@0:8", false},
        {"locationNumber", (IMP)zero, "Q16@0:8", false},
        {"peerGroupID", (IMP)zero, "Q16@0:8", false},
        {"peerIndex", (IMP)zero, "I16@0:8", false},
        {"peerCount", (IMP)one, "I16@0:8", false},
        {"dedicatedMemorySize", (IMP)zero, "Q16@0:8", false},
        {"hwResourcePoolCount", (IMP)zero, "I16@0:8", false},
        {"cmdBufArgsSize", (IMP)commandBufferArgumentsSize, "Q16@0:8", false},
        {"kickCleanupQueue", (IMP)nothing, "v16@0:8", false},
        {"updateGPUSelectionProperties", (IMP)nothing, "v16@0:8", false},
        {"updateResourcePoolPurgeability", (IMP)nothing, "v16@0:8", false},
        {"periodicUpdateResourcePoolPurgeability", (IMP)nothing, "v16@0:8", false},
        {"cancelPeriodicUpdateResourcePoolPurgeability", (IMP)nothing, "v16@0:8", false},
        {"recommendedMaxWorkingSetSize", (IMP)workingSetSize, "Q16@0:8", false},
        {"sharedMemorySize", (IMP)workingSetSize, "Q16@0:8", false},
        {"currentAllocatedSize", (IMP)zero, "Q16@0:8", false},
    };
    Class cls = object_getClass(device);
    addMethods(cls, deviceMethods, sizeof deviceMethods / sizeof *deviceMethods);
    class_addMethod(object_getClass(cls), @selector(resolveInstanceMethod:), (IMP)resolveStub, "B24@0:8:16");
    static const MethodSpec queueMethods[] = {
        {"getGPUPriority", (IMP)getGPUPriority, "Q16@0:8", false},
        {"getBackgroundGPUPriority", (IMP)getBackgroundGPUPriority, "Q16@0:8", false},
        {"setGPUPriority:", (IMP)setGPUPriority, "B24@0:8Q16", false},
        {"setGPUPriority:offset:", (IMP)setGPUPriorityOffset, "B32@0:8Q16Q24", false},
        {"_setGPUPriority:backgroundPriority:", (IMP)setBothGPUPriorities, "B32@0:8Q16Q24", false},
    };
    if (Class queue = objc_getClass("NBQueue"))
        addMethods(queue, queueMethods, sizeof queueMethods / sizeof *queueMethods);
    // IOGPUMetalResource's: the process charged for a resource's memory (one pool here, charged to nobody), and aliasing (a heap's
    // placement here never reuses a live resource's range).
    static const MethodSpec resourceMethods[] = {
        {"setResponsibleProcess:", (IMP)nothingWith, "v20@0:8i16", false},
        {"makeAliasable", (IMP)nothing, "v16@0:8", false},
    };
    static const char *const resources[] = {"NBBuffer", "NBTexture"};
    for (const char *name : resources)
        if (Class resource = objc_getClass(name))
            addMethods(resource, resourceMethods, sizeof resourceMethods / sizeof *resourceMethods);
    if (Class object = objc_getClass("NBObject"))
        class_addMethod(object_getClass(object), @selector(resolveInstanceMethod:), (IMP)resolveStub, "B24@0:8:16");
}

static id deviceForPort(io_service_t port)
{
    static id device;
    static bool tried;
    @synchronized([NativeAdrenoMetalDevice class]) {
        if (tried)
            return device;
        tried = true;
        char turnip[1024];
        if (!turnipPath(turnip, sizeof turnip)) {
            fprintf(stderr, "NativeAdrenoMetal: %s: no Turnip beside the plugin\n", getprogname());
            return nil;
        }
        uint64_t registryID = 0;
        IORegistryEntryGetRegistryEntryID(port, &registryID);
        // Turnip's darwin backend opens the accelerator itself, by class (its default is the iOS IOAcceleratorES) with the plugin's type.
        setenv("TU_DARWIN_SERVICE", "AGXAccelerator", 1);
        // The frontend's refusals (a texture it does not make, with the reason) on stderr too, where stderr-log=1 shows them.
        setenv("NMB_LOG_STDERR", "1", 1);
        // Every process's device takes its memory from the one DroidVMGpu pool (droidvm-gpu-pool-mib, 512 MiB): the runtime's 64 MiB
        // blocks, one per pool a process uses and more kept in reserve, left WindowServer none for its memoryless targets.
        setenv("M2V_BLOCK_MIB", "8", 0);
        // The display takes plain rows: no Apple framebuffer or IOSurface compression, which this GPU does not write.
        setenv("CA_DISABLE_FRAMEBUFFER_COMPRESSION", "1", 1);
        CFPreferencesSetAppValue(CFSTR("CAEnableFramebufferCompression"), kCFBooleanFalse, kCFPreferencesCurrentApplication);
        CFPreferencesSetAppValue(CFSTR("CAEnableIOSurfaceCompression"), kCFBooleanFalse, kCFPreferencesCurrentApplication);
        // The runtime needs a writable shader-cache directory: the user cache or temp directory, else /private/var/tmp.
        char candidates[3][512] = {};
        if (!confstr(_CS_DARWIN_USER_CACHE_DIR, candidates[0], sizeof candidates[0] - 16))
            candidates[0][0] = 0;
        if (!confstr(_CS_DARWIN_USER_TEMP_DIR, candidates[1], sizeof candidates[1] - 16))
            candidates[1][0] = 0;
        strlcpy(candidates[2], "/private/var/tmp/", sizeof candidates[2]);
        for (unsigned i = 0; i < 3 && !device; i++) {
            if (!candidates[i][0])
                continue;
            strlcat(candidates[i], "m2v", sizeof candidates[i]);
            mkdir(candidates[i], 0700);
            if (access(candidates[i], W_OK) != 0)
                continue;
            @try {
                device = native_bridge_metal_open(turnip, candidates[i], registryID, missingSelector);
            } @catch (NSException *exception) {
                fprintf(stderr, "NativeAdrenoMetal: %s: %s\n", getprogname(), exception.reason.UTF8String);
                device = nil;
            }
        }
        if (device) {
            IOObjectRetain(port);
            gAcceleratorPort = port;
            addIOGPUMethods(device);
            fprintf(stderr, "NativeAdrenoMetal: %s: device %s\n", getprogname(), [[device name] UTF8String]);
        } else
            fprintf(stderr, "NativeAdrenoMetal: %s: no device: %.100s\n", getprogname(), nmb_last_error());
        return device;
    }
}

@implementation NativeAdrenoMetalDevice
- (id)initWithAcceleratorPort:(io_service_t)port
{
    // The registered device is the frontend's object, not this one (IOGPUMetalDevice's own initializer would open an IOGPU user client).
    // This one is kept: -[IOGPUMetalDevice dealloc] tears down state its initializer never made (a NULL dispatch queue).
    static NSMutableArray *kept;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ kept = [NSMutableArray array]; });
    @synchronized(kept) {
        [kept addObject:self];
    }
    return deviceForPort(port);
}
@end
