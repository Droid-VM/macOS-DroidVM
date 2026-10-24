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
    fprintf(stderr, "NativeAdrenoMetal: %s: missing %s\n", getprogname(), selector);
    (void)cls;
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
// themselves (-_setDeviceWrapper:, weak; -_deviceWrapper is the device itself without one).
static io_service_t gAcceleratorPort;
static id gAcceleratorService;
static __weak id gDeviceWrapper;

static void setAcceleratorService(id, SEL, id service) { gAcceleratorService = service; }
static io_service_t acceleratorPort(id, SEL) { return gAcceleratorPort; }
static void setDeviceWrapper(id, SEL, id wrapper) { gDeviceWrapper = wrapper; }
static id deviceWrapper(id self, SEL) { id wrapper = gDeviceWrapper; return wrapper ? wrapper : self; }
static BOOL isBuiltIn(id, SEL) { return YES; }

static void addIOGPUMethods(id device)
{
    Class cls = object_getClass(device);
    const struct { const char *name; IMP imp; const char *types; } methods[] = {
        {"_setAcceleratorService:", (IMP)setAcceleratorService, "v24@0:8@16"},
        {"acceleratorPort", (IMP)acceleratorPort, "I16@0:8"},
        {"_setDeviceWrapper:", (IMP)setDeviceWrapper, "v24@0:8@16"},
        {"_deviceWrapper", (IMP)deviceWrapper, "@16@0:8"},
        {"isBuiltIn", (IMP)isBuiltIn, "B16@0:8"},
    };
    for (const auto &method : methods) {   // the base class's own answers stay
        SEL selector = sel_registerName(method.name);
        if (![cls instancesRespondToSelector:selector])
            class_addMethod(cls, selector, method.imp, method.types);
    }
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
