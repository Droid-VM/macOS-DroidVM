// SPDX-License-Identifier: BSD-2-Clause-Patent
// DroidVMDisplay: the macOS display of a DroidVM guest, an IOMobileFramebufferLegacy (IOMobileGraphicsFamily) over the firmware
// framebuffer, as AppleParavirtDisplay (AppleParavirtGPUIOGPUFamily, the vma2 display) is over the paravirtual GPU. The family runs
// the swap queue, the user client and the notifications; the driver supplies the hardware hooks AppleParavirtDisplay overrides.
//
// Stage 1: the GOP framebuffer the bootloader set up (boot_args Video: PE_Video of the platform) is the scanout. A 16 ms timer takes
// the queued swaps (AppleParavirtDisplay::swap_begin_gated) and the CPU copies the swap's main IOSurface into it, then completes the
// swap. Display attributes, timing and color elements are published as AppleParavirtDisplay::createDisplayAttributes does.
//
// Discovery: IOMobileFramebuffer.framework (iomfb_populate_all_display_infos) expects as many framebuffers as the DisplayPortCount
// of the AppleParavirtGPU services when an /arm-io node is compatible "paravirtualizedgraphics,gpu", and waits for them. Apple's
// AppleParavirtGPUIOGPUFamily is not in the collection, so the class of that name here is the nub of that node and the provider
// of the display.
//
// Offsets into IOMobileFramebufferLegacy and its swap requests are those AppleParavirtDisplay of the same kernelcache (kc265)
// uses; the addresses noted are its code (research/re/apd/).
#include "IOMobileFramebufferABI.h"
#include <IOKit/IOLib.h>
#include <IOKit/IOPlatformExpert.h>
#include <IOKit/IOTimerEventSource.h>
#include <IOKit/IOUserClient.h>
#include <IOKit/IOWorkLoop.h>
#include <IOKit/pwr_mgt/RootDomain.h>
#include <libkern/c++/OSArray.h>
#include <libkern/c++/OSDictionary.h>
#include <libkern/c++/OSNumber.h>
#include <libkern/c++/OSString.h>

extern "C" task_t kernel_task;

// IOMobileFramebufferLegacy (instance 0x1af8)
static constexpr size_t kCurrentSwap = 6032;       // the swap being programmed (swap_begin_gated 0x...dba5c, clean_queue_gated)
static constexpr size_t kSwapQueueFirst = 6040;    // TAILQ head of the pending swaps
static constexpr size_t kSwapQueueLast = 6048;     // its tqh_last
static constexpr size_t kDisplayWidth = 6400;      // display_width() / display_height() (set_digital_out_mode block 0x...d6a60)
static constexpr size_t kDisplayHeight = 6404;
static constexpr size_t kSystemPowerState = 6428;  // u32: setPowerState's state (do_power_state_change_action_gated, request type 0)
static constexpr size_t kAPIPowerState = 6432;     // u32: setAPIPowerState's state (power_state_change_interrupt, request type 1)
static constexpr size_t kHardwarePowered = 6436;   // u32: the display is powered ("PowerStates-Cntr" in swap_wait_gated's report); with
                                                   // kHardwareStarted set, swap_wait fails kIOReturnOffline while it is 0 (0x...2d1e4)
static constexpr size_t kSwapInfoHeld = 6902;      // u16: swap info notifications are held (notify_swap_done_gated 0x...d9430)
static constexpr size_t kSwapInfoTime = 264;       // the swap info's time (notify_swap_done_gated 0x...d93f0)
// IOMobileFramebuffer (instance 144): set before power management in AppleParavirtDisplay's start_hardware block (0x...d8e90)
static constexpr size_t kHardwareStarted = 140;
// IOMFBSwapIORequest
static constexpr size_t kSwapLayers = 824;         // bit 0: main surface, bit 1: cursor surface (program_hardware_gated 0x...db858)
static constexpr size_t kSwapDropReasons = 844;    // programmed when nothing but bit 3 is set, else dropped (swap_begin_gated 0x...dbac0)
static constexpr size_t kSwapInfoA = 752;         // swap info words 3 and 4 (notify_swap_done_gated 0x...d93f4)
static constexpr size_t kSwapInfoB = 816;
static constexpr size_t kSwapMainSurface = 2752;   // layer i's surface at + 8 * i
static constexpr unsigned kSwapLayerCount = 4;
static constexpr size_t kSwapNext = 3192;          // TAILQ entry of the queue
static constexpr size_t kSwapPrev = 3200;
// IOMFBNotifyRequest
static constexpr size_t kNotifyAsyncReference = 24;   // OSAsyncReference64 of the user client (do_swap_info_notify_gated 0x...d9370)
static constexpr size_t kNotifyMask = 120;            // which swap info words the client wants; bit 31: as 32-bit halves
static constexpr size_t kNotifyLastTime = 128;        // the time of the previous notification (word 1 is the delta)
// IOAVElement: the element ID and its score (createTimingElementWithDimensionsAndRate 0x...d8974, createColorElementWithDepthAndEDR)
static constexpr size_t kElementID = 16;
static constexpr size_t kElementScore = 24;

template <typename T> static T &at(void *base, size_t offset) {return *reinterpret_cast<T *>(static_cast<uint8_t *>(base) + offset);}

// Kernel interfaces of the collection's kexts with no header here.
void iomfbUpdateSwapInfoState(IOMobileFramebufferLegacy *, IOMFBSwapIORequest *, uint32_t)
    __asm("__ZN25IOMobileFramebufferLegacy28update_swap_info_state_gatedEP18IOMFBSwapIORequest24IOMFBSwapCompletionState");
void iomfbSwapInfoDispatch(IOMobileFramebufferLegacy *, void *)
    __asm("__ZN25IOMobileFramebufferLegacy31swap_info_notify_dispatch_gatedEPNS_12SwapInfoBlobE");
IOReturn userClientSendAsyncResult(io_user_reference_t *reference, IOReturn, io_user_reference_t *args, UInt32 count, IOOptionBits)
    __asm("__ZN12IOUserClient28sendAsyncResult64WithOptionsEPyiS0_jj");   // protected in IOUserClient.h
uint64_t ioSurfaceWidth(const IOSurface *) __asm("__ZNK9IOSurface8getWidthEv");
uint64_t ioSurfaceHeight(const IOSurface *) __asm("__ZNK9IOSurface9getHeightEv");
uint64_t ioSurfaceBytesPerRow(const IOSurface *) __asm("__ZNK9IOSurface14getBytesPerRowEv");
uint64_t ioSurfaceBaseOffset(const IOSurface *) __asm("__ZNK9IOSurface13getBaseOffsetEv");
uint32_t ioSurfacePixelFormat(const IOSurface *) __asm("__ZNK9IOSurface14getPixelFormatEv");
IOMemoryDescriptor *ioSurfaceMemory(const IOSurface *) __asm("__ZNK9IOSurface19getMemoryDescriptorEv");
// IOAVVideoTimingData: per axis (horizontal, vertical) 32 bytes of which total +4, active +8, sync width +12, back porch +16,
// front porch +20, sync rate +24, sync polarity +28, then the pixel clock at +68 (IOAVVideoTimingElement's getters; the element keeps
// the data at +32).
OSObject *ioavTimingWithData(const void *data, uint32_t standardType, uint32_t timingStandard)
    __asm("__ZN22IOAVVideoTimingElement8withDataEPK19IOAVVideoTimingData16IOAVStandardType23IOAVVideoTimingStandard");
void ioavTimingSetColorElements(OSObject *, OSArray *) __asm("__ZN22IOAVVideoTimingElement16setColorElementsEP7OSArray");
OSObject *ioavColorWithCapabilities(uint32_t standardType, uint32_t depth, uint32_t encoding, uint32_t range, uint32_t eotf,
                                    uint32_t colorimetry, bool, const OSDictionary *, const OSDictionary *, const OSDictionary *,
                                    const OSSet *)
    __asm("__ZN21IOAVVideoColorElement16withCapabilitiesE16IOAVStandardTypej22IOAVVideoPixelEncoding26IOAVVideoColorDynamicRange"
          "18IOAVVideoColorEOTF20IOAVVideoColorimetrybPK12OSDictionaryS7_S7_PK5OSSet");

// macOS 27's IOMobileFramebuffer.framework submits a 1760-byte swap record (kern_SwapEnd: IOMobileFramebufferUserClient selector 5)
// and the 26.5 family of the collection checks for 1416 bytes. The two agree up to 0x51e; 27 has 16 more bytes there (its per-layer
// fields at 0x52e and 0x544 are 26.5's 0x51e and 0x534) and its other additions at the end, which the legacy family has no use for.
static constexpr uint32_t kSwapSubmitSelector = 5, kSwapRecord27 = 1760, kSwapRecord265 = 1416;
static constexpr uint32_t kSwapRecordSplit = 0x51e, kSwapRecordInserted = 16;
extern const char iomfbUserClientMetaClass[] __asm("__ZN29IOMobileFramebufferUserClient10gMetaClassE");
extern "C" void virt_set_external_method_hook(void (*)(IOUserClient *, IOExternalMethodArguments *));   // xnu-m IOUserClient.cpp

static void convertSwapRecord(IOUserClient *client, IOExternalMethodArguments *args)
{
    if (args->selector != kSwapSubmitSelector || args->structureInputSize != kSwapRecord27 ||
        !client->metaCast(reinterpret_cast<const OSMetaClass *>(iomfbUserClientMetaClass)))
        return;
    auto *record = const_cast<uint8_t *>(static_cast<const uint8_t *>(args->structureInput));   // the MIG request's inband buffer
    memmove(record + kSwapRecordSplit, record + kSwapRecordSplit + kSwapRecordInserted, kSwapRecord265 - kSwapRecordSplit);
    args->structureInputSize = kSwapRecord265;
}

class AppleParavirtGPU : public IOService {
    OSDeclareDefaultStructors(AppleParavirtGPU)
public:
    bool start(IOService *provider) override;
};

OSDefineMetaClassAndStructors(AppleParavirtGPU, IOService)

bool AppleParavirtGPU::start(IOService *provider)
{
    if (!IOService::start(provider))
        return false;
    setProperty("DisplayPortCount", 1ULL, 32);
    registerService();
    IOLog("DroidVMDisplay: AppleParavirtGPU on %s, 1 display port\n", provider->getName());
    return true;
}

class DroidVMDisplay : public IOMobileFramebufferLegacy {
    OSDeclareDefaultStructors(DroidVMDisplay)
public:
    bool start(IOService *) override;
    void stop(IOService *) override;
    bool start_hardware() override;
    IOReturn stop_hardware_gated() override;
    IOReturn swap_begin_gated() override;
    IOReturn swap_wait(IOMobileFramebufferUserClient *, unsigned int, unsigned int, unsigned int) override;
    IOReturn verify_swap(IOMFBSwapIORequest *) override;
    IOReturn swap_layer_map(IOMFBSwapIORequest *, unsigned int) override;
    IOReturn surface_layer_map(IOMFB::AP::DisplayedData *, unsigned int, IOSurface *) override;
    IOReturn surface_layer_unmap(IOMFB::AP::DisplayedData *, unsigned int) override;
    IOReturn set_display_device(unsigned int) override;
    IOReturn set_digital_out_mode(unsigned int, unsigned int) override;
    IOReturn get_dot_pitch(unsigned int *) override;
    IOReturn get_gamma_table(IOMFBGammaTable *) override;
    IOReturn set_gamma_table(IOMFBGammaTable *) override;
    IOReturn set_color_remap_mode(DisplayColorRemapMode) override;
    IOReturn get_color_remap_mode(DisplayColorRemapMode *) const override;
    IOReturn swap_set_color_matrix(IOMFBColorFixedMatrix *, IOMFBColorMatrixFunction, unsigned int) override;
    IOReturn set_notify_tag_mask_gated(IOMFB_NotificationType, IOMFBNotifyRequest *, unsigned int) override;
    IOReturn supported_frame_info(unsigned int, unsigned int *, char (*)[64], unsigned int *) override;
    IOReturn factory_portal(void *, task *) override;
    IOReturn executeFactoryConfigurations_gated() override;
    IOReturn set_frame_info_notification_state_gated(IOMFBNotifyRequest *, bool) override;
    IOReturn do_swap_info_notify_gated(IOMFBNotifyRequest *, const SwapInfoBlob *) override;
    IOReturn notify_swap_done_gated(unsigned int, ::SwapInfoBlob *, unsigned int *, unsigned int) override;
    IOReturn notify_crc_ready_gated(unsigned int) override;
    bool are_timings_enabled() const override;
    IOReturn do_power_state_change_gated() override;

private:
    static constexpr uint32_t kRefreshHz = 60;
    static constexpr uint32_t kWidthMM = 286, kHeightMM = 179;   // a 13.3-inch 16:10 panel: about 114 dpi at 1280x800
    static constexpr uint32_t kColorID = 100, kTimingID = 1000;  // AppleParavirtDisplay's IDs of its first color and timing element

    bool clean_queue_gated();
    void program_hardware_gated();
    void copySurface(IOSurface *);
    bool createDisplayAttributes();
    static void vblFired(OSObject *, IOTimerEventSource *);

    struct SwapInfo {   // IOMobileFramebufferLegacy::SwapInfoBlob as AppleParavirtDisplay fills it (48 bytes)
        uint32_t swapID;
        uint64_t words[5];
    };
    static_assert(sizeof(SwapInfo) == 48, "IOMobileFramebufferLegacy::SwapInfoBlob");
    static constexpr unsigned kSwapInfoRing = 6;

    PE_Video fVideo;
    IOMemoryMap *fScanoutMap;
    uint8_t *fHalfToByte;     // 'RGhA' surfaces: each half-float channel's 8-bit value, clamped to [0, 1]
    uint16_t *fRow;           // one 'RGhA' row
    uint64_t fRowBytes;
    uint8_t *fScanout;
    IOTimerEventSource *fVBL;
    DisplayColorRemapMode fColorRemapMode;
    uint32_t fSurfaceFormat;
    bool fDisplayOn;
    uint64_t fFrames;
    uint64_t fLayerShape;             // bring-up: the layers of the last swap, logged when they change
    uint64_t fLastLit, fLastCenter;   // bring-up: lit pixels and centre pixel of the last frame shown
    uint64_t fTicks, fDropped, fReported;   // swap_begin_gated runs, swaps dropped, fSubmitted + fFrames + fDropped + fStalled at the last report
    uint64_t fWaitFailures;                 // diagnostic: swap_wait calls that failed (WindowServer's display readiness)
    uint64_t fSubmitted, fStalled;          // swaps verified, VBL ticks with a queued swap clean_queue_gated did not hand over
    SwapInfo fSwapInfo[kSwapInfoRing];   // held while kSwapInfoHeld is set, sent in order afterwards
    unsigned fSwapInfoRead, fSwapInfoWrite;
};

OSDefineMetaClassAndStructors(DroidVMDisplay, IOMobileFramebufferLegacy)

static IOPMPowerState gPowerStates[2] = {   // AppleParavirtDisplay's gPowerState
    {1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
    {1, kIOPMDeviceUsable, kIOPMPowerOn, kIOPMPowerOn, 0, 0, 0, 0, 0, 0, 0, 0},
};

bool DroidVMDisplay::start(IOService *provider)
{
    if (getPlatform()->getConsoleInfo(&fVideo) != kIOReturnSuccess || !fVideo.v_baseAddr || fVideo.v_depth != 32) {
        IOLog("DroidVMDisplay: no 32-bit boot framebuffer (base %#lx depth %lu)\n", fVideo.v_baseAddr, fVideo.v_depth);
        return false;
    }
    IOMemoryDescriptor *memory = IOMemoryDescriptor::withPhysicalAddress(fVideo.v_baseAddr & ~3UL, fVideo.v_rowBytes * fVideo.v_height,
                                                                         kIODirectionInOut);
    if (memory) {
        fScanoutMap = memory->createMappingInTask(kernel_task, 0, kIOMapAnywhere | kIOMapWriteCombineCache);
        memory->release();
    }
    if (!fScanoutMap) {
        IOLog("DroidVMDisplay: cannot map the framebuffer at %#lx\n", fVideo.v_baseAddr);
        return false;
    }
    fScanout = reinterpret_cast<uint8_t *>(fScanoutMap->getVirtualAddress());
    IOLog("DroidVMDisplay: scanout %#lx %lux%lu row %lu\n", fVideo.v_baseAddr, fVideo.v_width, fVideo.v_height, fVideo.v_rowBytes);
    // Clear to a solid colour until the first frame: the boot console's text goes away and the screen shows that this mapping reaches it.
    for (unsigned long y = 0; y < fVideo.v_height; y++) {
        auto *row = reinterpret_cast<volatile uint32_t *>(fScanout + y * fVideo.v_rowBytes);
        for (unsigned long x = 0; x < fVideo.v_width; x++)
            row[x] = 0xff203050;
    }
    if (!IOMobileFramebufferLegacy::start(provider)) {
        IOLog("DroidVMDisplay: IOMobileFramebufferLegacy::start failed\n");
        OSSafeReleaseNULL(fScanoutMap);
        return false;
    }
    virt_set_external_method_hook(convertSwapRecord);
    IOLog("DroidVMDisplay: started, display %ux%u\n", display_width(), display_height());
    return true;
}

void DroidVMDisplay::stop(IOService *provider)
{
    virt_set_external_method_hook(nullptr);
    IOMobileFramebufferLegacy::stop(provider);
    if (fHalfToByte)
        IOFree(fHalfToByte, 65536);
    if (fRow)
        IOFree(fRow, fRowBytes);
    fHalfToByte = nullptr;
    fRow = nullptr;
    OSSafeReleaseNULL(fScanoutMap);
    fScanout = nullptr;
}

// Called by IOMobileFramebufferLegacy::start before it creates the default surface and registers the service (it tests bit 0).
bool DroidVMDisplay::start_hardware()
{
    if (!createDisplayAttributes())
        return false;
    fVBL = IOTimerEventSource::timerEventSource(this, vblFired);
    if (!fVBL || getWorkLoop()->addEventSource(fVBL) != kIOReturnSuccess) {   // the work loop of the family's command gate
        IOLog("DroidVMDisplay: Failed to create VBL timer\n");
        OSSafeReleaseNULL(fVBL);
        return false;
    }
    fVBL->enable();
    at<uint8_t>(this, kHardwareStarted) = 1;
    PMinit();
    getPlatform()->PMRegisterDevice(getProvider(), this);   // the provider is no power-managed AppleARMIODevice here
    registerPowerDriver(this, gPowerStates, 2);
    // The panel is always there: report it plugged in (the digital out state IOMobileFramebufferGetDigitalOutState answers), as
    // AppleParavirtDisplay does when the host reports its display. Unplugged (0), WindowServer kept this display disabled and composited
    // a virtual one as the main display ("get_hotplug_state - not active").
    hotPlug_notify(1);
    IOLog("DroidVMDisplay: hardware started\n");
    return true;
}

IOReturn DroidVMDisplay::stop_hardware_gated()
{
    if (fVBL) {
        fVBL->cancelTimeout();
        getWorkLoop()->removeEventSource(fVBL);
        OSSafeReleaseNULL(fVBL);
    }
    return kIOReturnSuccess;
}

void DroidVMDisplay::vblFired(OSObject *owner, IOTimerEventSource *)
{
    static_cast<DroidVMDisplay *>(owner)->swap_begin_gated();
}

// AppleParavirtDisplay::clean_queue_gated: whether a queued swap is ready to be programmed.
bool DroidVMDisplay::clean_queue_gated()
{
    if (at<IOMFBSwapIORequest *>(this, kCurrentSwap) || !at<IOMFBSwapIORequest *>(this, kSwapQueueFirst))
        return false;
    if (dropObsoleteSwaps_gated())
        return false;
    dropNoOpSwaps_gated();
    dropAbortedSwaps_gated(false);
    dropDummySwaps_gated();
    return at<IOMFBSwapIORequest *>(this, kSwapQueueFirst) != nullptr;
}

// AppleParavirtDisplay::swap_begin_gated: the family calls it when a swap is submitted, the VBL timer every 16 ms.
IOReturn DroidVMDisplay::swap_begin_gated()
{
    if (!fVBL)
        return kIOReturnNotReady;
    fVBL->cancelTimeout();
    while (clean_queue_gated()) {
        IOMFBSwapIORequest *swap = at<IOMFBSwapIORequest *>(this, kSwapQueueFirst);
        at<IOMFBSwapIORequest *>(this, kCurrentSwap) = swap;
        iomfbUpdateSwapInfoState(this, swap, 2);
        IOMFBSwapIORequest *next = at<IOMFBSwapIORequest *>(swap, kSwapNext);
        IOMFBSwapIORequest **prev = at<IOMFBSwapIORequest **>(swap, kSwapPrev);
        if (next)
            at<IOMFBSwapIORequest **>(next, kSwapPrev) = prev;
        else
            at<IOMFBSwapIORequest **>(this, kSwapQueueLast) = prev;
        *prev = next;
        if ((at<uint32_t>(swap, kSwapDropReasons) & ~8u) == 0) {
            program_hardware_gated();
        } else {
            dropSwap_gated(swap, false);
            fDropped++;
        }
    }
    if (at<IOMFBSwapIORequest *>(this, kSwapQueueFirst))
        fStalled++;
    if (++fTicks % 625 == 0 && fSubmitted + fFrames + fDropped + fStalled != fReported) {   // about every 10 s while swaps arrive
        fReported = fSubmitted + fFrames + fDropped + fStalled;
        IOLog("DroidVMDisplay: %llu swaps submitted, %llu shown, %llu dropped, %llu ticks stalled (current %p), last frame %llu lit centre %#llx\n",
              fSubmitted, fFrames, fDropped, fStalled, at<IOMFBSwapIORequest *>(this, kCurrentSwap), fLastLit, fLastCenter);
    }
    return fVBL->setTimeoutMS(16);
}

// Diagnostic: CoreAnimation asks swap_wait, without blocking, whether its last swaps are done before it composes the next frame
// (IOMFBDisplay::can_update_); after three swaps WindowServer found the display unready for good.
IOReturn DroidVMDisplay::swap_wait(IOMobileFramebufferUserClient *client, unsigned int swapID, unsigned int options, unsigned int timeout)
{
    IOReturn result = IOMobileFramebufferLegacy::swap_wait(client, swapID, options, timeout);
    if (result != kIOReturnSuccess && (++fWaitFailures <= 20 || fWaitFailures % 1000 == 0))
        IOLog("DroidVMDisplay: swap_wait(%u, 0x%x, %u) = 0x%x (%llu failures): +6412 %u power %u/%u +6436 %u +140 0x%x current %p queue %p\n",
              swapID, options, timeout, result, fWaitFailures, at<uint32_t>(this, 6412), at<uint32_t>(this, kSystemPowerState),
              at<uint32_t>(this, kAPIPowerState), at<uint32_t>(this, kHardwarePowered), at<uint8_t>(this, kHardwareStarted),
              at<IOMFBSwapIORequest *>(this, kCurrentSwap), at<IOMFBSwapIORequest *>(this, kSwapQueueFirst));
    return result;
}

// AppleParavirtDisplay::do_power_state_change_gated: the display is on while both the system and WindowServer (setAPIPowerState)
// want it on; each change goes to WindowServer as a power state notification, which CoreAnimation waits for before it swaps.
IOReturn DroidVMDisplay::do_power_state_change_gated()
{
    bool on = at<uint32_t>(this, kSystemPowerState) && at<uint32_t>(this, kAPIPowerState);
    if (on == fDisplayOn)
        return kIOReturnSuccess;
    fDisplayOn = on;
    at<uint32_t>(this, kHardwarePowered) = on;
    IOLog("DroidVMDisplay: display %s\n", on ? "on" : "off");
    powerstate_notify(true, on);
    return kIOReturnSuccess;
}

// AppleParavirtDisplay::program_hardware_gated (its slot 473): show the swap, then complete it. There is no cursor plane (no
// "CursorPlane" property), so WindowServer draws the cursor into the main surface.
void DroidVMDisplay::program_hardware_gated()
{
    IOMFBSwapIORequest *swap = at<IOMFBSwapIORequest *>(this, kCurrentSwap);
    // Layer i's surface follows the main one (AppleParavirtDisplay: bit 1, the cursor, at main + 8). After the login transition
    // WindowServer swaps a 128x128 BGRA cursor where the main surface is: the screen is the largest surface of the swap, smaller
    // ones are not drawn over it (the screen keeps its last full frame).
    uint8_t layers = at<uint8_t>(swap, kSwapLayers);
    IOSurface *surface = nullptr;
    uint64_t area = 0, shape = layers;
    for (unsigned layer = 0; layer < kSwapLayerCount; layer++) {
        IOSurface *candidate = (layers >> layer & 1) ? at<IOSurface *>(swap, kSwapMainSurface + 8 * layer) : nullptr;
        if (!candidate)
            continue;
        uint64_t width = ioSurfaceWidth(candidate), height = ioSurfaceHeight(candidate);
        shape = shape * 31 + width * 65537 + height;
        if (width * height > area) {
            area = width * height;
            surface = candidate;
        }
    }
    if (shape != fLayerShape) {   // bring-up: each new combination of layers
        fLayerShape = shape;
        IOLog("DroidVMDisplay: swap layers %#x:", layers);
        for (unsigned layer = 0; layer < kSwapLayerCount; layer++) {
            IOSurface *candidate = (layers >> layer & 1) ? at<IOSurface *>(swap, kSwapMainSurface + 8 * layer) : nullptr;
            if (candidate)
                IOLog(" %u: %llux%llu %#x", layer, ioSurfaceWidth(candidate), ioSurfaceHeight(candidate), ioSurfacePixelFormat(candidate));
        }
        IOLog("\n");
    }
    if (surface && area * 4 >= static_cast<uint64_t>(fVideo.v_width) * fVideo.v_height)   // a quarter of the screen at least
        copySurface(surface);
    swap_complete_gated();
}

static constexpr uint32_t kFormatBGRA = 'BGRA', kFormatRGhA = 'RGhA';   // 8-bit BGRA, 16-bit half-float RGBA

// A half float's value in [0, 1] as a byte, in integer arithmetic (no floating point in the kernel).
static uint8_t halfToByte(uint16_t half)
{
    unsigned exponent = (half >> 10) & 31, mantissa = half & 1023;
    if (half & 0x8000 || (exponent == 31 && mantissa))   // negative or NaN
        return 0;
    if (exponent >= 15)                                  // 1.0 and above
        return 255;
    uint32_t scaled = (exponent ? 1024 + mantissa : mantissa) * 255;   // value * 255 = scaled * 2^(exponent - 25), subnormals 2^-24
    unsigned shift = exponent ? 25 - exponent : 24;
    return static_cast<uint8_t>((scaled + (1u << (shift - 1))) >> shift);
}

void DroidVMDisplay::copySurface(IOSurface *surface)
{
    uint64_t width = ioSurfaceWidth(surface), height = ioSurfaceHeight(surface), rowBytes = ioSurfaceBytesPerRow(surface);
    uint64_t base = ioSurfaceBaseOffset(surface);
    uint32_t format = ioSurfacePixelFormat(surface);
    IOMemoryDescriptor *memory = ioSurfaceMemory(surface);
    if (!fFrames)   // WindowServer's first frame: the verbose boot console stops drawing over the framebuffer (it goes to serial)
        PE_initialize_console(nullptr, kPEDisableScreen);
    if (format != fSurfaceFormat || !fFrames) {
        IOLog("DroidVMDisplay: surface %llux%llu row %llu offset %llu format %#x memory %p\n", width, height, rowBytes, base, format, memory);
        fSurfaceFormat = format;
    }
    fFrames++;
    uint64_t pixelBytes = format == kFormatRGhA ? 8 : 4;
    if (!memory || !fScanout || rowBytes < width * pixelBytes || (format != kFormatBGRA && format != kFormatRGhA))
        return;
    uint64_t copyWidth = width < fVideo.v_width ? width : fVideo.v_width;
    uint64_t copyHeight = height < fVideo.v_height ? height : fVideo.v_height;
    if (format == kFormatRGhA && !fHalfToByte) {
        fHalfToByte = static_cast<uint8_t *>(IOMalloc(65536));
        fRowBytes = fVideo.v_width * 8;
        fRow = static_cast<uint16_t *>(IOMalloc(fRowBytes));
        if (!fHalfToByte || !fRow)
            return;
        for (uint32_t half = 0; half < 65536; half++)
            fHalfToByte[half] = halfToByte(static_cast<uint16_t>(half));
    }
    if (memory->prepare() != kIOReturnSuccess)
        return;
    uint64_t lit = 0, raw = 0, center = 0;
    bool sample = true;   // bring-up: the first frames and every 50th are logged, the last one goes into the periodic report
    for (uint64_t y = 0; y < copyHeight; y++) {
        uint8_t *line = fScanout + y * fVideo.v_rowBytes;
        if (format == kFormatBGRA) {
            memory->readBytes(base + y * rowBytes, line, copyWidth * 4);
            continue;
        }
        memory->readBytes(base + y * rowBytes, fRow, copyWidth * 8);
        auto *pixels = reinterpret_cast<uint32_t *>(line);
        for (uint64_t x = 0; x < copyWidth; x++) {
            const uint16_t *rgba = fRow + x * 4;
            pixels[x] = 0xff000000u | fHalfToByte[rgba[0]] << 16 | fHalfToByte[rgba[1]] << 8 | fHalfToByte[rgba[2]];
            if (sample) {
                lit += (pixels[x] & 0xffffff) != 0;
                raw += (rgba[0] | rgba[1] | rgba[2] | rgba[3]) != 0;
                if (y == copyHeight / 2 && x == copyWidth / 2)
                    center = static_cast<uint64_t>(rgba[3]) << 48 | static_cast<uint64_t>(rgba[2]) << 32 | rgba[1] << 16 | rgba[0];
            }
        }
    }
    memory->complete();
    fLastLit = lit;
    fLastCenter = center;
    if (format == kFormatRGhA && (fFrames <= 8 || fFrames % 50 == 0))
        IOLog("DroidVMDisplay: frame %llu: %llu pixels lit, %llu nonzero, centre %#llx\n", fFrames, lit, raw, center);
}

static bool appendNumber(OSDictionary *dictionary, const char *key, uint64_t value, unsigned bits = 32)
{
    OSNumber *number = OSNumber::withNumber(value, bits);
    bool done = number && dictionary->setObject(key, number);
    OSSafeReleaseNULL(number);
    return done;
}

static bool appendString(OSDictionary *dictionary, const char *key, const char *value)
{
    OSString *string = OSString::withCString(value);
    bool done = string && dictionary->setObject(key, string);
    OSSafeReleaseNULL(string);
    return done;
}

static bool appendDictionary(OSDictionary *dictionary, const char *key, OSDictionary *value)
{
    bool done = value && dictionary->setObject(key, value);
    OSSafeReleaseNULL(value);
    return done;
}

static OSDictionary *point(uint32_t x, uint32_t y)
{
    OSDictionary *dictionary = OSDictionary::withCapacity(3);
    if (dictionary && !(appendNumber(dictionary, "X", x) && appendNumber(dictionary, "Y", y)))
        OSSafeReleaseNULL(dictionary);
    return dictionary;
}

// AppleParavirtDisplay::createDisplayAttributes, with the display of the boot framebuffer: one timing (the GOP mode) with one
// 8-bit SDR color element. Chromaticities are sRGB's (16.16 fixed point, as the panel's EDID would give them).
bool DroidVMDisplay::createDisplayAttributes()
{
    uint32_t width = static_cast<uint32_t>(fVideo.v_width), height = static_cast<uint32_t>(fVideo.v_height);
    bool done = false;
    OSDictionary *attributes = OSDictionary::withCapacity(16), *product = OSDictionary::withCapacity(8);
    OSDictionary *chromaticity = OSDictionary::withCapacity(3), *whitePoint = point(20493, 21561);
    OSDictionary *transport = OSDictionary::withCapacity(2), *sourceLimits = OSDictionary::withCapacity(5);
    OSDictionary *scalingLimits = OSDictionary::withCapacity(2);
    OSArray *colors = OSArray::withCapacity(1), *timings = OSArray::withCapacity(1), *timingColors = OSArray::withCapacity(1);
    OSObject *color = ioavColorWithCapabilities(2, 8, 0, 0, 0, 16, false, nullptr, nullptr, nullptr, nullptr);
    // CVT reduced blanking as IOAVFamily's sCVTTimingData has it (1280x800@60: 1440x823, 71 MHz). Sync rates are 16.16 fixed point
    // (IOAVVideoTimingGetSyncRateRounded); the table leaves the horizontal one 0.
    uint8_t timingData[80] = {};
    uint32_t hTotal = width + 160, vTotal = height + 23;
    at<uint32_t>(timingData, 4) = hTotal;
    at<uint32_t>(timingData, 8) = width;
    at<uint32_t>(timingData, 12) = 32;                   // horizontal sync width, back porch, front porch
    at<uint32_t>(timingData, 16) = 80;
    at<uint32_t>(timingData, 20) = 48;
    at<uint32_t>(timingData, 28) = 1;                    // horizontal sync polarity (positive)
    at<uint32_t>(timingData, 36) = vTotal;
    at<uint32_t>(timingData, 40) = height;
    at<uint32_t>(timingData, 44) = 6;                    // vertical sync width, back porch, front porch
    at<uint32_t>(timingData, 48) = 14;
    at<uint32_t>(timingData, 52) = 3;
    at<uint32_t>(timingData, 56) = kRefreshHz << 16;
    at<uint32_t>(timingData, 68) = hTotal * vTotal * kRefreshHz;   // pixel clock in Hz
    OSObject *timing = ioavTimingWithData(timingData, 2, 4);
    do {
        if (!attributes || !product || !chromaticity || !whitePoint || !transport || !sourceLimits || !scalingLimits || !colors ||
            !timings || !timingColors || !color || !timing)
            break;
        at<uint64_t>(color, kElementID) = kColorID;
        at<uint32_t>(color, kElementScore) = kColorID;
        at<uint64_t>(timing, kElementID) = kTimingID;
        at<uint32_t>(timing, kElementScore) = kTimingID;
        if (!colors->setObject(color) || !timingColors->setObject(color) || !timings->setObject(timing))
            break;
        ioavTimingSetColorElements(timing, timingColors);
        if (!(appendString(product, "ManufacturerID", "APP") && appendNumber(product, "ProductID", 0) &&
              appendNumber(product, "SerialNumber", 0) && appendString(product, "ProductName", "DroidVM Display") &&
              appendNumber(product, "WeekOfManufacture", 24) && appendNumber(product, "YearOfManufacture", 2021)))
            break;
        if (!(appendDictionary(chromaticity, "Red", point(41943, 21627)) && appendDictionary(chromaticity, "Green", point(19661, 39322)) &&
              appendDictionary(chromaticity, "Blue", point(9830, 3932))))
            break;
        if (!appendNumber(whitePoint, "Gamma", 144179))   // 2.2
            break;
        if (!(attributes->setObject("SupportsPQEOTF", kOSBooleanFalse) && attributes->setObject("ProductAttributes", product) &&
              attributes->setObject("Chromaticity", chromaticity) && attributes->setObject("DefaultColorSpaceIsSRGB", kOSBooleanFalse) &&
              attributes->setObject("DefaultWhitePoint", whitePoint) && attributes->setObject("SupportsStandby", kOSBooleanTrue) &&
              appendNumber(attributes, "ContinuousFrequencySupport", 3) &&
              appendNumber(attributes, "MaxHorizontalImageSize", (kWidthMM + 5) / 10) &&
              appendNumber(attributes, "MaxVerticalImageSize", (kHeightMM + 5) / 10) &&
              appendNumber(attributes, "NativeFormatHorizontalPixels", width) && appendNumber(attributes, "NativeFormatVerticalPixels", height) &&
              appendNumber(attributes, "PreciseAspectRatio", (static_cast<uint64_t>(width) << 16) / height)))
            break;
        if (!(appendString(transport, "Upstream", "Other") && appendString(transport, "Downstream", "Other")))
            break;
        if (!(appendNumber(sourceLimits, "MaxSrcBufferWidth", 16384) && appendNumber(sourceLimits, "MaxSrcBufferHeight", 16384) &&
              appendNumber(sourceLimits, "MaxSrcRectWidth", 8192) && appendNumber(sourceLimits, "MaxSrcRectTotal", 0) &&
              appendNumber(sourceLimits, "IOMFBMaxCompressedSizeInBytes", 0)))
            break;
        if (!(appendNumber(scalingLimits, "RGBLayer_MinScaleFraction", 4) && appendNumber(scalingLimits, "RGBLayer_MaxScale", 4)))
            break;
        setProperty("IOMFBUUID", "44726F69-6456-4D00-0000-000000000001");
        setProperty("external", true);
        setProperty("primary", 0ULL, 32);   // AppleParavirtDisplay's display index
        done = setProperty("DisplayAttributes", attributes) && setProperty("Transport", transport) &&
            setProperty("ColorElements", colors) && setProperty("TimingElements", timings) &&
            setProperty("IOMFBMaxSrcPixels", sourceLimits) && setProperty("IOMFBScalingLimits", scalingLimits);
    } while (false);
    OSSafeReleaseNULL(attributes);
    OSSafeReleaseNULL(product);
    OSSafeReleaseNULL(chromaticity);
    OSSafeReleaseNULL(whitePoint);
    OSSafeReleaseNULL(transport);
    OSSafeReleaseNULL(sourceLimits);
    OSSafeReleaseNULL(scalingLimits);
    OSSafeReleaseNULL(colors);
    OSSafeReleaseNULL(timings);
    OSSafeReleaseNULL(timingColors);
    OSSafeReleaseNULL(color);
    OSSafeReleaseNULL(timing);
    if (!done || set_digital_out_mode(kColorID, kTimingID) != kIOReturnSuccess) {
        IOLog("DroidVMDisplay: createDisplayAttributes failed\n");
        return false;
    }
    return true;
}

// The mode of a color and a timing element (the IDs published above); AppleParavirtDisplay's block takes the timing's active size.
IOReturn DroidVMDisplay::set_digital_out_mode(unsigned int colorID, unsigned int timingID)
{
    if (colorID != kColorID || timingID != kTimingID)
        return kIOReturnBadArgument;
    at<uint32_t>(this, kDisplayWidth) = static_cast<uint32_t>(fVideo.v_width);
    at<uint32_t>(this, kDisplayHeight) = static_cast<uint32_t>(fVideo.v_height);
    setProperty("DisplayWidth", fVideo.v_width, 32);
    setProperty("DisplayHeight", fVideo.v_height, 32);
    setProperty("DPTimingModeId", timingID, 32);
    return kIOReturnSuccess;
}

// AppleParavirtDisplay: dots per inch from the physical width (IOMobileFramebufferLegacy's reads "dot-pitch" of the AppleARMIODevice).
IOReturn DroidVMDisplay::get_dot_pitch(unsigned int *pitch)
{
    *pitch = static_cast<unsigned int>(fVideo.v_width * 25.46 / kWidthMM + 0.5);
    return kIOReturnSuccess;
}

// AppleParavirtDisplay's hooks with nothing to do on a CPU-copied scanout: the swap and its layers need no mapping, there is no
// gamma or color hardware (the family's defaults are unsupported, AppleParavirtDisplay accepts them).
IOReturn DroidVMDisplay::verify_swap(IOMFBSwapIORequest *)   // AppleParavirtDisplay returns 1 (IOMobileFramebufferLegacy: 0)
{
    if (!fSubmitted++)
        IOLog("DroidVMDisplay: first swap submitted\n");
    return 1;
}
IOReturn DroidVMDisplay::swap_layer_map(IOMFBSwapIORequest *, unsigned int) {return kIOReturnSuccess;}
IOReturn DroidVMDisplay::surface_layer_map(IOMFB::AP::DisplayedData *, unsigned int, IOSurface *) {return kIOReturnSuccess;}
IOReturn DroidVMDisplay::surface_layer_unmap(IOMFB::AP::DisplayedData *, unsigned int) {return kIOReturnSuccess;}
IOReturn DroidVMDisplay::set_display_device(unsigned int) {return kIOReturnSuccess;}
IOReturn DroidVMDisplay::get_gamma_table(IOMFBGammaTable *) {return kIOReturnUnsupported;}
IOReturn DroidVMDisplay::set_gamma_table(IOMFBGammaTable *) {return kIOReturnSuccess;}
IOReturn DroidVMDisplay::set_color_remap_mode(DisplayColorRemapMode mode)
{
    fColorRemapMode = mode;
    return kIOReturnSuccess;
}
IOReturn DroidVMDisplay::get_color_remap_mode(DisplayColorRemapMode *mode) const
{
    *mode = fColorRemapMode;
    return kIOReturnSuccess;
}
IOReturn DroidVMDisplay::swap_set_color_matrix(IOMFBColorFixedMatrix *, IOMFBColorMatrixFunction, unsigned int) {return kIOReturnSuccess;}

// The slots IOMobileFramebufferLegacy leaves pure, as AppleParavirtDisplay implements them.
IOReturn DroidVMDisplay::set_notify_tag_mask_gated(IOMFB_NotificationType type, IOMFBNotifyRequest *request, unsigned int mask)
{
    if (type != 3)
        return kIOReturnBadArgument;
    at<uint32_t>(request, 120) = mask;
    return kIOReturnSuccess;
}
IOReturn DroidVMDisplay::supported_frame_info(unsigned int, unsigned int *, char (*)[64], unsigned int *) {return kIOReturnUnsupported;}
IOReturn DroidVMDisplay::factory_portal(void *, task *) {return kIOReturnUnsupported;}
IOReturn DroidVMDisplay::executeFactoryConfigurations_gated() {return kIOReturnUnsupported;}
IOReturn DroidVMDisplay::set_frame_info_notification_state_gated(IOMFBNotifyRequest *, bool) {return kIOReturnSuccess;}

// AppleParavirtDisplay::notify_swap_done_gated: the family calls it as the current swap completes; the swap info goes to the
// clients (swap_info_notify_dispatch_gated, which calls do_swap_info_notify_gated per request) unless notifications are held.
IOReturn DroidVMDisplay::notify_swap_done_gated(unsigned int swapID, ::SwapInfoBlob *, unsigned int *, unsigned int)
{
    IOMFBSwapIORequest *swap = at<IOMFBSwapIORequest *>(this, kCurrentSwap);
    if (at<uint32_t>(swap, kSwapDropReasons))
        return kIOReturnUnsupported;
    SwapInfo *info = &fSwapInfo[fSwapInfoWrite];
    *info = {swapID, {at<uint64_t>(this, kSwapInfoTime), 0, at<uint64_t>(swap, kSwapInfoA), at<uint32_t>(swap, kSwapInfoB), 0}};
    if (at<uint16_t>(this, kSwapInfoHeld)) {
        fSwapInfoWrite = (fSwapInfoWrite + 1) % kSwapInfoRing;
        return kIOReturnSuccess;
    }
    for (; fSwapInfoRead != fSwapInfoWrite; fSwapInfoRead = (fSwapInfoRead + 1) % kSwapInfoRing)
        iomfbSwapInfoDispatch(this, &fSwapInfo[fSwapInfoRead]);
    iomfbSwapInfoDispatch(this, info);
    return kIOReturnSuccess;
}

// AppleParavirtDisplay::do_swap_info_notify_gated: the request's async result is the mask, the swap ID and the words it asks for.
IOReturn DroidVMDisplay::do_swap_info_notify_gated(IOMFBNotifyRequest *request, const SwapInfoBlob *blob)
{
    const SwapInfo *info = reinterpret_cast<const SwapInfo *>(blob);
    uint32_t mask = at<uint32_t>(request, kNotifyMask);
    io_user_reference_t args[12] = {mask, info->swapID};
    unsigned count = 2;
    for (unsigned word = 0; word < 5; word++) {
        if (!(mask >> word & 1))
            continue;
        uint64_t value = word == 1 ? info->words[0] - at<uint64_t>(request, kNotifyLastTime) : info->words[word];
        unsigned need = mask >> 31 ? 2 : 1;
        if (count + need > 12) {
            IOLog("IOMFB Packer put: ran out of space\n");
            continue;
        }
        if (need == 2) {
            args[count++] = static_cast<uint32_t>(value);
            args[count++] = value >> 32;
        } else {
            args[count++] = value;
        }
    }
    at<uint64_t>(request, kNotifyLastTime) = info->words[0];
    return userClientSendAsyncResult(&at<io_user_reference_t>(request, kNotifyAsyncReference), kIOReturnSuccess, args, count,
                                     kIOUserNotifyOptionCanDrop);
}
IOReturn DroidVMDisplay::notify_crc_ready_gated(unsigned int) {return kIOReturnSuccess;}
bool DroidVMDisplay::are_timings_enabled() const {return false;}
