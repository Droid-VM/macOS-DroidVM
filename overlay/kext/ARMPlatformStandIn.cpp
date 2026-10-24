// SPDX-License-Identifier: BSD-2-Clause-Patent
// Stand-in for AppleARMPlatform, AppleIISController and AppleAudioClockLibs (scripts/kc-build.py "stands_in_for"): IOMobileGraphicsFamily and the kexts it
// needs (IOAVFamily, AppleM2ScalerCSCDriver, IODARTFamily) link against them, but they are Apple SoC drivers this platform does not
// have (ArmDTPlatform publishes the devices), and the source-built kernel's larger __TEXT covers AppleARMPlatform's in the
// collection (AppleAudioClockLibs' too). The kept kexts only look up optional platform functions and type-check providers, so the stand-in gives them
// what an absent function or a provider of another class gives: no function, and classes no object belongs to.
#include <IOKit/IOService.h>
#include <libkern/c++/OSSymbol.h>

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

// The platform function names the kept kexts pass to callPlatformFunction: nothing implements them here.
extern "C" {
const OSSymbol *gAppleARMFunctionCall;
const OSSymbol *gAppleARMPEFindCoproviderKey;
}

namespace {
struct Symbols {
    Symbols()
    {
        gAppleARMFunctionCall = OSSymbol::withCStringNoCopy("AppleARMFunctionCall");
        gAppleARMPEFindCoproviderKey = OSSymbol::withCStringNoCopy("AppleARMPEFindCoprovider");
    }
} gSymbols;   // OSKext::start runs the constructors before any kext that lists this one as a library starts
}
