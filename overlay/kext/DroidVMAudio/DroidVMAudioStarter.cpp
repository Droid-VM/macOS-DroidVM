// SPDX-License-Identifier: BSD-2-Clause-Patent
// DroidVMAudio: the guest's speaker and microphone as IOAudio2Devices, which coreaudiod's HAL (HALS_IOA2Manager) takes as
// built-in devices, over crosvm's virtio-snd (--virtio-mmio-snd, the ADT's /arm-io/virtio-snd): Droid-VM/UniXNU-droidvm
// package/DroidVMAudio.cpp and DroidVMVirtioSnd.c (wip/hackintosh, exported by k27/build-native-audio.sh). There the board's
// late probe starts both; here this starter does, on a thread of its own, as IOResources matches it (its start must not wait:
// see DroidVMEthernet). Without a virtio-snd window the devices run on their own clock into silence, so the system still has a
// default output (WebKit's media player fails without one: AVSampleBufferAudioRenderer init returns nil).
#include <IOKit/IOService.h>
#include <kern/thread.h>

extern "C" void droidvm_snd_start(void);

namespace {

void startAudio(void *, wait_result_t) { droidvm_snd_start(); }

}  // namespace

class DroidVMAudioStarter : public IOService {
  OSDeclareDefaultStructors(DroidVMAudioStarter)
public:
  bool start(IOService *provider) override {
    static bool started;
    if (started || !IOService::start(provider)) return false;
    started = true;
    thread_t thread;
    if (kernel_thread_start(startAudio, nullptr, &thread) == KERN_SUCCESS) thread_deallocate(thread);
    return true;
  }
};
OSDefineMetaClassAndStructors(DroidVMAudioStarter, IOService)
