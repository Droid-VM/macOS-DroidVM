// The board keeps System/Data and xART in one ISC container. APFS marks ISC
// containers OSInternal on probe/reconcile, hiding our main disk from
// DiskManagement. Preserve the visibility correction previously hosted by
// NativeRamBlock, independently of the disk transport.
#include <IOKit/IOService.h>
#include <IOKit/IOWorkLoop.h>
#include <IOKit/IOTimerEventSource.h>

class DroidVMAPFSVisibility : public IOService {
    OSDeclareDefaultStructors(DroidVMAPFSVisibility)
    IOWorkLoop *loop = nullptr;
    IOTimerEventSource *timer = nullptr;

    static void refresh(OSObject *owner, IOTimerEventSource *source)
    {
        auto *self = static_cast<DroidVMAPFSVisibility *>(owner);
        self->getProvider()->removeProperty("OSInternal");
        source->setTimeoutMS(2000);
    }
public:
    IOService *probe(IOService *provider, SInt32 *score) override
    {
        // Exclude containers of disk images and other transports.
        IOService *ancestor = provider;
        while (ancestor && !ancestor->metaCast("AppleVirtIOBlockStorageDevice"))
            ancestor = ancestor->getProvider();
        return ancestor ? IOService::probe(provider, score) : nullptr;
    }
    bool start(IOService *provider) override
    {
        if (!IOService::start(provider)) return false;
        loop = IOWorkLoop::workLoop();
        timer = IOTimerEventSource::timerEventSource(this, refresh);
        if (!loop || !timer || loop->addEventSource(timer) != kIOReturnSuccess) return false;
        provider->removeProperty("OSInternal");
        timer->setTimeoutMS(100);
        registerService();
        return true;
    }
    void stop(IOService *provider) override
    {
        if (timer) {
            timer->cancelTimeout();
            if (loop) loop->removeEventSource(timer);
        }
        IOService::stop(provider);
    }
    void free() override
    {
        OSSafeReleaseNULL(timer);
        OSSafeReleaseNULL(loop);
        IOService::free();
    }
};
OSDefineMetaClassAndStructors(DroidVMAPFSVisibility, IOService)
