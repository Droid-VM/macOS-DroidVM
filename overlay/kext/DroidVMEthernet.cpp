// SPDX-License-Identifier: BSD-2-Clause-Patent
// DroidVMEthernet: an Ethernet controller with no hardware behind it (en0, a fixed locally administered MAC, link up, every packet
// dropped). The VM has no network device, and IOTimeSyncClockManager derives the TimeSync clock identifier from a network
// interface's MAC: without one it never registers, clocksyncd waits for it and WindowServer (QuartzCore's TimeSync clock) waits on
// clocksyncd. Headers: IONetworkingFamily-188 (sources/IONetworkingFamily, as IOKit/network).
#include <IOKit/IOLib.h>
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-anon-enum-enum-conversion"   // the family's headers mix anonymous enums
#define __PRIVATE_SPI__   // the shipped family uses IONetworkController's reserved slots 2-5 (outputStart ... networkInterfaceNotification)
#include <IOKit/network/IOEthernetController.h>
#include <IOKit/network/IOEthernetInterface.h>
#include <IOKit/network/IONetworkMedium.h>
#include <IOKit/network/IOOutputQueue.h>
#pragma clang diagnostic pop

class DroidVMEthernet : public IOEthernetController {
    OSDeclareDefaultStructors(DroidVMEthernet)

    IOEthernetInterface *fInterface = nullptr;

public:
    bool start(IOService *provider) override;
    void stop(IOService *provider) override;
    IOReturn getHardwareAddress(IOEthernetAddress *address) override;
    IOReturn enable(IONetworkInterface *interface) override;
    IOReturn disable(IONetworkInterface *interface) override;
    UInt32 outputPacket(mbuf_t packet, void *param) override;
    IOReturn setPromiscuousMode(bool active) override { return kIOReturnSuccess; }
    IOReturn setMulticastMode(bool active) override { return kIOReturnSuccess; }
    IOReturn setMulticastList(IOEthernetAddress *addresses, UInt32 count) override { return kIOReturnSuccess; }
};

OSDefineMetaClassAndStructors(DroidVMEthernet, IOEthernetController)

bool DroidVMEthernet::start(IOService *provider)
{
    if (!IOEthernetController::start(provider))
        return false;
    OSDictionary *media = OSDictionary::withCapacity(1);
    IONetworkMedium *medium = IONetworkMedium::medium(IOMediumType(kIOMediumEthernetAuto) | IOMediumType(kIOMediumOptionFullDuplex), 1000 * 1000000ULL);
    if (!media || !medium || !IONetworkMedium::addMedium(media, medium) || !publishMediumDictionary(media)) {
        OSSafeReleaseNULL(media);
        OSSafeReleaseNULL(medium);
        IOLog("DroidVMEthernet: cannot publish the medium\n");
        return false;
    }
    media->release();
    setSelectedMedium(medium);
    setLinkStatus(kIONetworkLinkValid | kIONetworkLinkActive, medium, 1000 * 1000000ULL);
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
    IOLog("DroidVMEthernet: started\n");
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

IOReturn DroidVMEthernet::getHardwareAddress(IOEthernetAddress *address)
{
    static const UInt8 mac[kIOEthernetAddressSize] = {0x02, 0x44, 0x56, 0x4d, 0x00, 0x01};   // locally administered, "DVM"
    bcopy(mac, address->bytes, sizeof(mac));
    return kIOReturnSuccess;
}

IOReturn DroidVMEthernet::enable(IONetworkInterface *interface)
{
    return kIOReturnSuccess;
}

IOReturn DroidVMEthernet::disable(IONetworkInterface *interface)
{
    return kIOReturnSuccess;
}

UInt32 DroidVMEthernet::outputPacket(mbuf_t packet, void *param)
{
    freePacket(packet);
    return kIOReturnOutputSuccess;
}
