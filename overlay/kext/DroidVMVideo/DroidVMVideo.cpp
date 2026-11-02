// SPDX-License-Identifier: BSD-2-Clause-Patent
// DroidVMVideo: VideoToolbox's paravirtualized decoders and encoders on the phone's MediaCodec. The guest kernel plays the host
// side of Apple's VideoToolbox paravirtualization (AppleVideoToolboxParavirtualizationDriver, which
// VideoToolboxParavirtualizationSupport.framework opens) and runs its sessions on crosvm's virtio-media decoders and encoders
// (--virtio-mmio-media, the ADT's /arm-io/virtio-media-N): Droid-VM/UniXNU-droidvm package/DroidVMVirtioMedia.c,
// DroidVMVTParavirt.cpp and DroidVMVTHost.cpp (wip/hackintosh, exported by k27/build-native-video.sh). There the board's late
// probe starts both; here this starter does, on a thread of its own, as IOResources matches it (its start must not wait: see
// DroidVMEthernet). The service is published with droidvm-vt-paravirt=1 or by writing 1 to kern.droidvm_vt_paravirt.
#include <IOKit/IOService.h>
#include <kern/thread.h>

extern "C" {
void droidvm_media_start(void);
int droidvm_vt_paravirt_attach(void);
}

namespace {

void startVideo(void *, wait_result_t) {
  droidvm_media_start();
  droidvm_vt_paravirt_attach();
}

}  // namespace

class DroidVMVideo : public IOService {
  OSDeclareDefaultStructors(DroidVMVideo)
public:
  bool start(IOService *provider) override {
    static bool started;
    if (started || !IOService::start(provider)) return false;
    started = true;
    thread_t thread;
    if (kernel_thread_start(startVideo, nullptr, &thread) == KERN_SUCCESS) thread_deallocate(thread);
    return true;
  }
};
OSDefineMetaClassAndStructors(DroidVMVideo, IOService)
