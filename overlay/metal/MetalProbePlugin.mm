// SPDX-License-Identifier: BSD-2-Clause-Patent
// A stand-in for the Adreno Metal plugin that only proves the way there: Metal's discovery finds AGXAccelerator (DroidVMGpu), loads
// this bundle through MetalPluginName and calls the principal class's initWithAcceleratorPort:. It reports to stderr (the kernel's
// stderr-log=1 shows it), opens the accelerator with the plugin's type ('AG', NativeAdrenoPluginOpenType) and returns no device.
// IOGPU's +[IOGPUMetalDevice registerAcceleratorService:] takes only a subclass of IOGPUMetalDevice (IOGPU.framework, already loaded by
// Metal; linked through overlay/metal/frameworks/IOGPU.framework/IOGPU.tbd).
#import <Foundation/Foundation.h>
#include <IOKit/IOKitLib.h>
#include <stdio.h>
#include <unistd.h>

@interface IOGPUMetalDevice : NSObject
@end

@interface NativeAdrenoMetalDevice : IOGPUMetalDevice
- (id)initWithAcceleratorPort:(io_service_t)port;
@end

@implementation NativeAdrenoMetalDevice
- (id)initWithAcceleratorPort:(io_service_t)port
{
    io_connect_t connection = 0;
    kern_return_t status = IOServiceOpen(port, mach_task_self(), 0x4147, &connection);
    fprintf(stderr, "NativeAdrenoMetal probe: pid %d port %#x open %#x\n", getpid(), port, status);
    if (connection)
        IOServiceClose(connection);
    return nil;
}
@end

__attribute__((constructor)) static void loaded(void)
{
    fprintf(stderr, "NativeAdrenoMetal probe: loaded in pid %d\n", getpid());
}
