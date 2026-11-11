// SPDX-License-Identifier: BSD-2-Clause-Patent
// Stand-in for AppleARMPlatform, AppleIISController and AppleAudioClockLibs (scripts/kc-build.py "stands_in_for"): IOMobileGraphicsFamily and the kexts it
// needs (IOAVFamily, AppleM2ScalerCSCDriver, IODARTFamily) link against them, but they are Apple SoC drivers this platform does not
// have (ArmDTPlatform publishes the devices), and the source-built kernel's larger __TEXT covers AppleARMPlatform's in the
// collection (AppleAudioClockLibs' too). The kept kexts only look up optional platform functions and type-check providers, so the stand-in gives them
// what an absent function or a provider of another class gives: no function, and classes no object belongs to.
// Without MACOS_USB_PCI it stands in for IOUSBHostFamily too, which IOBluetoothFamily lists as a library without referring to any
// of its symbols; kept, it would bring AppleSMC, RTBuddy, AppleA7IOP and IOAccessoryManager, which need AppleARMPlatform's
// functions and 27's coprocessor logging. IOBluetoothFamily is kept for its IOBluetoothHCIController (on IOResources), which
// bluetoothd's MacUserClient waits for before it serves CoreBluetooth.
#include <IOKit/IOService.h>
#include <IOKit/IOPlatformExpert.h>
#include <libkern/c++/OSSymbol.h>

// The PCI USB host stack only type-checks AppleSMCFamily. This platform has no
// SMC provider; keeping its metaclass avoids loading the physical SMC/RTKit stack.
class AppleSMCFamily : public IOService {
    OSDeclareDefaultStructors(AppleSMCFamily)
};
OSDefineMetaClassAndStructors(AppleSMCFamily, IOService)

class AppleARMIODevice : public IOService {
    OSDeclareDefaultStructors(AppleARMIODevice)
};
OSDefineMetaClassAndStructors(AppleARMIODevice, IOService)

class AppleARMIISDevice : public IOService {
    OSDeclareDefaultStructors(AppleARMIISDevice)
};
OSDefineMetaClassAndStructors(AppleARMIISDevice, IOService)

class AppleARMFunction : public OSObject {
public:
    static AppleARMFunction *withProvider(IORegistryEntry *, const char *);
    static AppleARMFunction *withProvider(IORegistryEntry *, const OSSymbol *);
    static void registerFunctionParent(IOService *, IOService *);
};

AppleARMFunction *AppleARMFunction::withProvider(IORegistryEntry *, const char *) {return nullptr;}
AppleARMFunction *AppleARMFunction::withProvider(IORegistryEntry *, const OSSymbol *) {return nullptr;}
void AppleARMFunction::registerFunctionParent(IOService *, IOService *) {}

// IOAVFamily's audio clock domain for a pair of clock identifiers: there is no audio hardware, so no synchronous domain.
namespace AppleAudioClock {
struct Utility {
    static uint64_t getSynchronousClockDomain(uint64_t, uint64_t);
};
uint64_t Utility::getSynchronousClockDomain(uint64_t, uint64_t) {return 0;}
}

// AppleVirtualPlatform (kept for its PCIe bridge, docs/k27-vmapple-pcie-msi-plan.md) subclasses the arm-io bus and the
// platform expert as AppleVirtualPlatformIO and AppleVirtualPlatformARMPE. Their personalities (arm-io,vmapple1 and
// AppleVirtualPlatformARM) match nothing in our ADT, so no object of either is made: the parents only need their metaclasses,
// vtables and the members those subclasses' vtables name, and the members do what the base classes do.
class AppleARMFunction;
class AppleARMIO : public IOService {
    OSDeclareDefaultStructors(AppleARMIO)
public:
    static AppleARMIO *createDeviceWithProvider(AppleARMIO *, IORegistryEntry *);
    const char *deleteList();
    const char *excludeList();
    IOReturn getClockName(unsigned, unsigned *, unsigned);
    void publishBelow(IORegistryEntry *);
    bool isDMACoherent(IOService *, unsigned);
    void processDevice(IOService *);
    IOReturn getNubResources(IOService *);
    IOReturn resetPsdService(unsigned, char *, unsigned);
    IOReturn enablePsdService(unsigned, unsigned, char *, unsigned);
    IOReturn enableDeviceClock(unsigned, unsigned);
    IOReturn enableDevicePower(unsigned, unsigned, unsigned *);
    IOReturn getClockFrequency(const OSSymbol *, unsigned *, unsigned);
    IOReturn getClockFrequency(const char *, unsigned *, unsigned);
    IOReturn getClockFrequency(unsigned, unsigned *, unsigned);
    IOReturn getIODeviceClocks(unsigned *, bool, unsigned);
    IOReturn getPsdServiceState(unsigned, unsigned *, unsigned);
    void handlePlatformError(unsigned long);
    IOReturn enableDevicePinGroup(unsigned *, unsigned);
    void registerAltErrorHandler(AppleARMFunction *);
    bool compareNubName(const IOService *, OSString *, OSString **) const;
    void _RESERVEDAppleARMIO0();
    void _RESERVEDAppleARMIO1();
    void _RESERVEDAppleARMIO2();
    void _RESERVEDAppleARMIO3();
};
OSDefineMetaClassAndStructors(AppleARMIO, IOService)

AppleARMIO *AppleARMIO::createDeviceWithProvider(AppleARMIO *, IORegistryEntry *) {return nullptr;}
const char *AppleARMIO::deleteList() {return "";}
const char *AppleARMIO::excludeList() {return "";}
IOReturn AppleARMIO::getClockName(unsigned, unsigned *, unsigned) {return kIOReturnUnsupported;}
void AppleARMIO::publishBelow(IORegistryEntry *) {}
bool AppleARMIO::isDMACoherent(IOService *, unsigned) {return true;}
void AppleARMIO::processDevice(IOService *) {}
IOReturn AppleARMIO::getNubResources(IOService *) {return kIOReturnUnsupported;}
IOReturn AppleARMIO::resetPsdService(unsigned, char *, unsigned) {return kIOReturnUnsupported;}
IOReturn AppleARMIO::enablePsdService(unsigned, unsigned, char *, unsigned) {return kIOReturnUnsupported;}
IOReturn AppleARMIO::enableDeviceClock(unsigned, unsigned) {return kIOReturnUnsupported;}
IOReturn AppleARMIO::enableDevicePower(unsigned, unsigned, unsigned *) {return kIOReturnUnsupported;}
IOReturn AppleARMIO::getClockFrequency(const OSSymbol *, unsigned *, unsigned) {return kIOReturnUnsupported;}
IOReturn AppleARMIO::getClockFrequency(const char *, unsigned *, unsigned) {return kIOReturnUnsupported;}
IOReturn AppleARMIO::getClockFrequency(unsigned, unsigned *, unsigned) {return kIOReturnUnsupported;}
IOReturn AppleARMIO::getIODeviceClocks(unsigned *, bool, unsigned) {return kIOReturnUnsupported;}
IOReturn AppleARMIO::getPsdServiceState(unsigned, unsigned *, unsigned) {return kIOReturnUnsupported;}
void AppleARMIO::handlePlatformError(unsigned long) {}
IOReturn AppleARMIO::enableDevicePinGroup(unsigned *, unsigned) {return kIOReturnUnsupported;}
void AppleARMIO::registerAltErrorHandler(AppleARMFunction *) {}
bool AppleARMIO::compareNubName(const IOService *, OSString *, OSString **) const {return false;}
void AppleARMIO::_RESERVEDAppleARMIO0() {}
void AppleARMIO::_RESERVEDAppleARMIO1() {}
void AppleARMIO::_RESERVEDAppleARMIO2() {}
void AppleARMIO::_RESERVEDAppleARMIO3() {}

class AppleARMPE : public IODTPlatformExpert {
    OSDeclareDefaultStructors(AppleARMPE)
public:
    const char *deleteList() override;
    const char *excludeList() override;
    void PMRegisterDevice(IOService *, IOService *) override;
    IOReturn callPlatformFunction(const OSSymbol *, bool, void *, void *, void *, void *) override;
    bool platformAdjustService(IOService *) override;
    void PMInstantiatePowerDomains() override;
    OSString *createSystemSerialNumberString(OSData *) override;
};
OSDefineMetaClassAndStructors(AppleARMPE, IODTPlatformExpert)

const char *AppleARMPE::deleteList() {return "";}
const char *AppleARMPE::excludeList() {return "";}
void AppleARMPE::PMRegisterDevice(IOService *parent, IOService *device) {IODTPlatformExpert::PMRegisterDevice(parent, device);}
IOReturn AppleARMPE::callPlatformFunction(const OSSymbol *name, bool wait, void *p1, void *p2, void *p3, void *p4)
{
    return IODTPlatformExpert::callPlatformFunction(name, wait, p1, p2, p3, p4);
}
bool AppleARMPE::platformAdjustService(IOService *service) {return IODTPlatformExpert::platformAdjustService(service);}
void AppleARMPE::PMInstantiatePowerDomains() {IODTPlatformExpert::PMInstantiatePowerDomains();}
OSString *AppleARMPE::createSystemSerialNumberString(OSData *data) {return IODTPlatformExpert::createSystemSerialNumberString(data);}

// The platform function names the kept kexts pass to callPlatformFunction: nothing implements them here.
// The USB cable keys are IOAccessoryManager's and AppleVirtualPlatform's USB device side, which nothing here starts.
extern "C" {
const OSSymbol *gAppleARMFunctionCall;
const OSSymbol *gAppleARMPEFindCoproviderKey;
const OSSymbol *gAppleARMUSBCableDetectResourceKey;
const OSSymbol *gAppleARMUSBCableTypeResourceKey;
const OSSymbol *gAppleARMUSBCableTypeDetached;
const OSSymbol *gAppleARMUSBCableTypeUSBDevice;
const OSSymbol *gAppleARMUSBCableTypeUSBDeviceNeedsAuthentication;
const OSSymbol *gAppleARMUSBCableTypeUSBHost;
const OSSymbol *gAppleARMUSBCableTypeUSBHostAltConfig;
const OSSymbol *gAppleARMUSBCableTypeUSB3Device;
const OSSymbol *gAppleARMUSBCableTypeUSB3DeviceNeedsAuthentication;
const OSSymbol *gAppleARMUSBCableTypeUSB3Host;
const OSSymbol *gAppleARMUSBCableTypeUSB3HostAltConfig;
}

namespace {
struct Symbols {
    Symbols()
    {
        gAppleARMFunctionCall = OSSymbol::withCStringNoCopy("AppleARMFunctionCall");
        gAppleARMPEFindCoproviderKey = OSSymbol::withCStringNoCopy("AppleARMPEFindCoprovider");
        gAppleARMUSBCableDetectResourceKey = OSSymbol::withCStringNoCopy("AppleARMUSBCableDetect");
        gAppleARMUSBCableTypeResourceKey = OSSymbol::withCStringNoCopy("AppleARMUSBCableType");
        gAppleARMUSBCableTypeDetached = OSSymbol::withCStringNoCopy("Detached");
        gAppleARMUSBCableTypeUSBDevice = OSSymbol::withCStringNoCopy("USBDevice");
        gAppleARMUSBCableTypeUSBDeviceNeedsAuthentication = OSSymbol::withCStringNoCopy("USBDeviceNeedsAuthentication");
        gAppleARMUSBCableTypeUSBHost = OSSymbol::withCStringNoCopy("USBHost");
        gAppleARMUSBCableTypeUSBHostAltConfig = OSSymbol::withCStringNoCopy("USBHostAltConfig");
        gAppleARMUSBCableTypeUSB3Device = OSSymbol::withCStringNoCopy("USB3Device");
        gAppleARMUSBCableTypeUSB3DeviceNeedsAuthentication = OSSymbol::withCStringNoCopy("USB3DeviceNeedsAuthentication");
        gAppleARMUSBCableTypeUSB3Host = OSSymbol::withCStringNoCopy("USB3Host");
        gAppleARMUSBCableTypeUSB3HostAltConfig = OSSymbol::withCStringNoCopy("USB3HostAltConfig");
    }
} gSymbols;   // OSKext::start runs the constructors before any kext that lists this one as a library starts
}
