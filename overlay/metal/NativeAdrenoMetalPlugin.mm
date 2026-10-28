// SPDX-License-Identifier: BSD-2-Clause-Patent
// NativeAdrenoMetal for macOS: the Metal plugin of DroidVMGpu's AGXAccelerator. IOGPU's +[IOGPUMetalDevice registerAcceleratorService:] loads
// this bundle from /Library/GPUBundles, takes NativeAdrenoMetalDevice (it must subclass IOGPUMetalDevice) and registers what
// -initWithAcceleratorPort: returns with MTLAddDevice. That is UniXNU's native Metal frontend (drivers/NativeMetal/NativeBridgeMetalFrontend.mm:
// the metal2vulkan runtime on Turnip, beside this executable, on NativeAdreno's user client), one device per process. The iOS plugin's
// render-server machinery (status stream, display hand-off, pipeline packs) is not here. Reports go to stderr (the kernel's stderr-log=1).
#import <Foundation/Foundation.h>
#include <CommonCrypto/CommonDigest.h>
#include <IOKit/IOKitLib.h>
#include <atomic>
#include <dlfcn.h>
#include <mach/mach_time.h>
#include <objc/runtime.h>
#include <objc/message.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/sysctl.h>
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
// A texture over a buffer (IconRendering's symbol images) starts where a linear texture may: Turnip's texel-buffer alignment, which the
// frontend answers for the linear one; unanswered, iconservicesagent threw and no icon was drawn.
static NSUInteger textureBufferAlignment(id self, SEL, NSUInteger format)
{
    return ((NSUInteger (*)(id, SEL, NSUInteger))objc_msgSend)(self, sel_registerName("minimumLinearTextureAlignmentForPixelFormat:"), format);
}
// NativeMetal's shader priming (PrimeShaders.h) is not run on this board; the frontend's telemetry reads its progress.
extern "C" {volatile uint32_t native_prime_compiling, native_prime_libraries_done, native_prime_libraries_total, native_prime_made,
    native_prime_rate;}
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

// IOGPUMetalCommandBuffer's userDictionary: a mutable dictionary per command buffer, which MPS keeps its per-buffer state in. The stub's
// nil lost it: MPSCore made an array for the buffer, stored it in nil, released it and then added to it (WindowServer's desktop window
// effects, a pointer authentication failure in objc_msgSend once logged in).
static char kUserDictionaryKey;
static id userDictionary(id self, SEL)
{
    @synchronized(self) {
        NSMutableDictionary *dictionary = objc_getAssociatedObject(self, &kUserDictionaryKey);
        if (!dictionary) {
            dictionary = [NSMutableDictionary dictionary];
            objc_setAssociatedObject(self, &kUserDictionaryKey, dictionary, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
        }
        return dictionary;
    }
}

// The device's GPU core count, which MPSCore's MPSDevice::GetMPSDevice reads for every Apple GPU family: without it MPS has no device,
// MPSCommandBufferImageCache's init returns nil and MPSAutoCache reads through it (WindowServer's desktop window effects after login).
// The bridge has no answer for it; an Adreno's shader processors are counted as eight cores, which only sizes MPS's kernel choices.
static NSUInteger gpuCoreCount(id, SEL) { return 8; }

// _MTLFunction's bitCodeHash, a 32-byte digest: Metal's stitched-library path hashes each function's (createStitchingScriptHash), and the
// frontend's function had none, so the runtime's doesNotRecognizeSelector: threw (iconservicesagent crashed on every launch, and its
// relaunches used up its GPU opens). The digest names the function object: its name and a serial no other function in the process has.
static char kBitCodeHashKey;
static const void *bitCodeHash(id self, SEL)
{
    @synchronized(self) {
        NSData *hash = objc_getAssociatedObject(self, &kBitCodeHashKey);
        if (!hash) {
            static std::atomic<uint64_t> serial;
            NSString *text = [NSString stringWithFormat:@"%@#%llu", [self valueForKey:@"name"], (unsigned long long)++serial];
            NSData *bytes = [text dataUsingEncoding:NSUTF8StringEncoding];
            NSMutableData *digest = [NSMutableData dataWithLength:CC_SHA256_DIGEST_LENGTH];
            CC_SHA256(bytes.bytes, (CC_LONG)bytes.length, (unsigned char *)digest.mutableBytes);
            hash = digest;
            objc_setAssociatedObject(self, &kBitCodeHashKey, hash, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
        }
        return hash.bytes;
    }
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
        {"gpuCoreCount", (IMP)gpuCoreCount, "Q16@0:8", false},
        // _MTLGetMTLCompilerLLVMVersionForDevice reads it for a stitched library (Core Image's DAG programs): below 8 it takes the
        // default compiler version 0x7d17; unanswered, iconservicesagent threw and crashed on every launch
        {"featureProfile", (IMP)zero, "Q16@0:8", false},
        {"minimumTextureBufferAlignmentForPixelFormat:", (IMP)textureBufferAlignment, "Q24@0:8Q16", false},
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
    static const MethodSpec commandBufferMethods[] = {
        {"userDictionary", (IMP)userDictionary, "@16@0:8", true},
    };
    static const MethodSpec functionMethods[] = {
        {"bitCodeHash", (IMP)bitCodeHash, "^v16@0:8", false},
    };
    if (Class function = objc_getClass("NBFunction"))
        addMethods(function, functionMethods, sizeof functionMethods / sizeof *functionMethods);
    if (Class commandBuffer = objc_getClass("NBCommandBuffer"))
        addMethods(commandBuffer, commandBufferMethods, sizeof commandBufferMethods / sizeof *commandBufferMethods);
    // The frontend's classes declare no Metal protocols, and clients check them: MPSCommandBufferImageCache's init returns nil for a
    // command buffer that does not conform to MTLCommandBuffer, and MPSAutoCache reads through it (WindowServer after login).
    static const char *const conformances[][2] = {
        {"NBBuffer", "MTLBuffer"}, {"NBTexture", "MTLTexture"}, {"NBLibrary", "MTLLibrary"}, {"NBFunction", "MTLFunction"},
        {"NBComputePipeline", "MTLComputePipelineState"}, {"NBRenderPipeline", "MTLRenderPipelineState"},
        {"NBSampler", "MTLSamplerState"}, {"NBDepthStencil", "MTLDepthStencilState"}, {"NBEvent", "MTLEvent"},
        {"NBSharedEvent", "MTLSharedEvent"}, {"NBFence", "MTLFence"}, {"NBQueue", "MTLCommandQueue"},
        {"NBCommandBuffer", "MTLCommandBuffer"}, {"NBEncoder", "MTLCommandEncoder"}, {"NBComputeEncoder", "MTLComputeCommandEncoder"},
        {"NBRenderEncoder", "MTLRenderCommandEncoder"}, {"NBBlitEncoder", "MTLBlitCommandEncoder"}, {"NBHeap", "MTLHeap"},
        {"NBBinaryArchive", "MTLBinaryArchive"},
    };
    for (const auto &conformance : conformances) {
        Class cls = objc_getClass(conformance[0]);
        Protocol *protocol = objc_getProtocol(conformance[1]);
        if (cls && protocol)
            class_addProtocol(cls, protocol);
        else
            fprintf(stderr, "NativeAdrenoMetal: %s: no %s for %s\n", getprogname(), conformance[1], conformance[0]);
    }
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
        // The display takes plain rows: no Apple framebuffer or IOSurface compression, which this GPU does not write.
        setenv("CA_DISABLE_FRAMEBUFFER_COMPRESSION", "1", 1);
        CFPreferencesSetAppValue(CFSTR("CAEnableFramebufferCompression"), kCFBooleanFalse, kCFPreferencesCurrentApplication);
        CFPreferencesSetAppValue(CFSTR("CAEnableIOSurfaceCompression"), kCFBooleanFalse, kCFPreferencesCurrentApplication);
        // The runtime needs a writable shader-cache directory: the user cache directory, the process's own folder in it (a platform
        // sandbox lets a service write only there), the temp directory, else /private/var/tmp.
        char candidates[4][512] = {};
        if (!confstr(_CS_DARWIN_USER_CACHE_DIR, candidates[0], sizeof candidates[0] - 16))
            candidates[0][0] = 0;
        if (NSString *bundle = NSBundle.mainBundle.bundleIdentifier; candidates[0][0] && bundle.length) {
            snprintf(candidates[1], sizeof candidates[1] - 16, "%s%s/", candidates[0], bundle.UTF8String);
            mkdir(candidates[1], 0700);
        }
        if (!confstr(_CS_DARWIN_USER_TEMP_DIR, candidates[2], sizeof candidates[2] - 16))
            candidates[2][0] = 0;
        strlcpy(candidates[3], "/private/var/tmp/", sizeof candidates[3]);
        for (unsigned i = 0; i < 4 && !device; i++) {
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
            if (!device) {   // the reason past the path, which the kernel's log line would cut off
                const char *error = nmb_last_error(), *kind = error ? strstr(error, "kind") : nullptr;
                fprintf(stderr, "NativeAdrenoMetal: %s: %s refused: %.160s\n", getprogname(), candidates[i], kind ? kind : error ? error : "");
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

// The kernel boot argument ca-triple-buffer=1 sets WindowServer's CA_FORCE_TRIPLE_BUFFERED_LATENCY (QuartzCore's debug option 198,
// read by IOMFBDisplay::can_update_): CoreAnimation then renders a frame ahead (a frame of presentation latency) instead of starting
// each frame only after the last one's buffer came back, which it otherwise does whenever a frame took longer than a refresh. A window
// drag of the heavy window went from 56-60 to 61-67 frames a second (kc253).
__attribute__((constructor)) static void tripleBufferFromBootArgs() {
 char args[1024]={};size_t size=sizeof(args)-1;
 if(strcmp(getprogname(),"WindowServer") || sysctlbyname("kern.bootargs",args,&size,nullptr,0) || !strstr(args,"ca-triple-buffer=1"))return;
 auto setOption=reinterpret_cast<void(*)(unsigned,bool)>(dlsym(RTLD_DEFAULT,"CASetDebugOption"));
 if(setOption)setOption(198,true);
 fprintf(stderr,"NativeAdrenoMetal: CA_FORCE_TRIPLE_BUFFERED_LATENCY %s\n",setOption?"set":"not found");
}

// The kernel boot argument ca-free-wakeup=1: SkyLight starts each WindowServer update at -[CAWindowServerDisplay nextWakeupTime], which
// QuartzCore's IOMFBServer::next_wakeup_time puts on the refresh grid (the last VBL plus a frame): an update that took 13 ms is
// followed by one at 16.7 ms. This answers the earlier of that and max(now, the last update's start + a refresh), the start being the
// last -beginExternalUpdate:usingSoftwareRenderer:; DroidVMDisplay shows a swap when it comes, not at a VBL. Without an update in the
// last second the grid's answer stands. The refresh is droidvm-display-hz's (120 by default). A heavy window drag went from 60 frames
// a second (updates 16.6 ms apart, kc283) to 96 (10.4 ms, kc282), its input to GPU end from 18.7 to 14.7 ms (medians).
static std::atomic<uint64_t> gUpdateBegan{0},gLastAsk{0};
static double hostSeconds(uint64_t t) {
 static mach_timebase_info_data_t base;if(!base.denom)mach_timebase_info(&base);
 return (double)t*base.numer/base.denom/1e9;
}
static uint64_t hostTicks(double seconds) {
 static mach_timebase_info_data_t base;if(!base.denom)mach_timebase_info(&base);
 return (uint64_t)(seconds*1e9*base.denom/base.numer);
}
__attribute__((constructor)) static void freeWakeupFromBootArgs() {
 char args[1024]={};size_t size=sizeof(args)-1;
 if(strcmp(getprogname(),"WindowServer") || sysctlbyname("kern.bootargs",args,&size,nullptr,0) || !strstr(args,"ca-free-wakeup=1"))return;
 const char *hz=strstr(args,"droidvm-display-hz=");
 const double refresh=1.0/(hz && atoi(hz+19)>=30 && atoi(hz+19)<=240?atoi(hz+19):120);
 Class display=objc_getClass("CAWindowServerDisplay");
 static SEL wakeSel=sel_registerName("nextWakeupTime"),beginSel=sel_registerName("beginExternalUpdate:usingSoftwareRenderer:");
 Method wake=display?class_getInstanceMethod(display,wakeSel):nullptr,begin=display?class_getInstanceMethod(display,beginSel):nullptr;
 if(!wake || !begin || method_getTypeEncoding(wake)[0]!='d' || method_getNumberOfArguments(begin)!=4) {
  fprintf(stderr,"NativeAdrenoMetal: free wakeup: CAWindowServerDisplay lacks %s\n",!wake?"nextWakeupTime":"beginExternalUpdate:usingSoftwareRenderer:");
  return;
 }
 static auto wakeGrid=reinterpret_cast<double(*)(id,SEL)>(method_getImplementation(wake));
 static auto beginOriginal=reinterpret_cast<uint64_t(*)(id,SEL,void *,uint64_t)>(method_getImplementation(begin));
 method_setImplementation(begin,imp_implementationWithBlock(^uint64_t(id self,void *update,uint64_t software) {
  // The update's start is SkyLight's last ask before it, where its update callback began (the callback prepares for 0.8 ms before
  // this, kc290): updates a refresh apart from there are a refresh apart here too.
  const uint64_t now=mach_absolute_time(),asked=gLastAsk.load(std::memory_order_relaxed);
  gUpdateBegan.store(asked && now-asked<hostTicks(0.003)?asked:now,std::memory_order_relaxed);
  return beginOriginal(self,beginSel,update,software);
 }));
 method_setImplementation(wake,imp_implementationWithBlock(^double(id self) {
  const double grid=wakeGrid(self,wakeSel);
  gLastAsk.store(mach_absolute_time(),std::memory_order_relaxed);
  const uint64_t began=gUpdateBegan.load(std::memory_order_relaxed);
  if(grid<=0 || !began)return grid;
  const double now=hostSeconds(mach_absolute_time()),start=hostSeconds(began);
  if(now-start>1.0)return grid;
  // SkyLight (WS::Updater::UpdateDisplays) adds its updater delay (0.5 ms) to the answer and updates at once only when the last update
  // is more than 1.25 frames before that; otherwise it schedules the update for then. Told "now" once a refresh had passed, it put the
  // update off until 1.25 frames after the last, and updates came 10 ms apart (kc288). Before the due time the answer is the due time
  // less the delay, when SkyLight's timer fires; from then on it is the least that is 1.25 frames past the last start (and 1 ms over),
  // so SkyLight updates at once. With "now" plus 1.25 frames, a wakeup with nothing new to draw put the next one 11 ms off, and a
  // tenth of the updates came 20 ms apart (kc291).
  const double due=start+refresh-0.0005,ahead=start+1.25*refresh+0.001;
  if(now<due)return due<grid?due:grid;
  return now>ahead?now:ahead;
 }));
 fprintf(stderr,"NativeAdrenoMetal: free wakeup on (%.2f ms)\n",refresh*1e3);
}
