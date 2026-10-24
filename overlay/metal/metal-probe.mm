// SPDX-License-Identifier: BSD-2-Clause-Patent
// metal-probe: a launchd job of the Data seed (scripts/stage-gpu-plugin.py --probe) that reports to stderr (the kernel's stderr-log=1
// shows it) what a process sees of the Metal plugin: whether dyld loads NativeAdrenoMetal.bundle (dlerror otherwise) and how many
// Metal devices MTLCopyAllDevices returns, and whether each comes back by its registry ID (MTLCopyDeviceForRegistryID: VFX keys its
// resource managers by that device).
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

extern "C" id<MTLDevice> MTLCopyDeviceForRegistryID(uint64_t registryID);

int main(void)
{
    sleep(20);   // after the accelerator is published
    const char *plugin = "/Library/GPUBundles/NativeAdrenoMetal.bundle/Contents/MacOS/NativeAdrenoMetal";
    void *handle = dlopen(plugin, RTLD_NOW);
    const char *why = handle ? plugin : dlerror();
    for (size_t at = 0, length = strlen(why); at < length; at += 100)   // stderr-log shows 160 bytes of a write
        fprintf(stderr, "metal-probe: dlopen %s: %.100s\n", handle ? "ok" : "failed", why + at);
    @autoreleasepool {
        NSArray<id<MTLDevice>> *devices = MTLCopyAllDevices();
        fprintf(stderr, "metal-probe: %lu Metal devices\n", (unsigned long)devices.count);
        for (id<MTLDevice> device in devices)
        {
            id<MTLDevice> again = MTLCopyDeviceForRegistryID(device.registryID);
            fprintf(stderr, "metal-probe: device %s %p registry %#llx: by registry ID %p\n", device.name.UTF8String, device,
                    device.registryID, again);
        }
    }
    return 0;
}
