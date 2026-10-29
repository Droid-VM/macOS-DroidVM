// SPDX-License-Identifier: BSD-2-Clause-Patent
// gpu-bench: a launchd job of the Data seed (scripts/stage-gpu-plugin.py --probe) that times the simplest full-screen passes on the GPU
// (command buffer GPUStartTime..GPUEndTime, median of 30) and reports them to stderr (stderr-log=1). WindowServer's frames cost about
// 0.9 ms per million pixels whatever their passes do, compositing alike: is a plain fill or copy as slow, and does it matter whether the
// target is an IOSurface (Core Animation's framebuffers and backing stores) or a private texture?
#import <Foundation/Foundation.h>
#import <IOSurface/IOSurface.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <stdio.h>
#include <unistd.h>
#include <vector>

static NSString *const kSource = @R"(
#include <metal_stdlib>
using namespace metal;
struct V {float4 position [[position]]; float2 uv;};
vertex V fullscreen(uint id [[vertex_id]]) {
    float2 uv = float2((id << 1) & 2, id & 2);
    return {float4(uv * float2(2, -2) + float2(-1, 1), 0, 1), uv};
}
fragment half4 fill() {return half4(0.2h, 0.4h, 0.6h, 0.5h);}
fragment half4 copy(V in [[stage_in]], texture2d<half> source [[texture(0)]]) {
    constexpr sampler linear(filter::linear);
    return source.sample(linear, in.uv);
}
fragment half4 blur(V in [[stage_in]], texture2d<half> source [[texture(0)]]) {
    constexpr sampler linear(filter::linear);
    half4 sum = 0;
    for (int i = -4; i <= 4; i++)
        sum += source.sample(linear, in.uv + float2(i * 2.0 / 1280.0, 0)) * half(1.0 / 9.0);
    return sum;
}
)";

static const NSUInteger kWidth = 1280, kHeight = 800;

static id<MTLTexture> privateTexture(id<MTLDevice> device, NSUInteger width, NSUInteger height)
{
    MTLTextureDescriptor *d = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:width height:height
                                                                             mipmapped:NO];
    d.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
    d.storageMode = MTLStorageModePrivate;
    return [device newTextureWithDescriptor:d];
}

static id<MTLTexture> surfaceTexture(id<MTLDevice> device)
{
    NSDictionary *properties = @{(id)kIOSurfaceWidth: @(kWidth), (id)kIOSurfaceHeight: @(kHeight), (id)kIOSurfaceBytesPerElement: @4,
                                 (id)kIOSurfaceBytesPerRow: @(kWidth * 4), (id)kIOSurfacePixelFormat: @((uint32_t)'BGRA')};
    IOSurfaceRef surface = IOSurfaceCreate((__bridge CFDictionaryRef)properties);
    if (!surface)
        return nil;
    MTLTextureDescriptor *d = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:kWidth height:kHeight
                                                                             mipmapped:NO];
    d.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
    d.storageMode = MTLStorageModeShared;
    id<MTLTexture> texture = [device newTextureWithDescriptor:d iosurface:surface plane:0];
    CFRelease(surface);
    return texture;
}

// passes: render passes per command buffer, each drawing one full-target triangle (or none: a clear).
static void run(id<MTLCommandQueue> queue, const char *name, id<MTLTexture> target, id<MTLRenderPipelineState> pipeline,
                id<MTLTexture> source, unsigned passes, bool clear)
{
    if (!target || (!pipeline && !clear)) {
        fprintf(stderr, "gpu-bench: %s: no %s\n", name, target ? "pipeline" : "target");
        return;
    }
    std::vector<double> times;
    for (int round = 0; round < 33; round++) {
        id<MTLCommandBuffer> buffer = [queue commandBuffer];
        for (unsigned pass = 0; pass < passes; pass++) {
            MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
            rp.colorAttachments[0].texture = target;
            rp.colorAttachments[0].loadAction = clear ? MTLLoadActionClear : MTLLoadActionDontCare;
            rp.colorAttachments[0].storeAction = MTLStoreActionStore;
            rp.colorAttachments[0].clearColor = MTLClearColorMake(0.1, 0.2, 0.3, 1);
            id<MTLRenderCommandEncoder> encoder = [buffer renderCommandEncoderWithDescriptor:rp];
            if (pipeline) {
                [encoder setRenderPipelineState:pipeline];
                if (source)
                    [encoder setFragmentTexture:source atIndex:0];
                [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            }
            [encoder endEncoding];
        }
        [buffer commit];
        [buffer waitUntilCompleted];
        if (round >= 3 && buffer.status == MTLCommandBufferStatusCompleted)
            times.push_back((buffer.GPUEndTime - buffer.GPUStartTime) * 1e6);
    }
    if (times.empty()) {
        fprintf(stderr, "gpu-bench: %s: no completed buffers\n", name);
        return;
    }
    std::sort(times.begin(), times.end());
    const double median = times[times.size() / 2], mpx = double(target.width) * target.height * passes / 1e6;
    fprintf(stderr, "gpu-bench: %-14s %ux %4lux%-4lu median %7.0f us min %7.0f us %6.2f Gpx/s %6.1f us/pass\n", name, passes,
            (unsigned long)target.width, (unsigned long)target.height, median, times.front(), mpx / median * 1e-3, median / passes);
}

int main(void)
{
    sleep(90);   // WindowServer up and the login screen still
    @autoreleasepool {
        NSArray<id<MTLDevice>> *devices = MTLCopyAllDevices();
        id<MTLDevice> device = devices.firstObject;
        if (!device) {
            fprintf(stderr, "gpu-bench: no Metal device\n");
            return 1;
        }
        NSError *error = nil;
        id<MTLLibrary> library = [device newLibraryWithSource:kSource options:nil error:&error];
        if (!library) {
            fprintf(stderr, "gpu-bench: library: %.120s\n", error.localizedDescription.UTF8String);
            return 1;
        }
        auto pipeline = [&](NSString *fragment, bool blend) -> id<MTLRenderPipelineState> {
            MTLRenderPipelineDescriptor *d = [MTLRenderPipelineDescriptor new];
            d.vertexFunction = [library newFunctionWithName:@"fullscreen"];
            d.fragmentFunction = [library newFunctionWithName:fragment];
            d.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
            if (blend) {
                d.colorAttachments[0].blendingEnabled = YES;
                d.colorAttachments[0].sourceRGBBlendFactor = d.colorAttachments[0].sourceAlphaBlendFactor = MTLBlendFactorOne;
                d.colorAttachments[0].destinationRGBBlendFactor = d.colorAttachments[0].destinationAlphaBlendFactor =
                    MTLBlendFactorOneMinusSourceAlpha;
            }
            NSError *failure = nil;
            id<MTLRenderPipelineState> state = [device newRenderPipelineStateWithDescriptor:d error:&failure];
            if (!state)
                fprintf(stderr, "gpu-bench: pipeline %s: %.100s\n", fragment.UTF8String, failure.localizedDescription.UTF8String);
            return state;
        };
        id<MTLRenderPipelineState> fill = pipeline(@"fill", false), blendFill = pipeline(@"fill", true), copy = pipeline(@"copy", false),
                                   blur = pipeline(@"blur", false);
        id<MTLCommandQueue> queue = [device newCommandQueue];
        id<MTLTexture> privateA = privateTexture(device, kWidth, kHeight), privateB = privateTexture(device, kWidth, kHeight),
                       surfaceA = surfaceTexture(device), surfaceB = surfaceTexture(device), tiny = privateTexture(device, 64, 64);
        fprintf(stderr, "gpu-bench: %s, targets %s %s\n", device.name.UTF8String, privateA ? "private" : "-", surfaceA ? "surface" : "-");
        for (int repeat = 0; repeat < 2; repeat++) {
            run(queue, "clear-private", privateA, nil, nil, 1, true);
            run(queue, "clear-surface", surfaceA, nil, nil, 1, true);
            run(queue, "fill-private", privateA, fill, nil, 1, false);
            run(queue, "fill-surface", surfaceA, fill, nil, 1, false);
            run(queue, "blend-private", privateA, blendFill, nil, 1, false);
            run(queue, "blend-surface", surfaceA, blendFill, nil, 1, false);
            run(queue, "copy-private", privateB, copy, privateA, 1, false);
            run(queue, "copy-surface", surfaceB, copy, surfaceA, 1, false);
            run(queue, "blur-private", privateB, blur, privateA, 1, false);
            run(queue, "blur-surface", surfaceB, blur, surfaceA, 1, false);
            run(queue, "fill-private", privateA, fill, nil, 8, false);
            run(queue, "fill-surface", surfaceA, fill, nil, 8, false);
            run(queue, "fill-tiny", tiny, fill, nil, 50, false);
            run(queue, "clear-tiny", tiny, nil, nil, 50, true);
        }
        // With tu-pass-timing=1, Turnip logs its per-pass GPU times every 10 s at the next pass: one more after 11 s.
        sleep(11);
        run(queue, "fill-private", privateA, fill, nil, 1, false);
        fprintf(stderr, "gpu-bench: done\n");
    }
    return 0;
}
