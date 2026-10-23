// SPDX-License-Identifier: BSD-2-Clause-Patent
// Module start/stop for a driver that scripts/kc-build.py links into the collection as a kext of its own.
// OSKext::start runs the C++ constructors (OSRuntimeInitializeCPP) around these; the driver itself starts through IOKit matching.
#include <mach/kmod.h>

extern "C" {
kern_return_t native_kext_start(kmod_info_t *, void *) { return KERN_SUCCESS; }
kern_return_t native_kext_stop(kmod_info_t *, void *) { return KERN_SUCCESS; }
}
