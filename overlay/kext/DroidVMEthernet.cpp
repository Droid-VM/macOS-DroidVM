// SPDX-License-Identifier: BSD-2-Clause-Patent
// DroidVMEthernet: en0, the guest's network. With crosvm's virtio-net on the virtio-mmio transport (--net through
// --virtio-mmio-net, the app's network bridged to the phone's br-wifi), which the ADT publishes as /arm-io/net (compatible
// "droidvm,net"), it drives that device; the transport follows Droid-VM/UniXNU-droidvm package/DroidVMVirtioNet.c (wip/hackintosh):
// VIRTIO_F_VERSION_1 + VIRTIO_NET_F_MAC only, so every packet carries a 12-byte virtio_net_hdr in one descriptor, split queues
// without interrupts, a polling thread. Without the device (or with droidvm-net=0) it is the controller with no hardware behind it
// it was before: a fixed locally administered MAC, link up, every packet dropped.
// Either way en0 exists: IOTimeSyncClockManager derives the TimeSync clock identifier from a network interface's MAC; without one it
// never registers, clocksyncd waits for it and WindowServer (QuartzCore's TimeSync clock) waits on clocksyncd.
// Headers: IONetworkingFamily-188 (sources/IONetworkingFamily, as IOKit/network); NativeVirtioPci.h for the MMIO accessors.
#include <IOKit/IOBufferMemoryDescriptor.h>
#include <IOKit/IODeviceTreeSupport.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOLocks.h>
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-anon-enum-enum-conversion"   // the family's headers mix anonymous enums
#define __PRIVATE_SPI__   // the shipped family uses IONetworkController's reserved slots 2-5 (outputStart ... networkInterfaceNotification)
#include <IOKit/network/IOEthernetController.h>
#include <IOKit/network/IOEthernetInterface.h>
#include <IOKit/network/IONetworkMedium.h>
#include <IOKit/network/IOOutputQueue.h>
#pragma clang diagnostic pop
#include <kern/thread.h>
#include <net/ethernet.h>
#include "NativeVirtioPci.h"

using virtio_pci::mmioRead;
using virtio_pci::mmioWrite;

namespace {

// VirtIO 1.2 4.2.2, the MMIO device registers
enum : unsigned {
  regMagic = 0x00, regVersion = 0x04, regDeviceId = 0x08, regDeviceFeatures = 0x10, regDeviceFeaturesSel = 0x14,
  regDriverFeatures = 0x20, regDriverFeaturesSel = 0x24, regQueueSel = 0x30, regQueueNumMax = 0x34, regQueueNum = 0x38,
  regQueueReady = 0x44, regQueueNotify = 0x50, regInterruptStatus = 0x60, regInterruptAck = 0x64, regStatus = 0x70,
  regQueueDesc = 0x80, regQueueDriver = 0x90, regQueueDevice = 0xa0, regConfig = 0x100,
};
enum : uint32_t { statusAcknowledge = 1, statusDriver = 2, statusDriverOk = 4, statusFeaturesOk = 8, statusFailed = 0x80 };
enum : unsigned { netFeatureMac = 5, descWrite = 2, availNoInterrupt = 1, queueRx = 0, queueTx = 1 };
constexpr unsigned maxQueue = 256;          // descriptors per queue, at most (crosvm's QueueNumMax is the other bound)
constexpr unsigned hdrBytes = 12;           // sizeof(struct virtio_net_hdr_v1) once VIRTIO_F_VERSION_1 is negotiated
constexpr unsigned frameBytes = 1514;       // a full ethernet frame without the FCS
constexpr unsigned bufferBytes = 2048;      // hdrBytes + frameBytes, rounded up: a buffer never crosses a page
constexpr unsigned ringBytes = 3 * 4096;    // a queue: descriptors at 0, the driver ring at 4096, the device ring at 8192
constexpr unsigned fastPollMs = 1, idlePollMs = 10, fastPollTicks = 1000;   // 1 ms polls for a second after any traffic
constexpr unsigned maxMulticast = 32;
constexpr UInt64 linkSpeed = 1000 * 1000000ULL;

struct Desc { uint64_t address; uint32_t length; uint16_t flags, next; };
static_assert(sizeof(Desc) == 16, "VirtIO wire layout");

inline void dmaBarrier() { __asm__ volatile("dmb osh" ::: "memory"); }

// The ring memory must be physically contiguous for the device; the frame buffers each live within one page.
IOBufferMemoryDescriptor *contiguous(unsigned bytes, uint64_t *physical)
{
  IOBufferMemoryDescriptor *memory = IOBufferMemoryDescriptor::inTaskWithOptions(kernel_task,
    static_cast<IOOptionBits>(kIODirectionInOut) | static_cast<IOOptionBits>(kIOMemoryPhysicallyContiguous), bytes, 4096);
  IOByteCount length = 0;
  *physical = memory ? memory->getPhysicalSegment(0, &length) : 0;
  if (!*physical || length < bytes) { OSSafeReleaseNULL(memory); return nullptr; }
  bzero(memory->getBytesNoCopy(), bytes);
  return memory;
}

} // namespace

class DroidVMEthernet : public IOEthernetController {
    OSDeclareDefaultStructors(DroidVMEthernet)

    IOEthernetInterface *fInterface = nullptr;
    IOEthernetAddress fAddress = {{0x02, 0x44, 0x56, 0x4d, 0x00, 0x01}};   // locally administered, "DVM" (no device, or no MAC from it)
    // The device, when there is one
    IOMemoryMap *fRegisters = nullptr;
    IOBufferMemoryDescriptor *fMemory = nullptr;   // the rx queue, the tx queue, the rx buffers, the tx buffers
    uint8_t *fBase = nullptr;
    uint64_t fPhysical = 0;
    unsigned fSize = 0;
    uint16_t fRxUsed = 0, fTxHead = 0;
    IOLock *fTxLock = nullptr;
    bool fUp = false;
    volatile bool fEnabled = false, fActive = false, fPromiscuous = false, fMulticast = false;
    IOEthernetAddress fMulticastList[maxMulticast];
    volatile UInt32 fMulticastCount = 0;           // > maxMulticast: every multicast frame passes
    UInt64 fRxPackets = 0, fTxPackets = 0, fRxDrops = 0, fTxDrops = 0;

    uintptr_t registers() const { return static_cast<uintptr_t>(fRegisters->getVirtualAddress()); }
    uint32_t read32(unsigned offset) const { return mmioRead<uint32_t>(registers() + offset); }
    void write32(unsigned offset, uint32_t value) const { mmioWrite<uint32_t>(registers() + offset, value); }
    void write64(unsigned offset, uint64_t value) const { write32(offset, static_cast<uint32_t>(value)); write32(offset + 4, static_cast<uint32_t>(value >> 32)); }
    uint8_t *ring(unsigned queue) const { return fBase + queue * ringBytes; }
    uint64_t ringPhysical(unsigned queue) const { return fPhysical + queue * ringBytes; }
    unsigned bufferOffset(unsigned queue, unsigned slot) const { return 2 * ringBytes + (queue * fSize + slot) * bufferBytes; }

    const char *attachDevice();
    bool resetDevice();
    bool setUpQueue(unsigned queue);
    bool accepts(const uint8_t *destination);
    void pollReceive();
    static void pollThread(void *self, wait_result_t);

public:
    bool start(IOService *provider) override;
    void stop(IOService *provider) override;
    void free() override;
    IOReturn getHardwareAddress(IOEthernetAddress *address) override;
    IOReturn enable(IONetworkInterface *interface) override;
    IOReturn disable(IONetworkInterface *interface) override;
    // IOBSD is up (our IOResourceMatch), and the family's wait for it from start() needs IOResources matched, which it is
    // not while IOResources' own matching starts us: a deadlock whenever IOBSD is published inside IOResources' first match
    UInt32 getFeatures() const override { return kIONetworkFeatureNoBSDWait; }
    UInt32 outputPacket(mbuf_t packet, void *param) override;
    IOReturn setPromiscuousMode(bool active) override { fPromiscuous = active; return kIOReturnSuccess; }
    IOReturn setMulticastMode(bool active) override { fMulticast = active; return kIOReturnSuccess; }
    IOReturn setMulticastList(IOEthernetAddress *addresses, UInt32 count) override;
};

OSDefineMetaClassAndStructors(DroidVMEthernet, IOEthernetController)

bool DroidVMEthernet::resetDevice()
{
    write32(regStatus, 0);
    for (unsigned waited = 0; read32(regStatus); ++waited) {
        if (waited > 1000)
            return false;
        IODelay(1);
    }
    return true;
}

bool DroidVMEthernet::setUpQueue(unsigned queue)
{
    write32(regQueueSel, queue);
    if (read32(regQueueReady))
        return false;
    *reinterpret_cast<volatile uint16_t *>(ring(queue) + 4096) = availNoInterrupt;   // this driver polls
    dmaBarrier();
    write32(regQueueNum, fSize);
    write64(regQueueDesc, ringPhysical(queue));
    write64(regQueueDriver, ringPhysical(queue) + 4096);
    write64(regQueueDevice, ringPhysical(queue) + 8192);
    write32(regQueueReady, 1);
    return true;
}

// Finds /arm-io/net, maps it and brings the device up (negotiation, both queues, every receive buffer posted). nullptr, or why not.
const char *DroidVMEthernet::attachDevice()
{
    uint32_t enabled = 1;
    PE_parse_boot_argn("droidvm-net", &enabled, sizeof(enabled));
    if (!enabled)
        return "off (droidvm-net=0)";
    IORegistryEntry *entry = IORegistryEntry::fromPath("/arm-io/net", gIODTPlane);
    IOService *nub = OSDynamicCast(IOService, entry);
    if (!nub) {
        OSSafeReleaseNULL(entry);
        return "no /arm-io/net";
    }
    fRegisters = nub->mapDeviceMemoryWithIndex(0, kIOMapAnywhere | kIOMapInhibitCache);
    entry->release();
    if (!fRegisters || fRegisters->getLength() < regConfig + 8)
        return "cannot map /arm-io/net";
    if (read32(regMagic) != 0x74726976 || read32(regVersion) != 2 || read32(regDeviceId) != 1)
        return "no virtio-net at /arm-io/net";

    if (!resetDevice())
        return "reset";
    write32(regStatus, statusAcknowledge);
    write32(regStatus, statusAcknowledge | statusDriver);
    write32(regDeviceFeaturesSel, 0);
    uint32_t low = read32(regDeviceFeatures);
    write32(regDeviceFeaturesSel, 1);
    if (!(read32(regDeviceFeatures) & 1))
        return "no VIRTIO_F_VERSION_1";
    bool mac = (low >> netFeatureMac) & 1;
    write32(regDriverFeaturesSel, 0);
    write32(regDriverFeatures, mac ? 1u << netFeatureMac : 0);
    write32(regDriverFeaturesSel, 1);
    write32(regDriverFeatures, 1);   // VIRTIO_F_VERSION_1 in the high word
    write32(regStatus, statusAcknowledge | statusDriver | statusFeaturesOk);
    if (!(read32(regStatus) & statusFeaturesOk))
        return "features refused";
    if (mac)
        for (unsigned i = 0; i < kIOEthernetAddressSize; ++i)
            fAddress.bytes[i] = mmioRead<uint8_t>(registers() + regConfig + i);

    // One size for both queues: the largest power of two both take, up to maxQueue
    unsigned limit = maxQueue;
    for (unsigned queue = queueRx; queue <= queueTx; ++queue) {
        write32(regQueueSel, queue);
        uint32_t most = read32(regQueueNumMax);
        if (most < limit)
            limit = most;
    }
    for (fSize = 1; fSize * 2 <= limit; fSize *= 2) {
    }
    if (fSize < 16)
        return "queues too small";
    fMemory = contiguous(2 * ringBytes + 2 * fSize * bufferBytes, &fPhysical);
    if (!fMemory)
        return "no contiguous memory";
    fBase = static_cast<uint8_t *>(fMemory->getBytesNoCopy());
    if (!setUpQueue(queueRx) || !setUpQueue(queueTx))
        return "queue set-up";

    // Every receive buffer goes into the available ring before DRIVER_OK: crosvm takes the ring as the driver leaves it then.
    Desc *descriptors = reinterpret_cast<Desc *>(ring(queueRx));
    volatile uint16_t *available = reinterpret_cast<volatile uint16_t *>(ring(queueRx) + 4096);
    for (unsigned i = 0; i < fSize; ++i) {
        descriptors[i] = {fPhysical + bufferOffset(queueRx, i), bufferBytes, descWrite, 0};
        available[2 + i] = static_cast<uint16_t>(i);
    }
    dmaBarrier();
    available[1] = static_cast<uint16_t>(fSize);
    write32(regStatus, statusAcknowledge | statusDriver | statusFeaturesOk | statusDriverOk);
    if ((read32(regStatus) & (statusFailed | 0xf)) != 0xf)
        return "device not ready";
    dmaBarrier();
    write32(regQueueNotify, queueRx);
    fUp = true;
    return nullptr;
}

bool DroidVMEthernet::start(IOService *provider)
{
    if (!IOEthernetController::start(provider))
        return false;
    fTxLock = IOLockAlloc();
    if (!fTxLock)
        return false;
    const char *why = attachDevice();
    if (why) {
        if (fRegisters && fRegisters->getLength() >= regConfig + 8 && read32(regMagic) == 0x74726976)
            resetDevice();
        OSSafeReleaseNULL(fRegisters);
        OSSafeReleaseNULL(fMemory);
        fUp = false;
    }
    OSDictionary *media = OSDictionary::withCapacity(1);
    IONetworkMedium *medium = IONetworkMedium::medium(IOMediumType(kIOMediumEthernetAuto) | IOMediumType(kIOMediumOptionFullDuplex), linkSpeed);
    if (!media || !medium || !IONetworkMedium::addMedium(media, medium) || !publishMediumDictionary(media)) {
        OSSafeReleaseNULL(media);
        OSSafeReleaseNULL(medium);
        IOLog("DroidVMEthernet: cannot publish the medium\n");
        return false;
    }
    media->release();
    setSelectedMedium(medium);
    setLinkStatus(kIONetworkLinkValid | kIONetworkLinkActive, medium, linkSpeed);
    medium->release();
    if (!attachInterface(reinterpret_cast<IONetworkInterface **>(&fInterface), false)) {
        IOLog("DroidVMEthernet: cannot attach the interface\n");
        return false;
    }
    // IOTimeSyncClockManager takes the clock identifier from the built-in interfaces only (the interface copies IOBuiltin from the
    // controller's provider, IOResources here) and looks once, at its start: the KC gates IOTimeSyncRootService (the manager's
    // provider) on the resource published here, once the interface is matched. Earlier than IOBSD the interface cannot attach.
    fInterface->setProperty(kIOBuiltin, true);
    fInterface->registerService(kIOServiceSynchronous);
    publishResource("DroidVMEthernet");
    if (fUp) {
        thread_t thread;
        if (kernel_thread_start(pollThread, this, &thread) == KERN_SUCCESS)
            thread_deallocate(thread);
        else
            fUp = false;
    }
    const uint8_t *m = fAddress.bytes;
    if (fUp)
        IOLog("DroidVMEthernet: virtio-net at /arm-io/net, %u descriptors a queue, MAC %02x:%02x:%02x:%02x:%02x:%02x\n", fSize, m[0], m[1],
              m[2], m[3], m[4], m[5]);
    else
        IOLog("DroidVMEthernet: no network device (%s), en0 drops every packet\n", why ? why : "poll thread");
    return true;
}

void DroidVMEthernet::stop(IOService *provider)
{
    if (fInterface) {
        detachInterface(fInterface);
        OSSafeReleaseNULL(fInterface);
    }
    IOEthernetController::stop(provider);
}

void DroidVMEthernet::free()
{
    // The poll thread holds no reference: a started device is never let go of (the controller is never stopped)
    OSSafeReleaseNULL(fRegisters);
    OSSafeReleaseNULL(fMemory);
    if (fTxLock)
        IOLockFree(fTxLock);
    fTxLock = nullptr;
    IOEthernetController::free();
}

IOReturn DroidVMEthernet::getHardwareAddress(IOEthernetAddress *address)
{
    *address = fAddress;
    return kIOReturnSuccess;
}

IOReturn DroidVMEthernet::enable(IONetworkInterface *interface)
{
    fEnabled = true;
    return kIOReturnSuccess;
}

IOReturn DroidVMEthernet::disable(IONetworkInterface *interface)
{
    fEnabled = false;
    return kIOReturnSuccess;
}

IOReturn DroidVMEthernet::setMulticastList(IOEthernetAddress *addresses, UInt32 count)
{
    UInt32 kept = count < maxMulticast ? count : maxMulticast;
    fMulticastCount = 0;
    bcopy(addresses, fMulticastList, kept * sizeof(IOEthernetAddress));
    fMulticastCount = count;
    return kIOReturnSuccess;
}

// No output queue: the interface calls in from the stack's threads, so the transmit ring is taken under a lock. The frame is copied
// straight into its slot's buffer; a slot is free again once the device's used index has passed it.
UInt32 DroidVMEthernet::outputPacket(mbuf_t packet, void *param)
{
    size_t length = mbuf_pkthdr_len(packet);
    if (!fUp || !fEnabled || length == 0 || length > frameBytes) {
        if (fUp)
            ++fTxDrops;
        freePacket(packet);
        return kIOReturnOutputDropped;
    }
    IOLockLock(fTxLock);
    volatile uint16_t *used = reinterpret_cast<volatile uint16_t *>(ring(queueTx) + 8192);
    dmaBarrier();
    if (static_cast<uint16_t>(fTxHead - used[1]) >= fSize) {   // every slot still with the device
        IOLockUnlock(fTxLock);
        ++fTxDrops;
        freePacket(packet);
        return kIOReturnOutputDropped;
    }
    unsigned slot = fTxHead % fSize;
    uint8_t *buffer = fBase + bufferOffset(queueTx, slot);
    bzero(buffer, hdrBytes);
    if (mbuf_copydata(packet, 0, length, buffer + hdrBytes) != 0) {
        IOLockUnlock(fTxLock);
        ++fTxDrops;
        freePacket(packet);
        return kIOReturnOutputDropped;
    }
    reinterpret_cast<Desc *>(ring(queueTx))[slot] = {fPhysical + bufferOffset(queueTx, slot), static_cast<uint32_t>(hdrBytes + length), 0, 0};
    volatile uint16_t *available = reinterpret_cast<volatile uint16_t *>(ring(queueTx) + 4096);
    available[2 + slot] = static_cast<uint16_t>(slot);
    dmaBarrier();
    available[1] = ++fTxHead;
    dmaBarrier();
    write32(regQueueNotify, queueTx);
    IOLockUnlock(fTxLock);
    ++fTxPackets;
    fActive = true;
    freePacket(packet);
    return kIOReturnOutputSuccess;
}

// The device has no filter (no control queue): crosvm's tap hands over every frame the bridge carries, on a busy wifi network
// mostly multicast this guest has not joined. As a NIC's filter would: broadcast, our own unicast, and the multicast groups the
// stack joined (IPv6 neighbour discovery, mDNS), everything in promiscuous mode.
bool DroidVMEthernet::accepts(const uint8_t *destination)
{
    if (fPromiscuous)
        return true;
    if (!(destination[0] & 1))
        return !memcmp(destination, fAddress.bytes, kIOEthernetAddressSize);
    if ((destination[0] & destination[1] & destination[2] & destination[3] & destination[4] & destination[5]) == 0xff)
        return true;
    if (!fMulticast)
        return false;
    UInt32 count = fMulticastCount;
    if (count > maxMulticast)
        return true;
    for (UInt32 i = 0; i < count; ++i)
        if (!memcmp(destination, fMulticastList[i].bytes, kIOEthernetAddressSize))
            return true;
    return false;
}

// Takes the frames the device wrote, hands them to the interface, and gives each buffer back to the receive queue. One thread
// only, so the interface's inputPacket calls are serialized as the family requires.
void DroidVMEthernet::pollReceive()
{
    Desc *descriptors = reinterpret_cast<Desc *>(ring(queueRx));
    volatile uint16_t *available = reinterpret_cast<volatile uint16_t *>(ring(queueRx) + 4096);
    volatile uint16_t *used = reinterpret_cast<volatile uint16_t *>(ring(queueRx) + 8192);
    const volatile uint32_t *elements = reinterpret_cast<const volatile uint32_t *>(ring(queueRx) + 8196);
    uint16_t head = available[1];
    unsigned returned = 0;
    while (used[1] != fRxUsed) {
        dmaBarrier();
        uint32_t id = elements[(fRxUsed % fSize) * 2], written = elements[(fRxUsed % fSize) * 2 + 1];
        if (id < fSize) {
            const uint8_t *frame = fBase + bufferOffset(queueRx, id) + hdrBytes;
            unsigned length = written > hdrBytes ? written - hdrBytes : 0;
            mbuf_t packet = nullptr;
            if (fEnabled && fInterface && length >= ETHER_HDR_LEN && length <= frameBytes && accepts(frame) &&
                (packet = allocatePacket(length)) && mbuf_copyback(packet, 0, length, frame, MBUF_DONTWAIT) == 0) {
                fInterface->inputPacket(packet, length);
                ++fRxPackets;
            } else {
                if (packet)
                    freePacket(packet);
                ++fRxDrops;
            }
            descriptors[id] = {fPhysical + bufferOffset(queueRx, id), bufferBytes, descWrite, 0};
            available[2 + (head + returned) % fSize] = static_cast<uint16_t>(id);
            ++returned;
        }
        ++fRxUsed;
    }
    if (returned) {
        dmaBarrier();
        available[1] = static_cast<uint16_t>(head + returned);
        dmaBarrier();
        write32(regQueueNotify, queueRx);
        fActive = true;
        // An MMIO read is a trap to the hypervisor: only with traffic (the queues are NO_INTERRUPT; the device may still raise one)
        if (uint32_t pending = read32(regInterruptStatus) & 3)
            write32(regInterruptAck, pending);
    }
}

// The idle poll touches only guest RAM (the used ring); 1 ms polls for a second after traffic, 10 ms otherwise.
void DroidVMEthernet::pollThread(void *self, wait_result_t)
{
    DroidVMEthernet *ethernet = static_cast<DroidVMEthernet *>(self);
    for (unsigned quiet = fastPollTicks;;) {
        ethernet->pollReceive();
        if (ethernet->fActive) {
            ethernet->fActive = false;
            quiet = 0;
        } else if (quiet < fastPollTicks) {
            ++quiet;
        }
        IOSleep(quiet < fastPollTicks ? fastPollMs : idlePollMs);
    }
}
