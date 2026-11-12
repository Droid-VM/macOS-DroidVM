// SPDX-License-Identifier: BSD-2-Clause-Patent
// Modern virtio-pci transport (VirtIO 1.2 4.1) on bus 0 of a generic ECAM host bridge, shared by the UniXNU-droidvm
// virtio drivers. crosvm (DroidVM) has virtio-pci only; QEMU virt runs with highmem=off so ECAM and BARs stay below 4 GiB.
// The firmware has assigned the BARs; the transport enables memory decode and bus mastering.
// Enumerated PCI clients may map queue MSI-X vectors after the PCI family allocates them.
#pragma once
#include <IOKit/IOLib.h>
#include <IOKit/IOMemoryDescriptor.h>
#include <kern/clock.h>
#include <kern/task.h>

namespace virtio_pci {

// MMIO and ECAM accesses go through these: plain ldr/str with a base register only. Compilers otherwise pick pre/post-index
// writeback forms, whose aborts carry no instruction syndrome (ISV=0); KVM and Gunyah cannot emulate those and the guest
// takes an external abort.
template <typename T> inline T mmioRead(uintptr_t address)
{
  T value;
  if constexpr (sizeof(T) == 1) {
    uint32_t word;
    __asm__ volatile("ldrb %w0, [%1]" : "=r"(word) : "r"(address) : "memory");
    value = static_cast<T>(word);
  } else if constexpr (sizeof(T) == 2) {
    uint32_t word;
    __asm__ volatile("ldrh %w0, [%1]" : "=r"(word) : "r"(address) : "memory");
    value = static_cast<T>(word);
  } else if constexpr (sizeof(T) == 4) {
    __asm__ volatile("ldr %w0, [%1]" : "=r"(value) : "r"(address) : "memory");
  } else {
    __asm__ volatile("ldr %0, [%1]" : "=r"(value) : "r"(address) : "memory");
  }
  return value;
}

template <typename T> inline void mmioWrite(uintptr_t address, T value)
{
  if constexpr (sizeof(T) == 1) {
    __asm__ volatile("strb %w0, [%1]" : : "r"(static_cast<uint32_t>(value)), "r"(address) : "memory");
  } else if constexpr (sizeof(T) == 2) {
    __asm__ volatile("strh %w0, [%1]" : : "r"(static_cast<uint32_t>(value)), "r"(address) : "memory");
  } else if constexpr (sizeof(T) == 4) {
    __asm__ volatile("str %w0, [%1]" : : "r"(value), "r"(address) : "memory");
  } else {
    __asm__ volatile("str %0, [%1]" : : "r"(value), "r"(address) : "memory");
  }
  __asm__ volatile("dsb oshst" ::: "memory");
}

constexpr uint16_t vendorId = 0x1af4;
// virtio device IDs (VirtIO 1.2 5)
enum : unsigned { deviceBlock = 2, deviceGpu = 16, deviceInput = 18 };
// virtio_pci_common_cfg
enum : unsigned {
  deviceFeatureSelect = 0x00, deviceFeature = 0x04, driverFeatureSelect = 0x08, driverFeature = 0x0c,
  configMsixVector = 0x10, deviceStatus = 0x14, configGeneration = 0x15, queueSelect = 0x16, queueSize = 0x18,
  queueMsixVector = 0x1a,
  queueEnable = 0x1c, queueNotifyOff = 0x1e, queueDesc = 0x20, queueDriver = 0x28, queueDevice = 0x30,
};
// virtio_pci_cap cfg_type
enum : unsigned { capCommon = 1, capNotify = 2, capIsr = 3, capDevice = 4 };
// Device status bits
enum : uint8_t { statusAcknowledge = 1, statusDriver = 2, statusDriverOk = 4, statusFeaturesOk = 8 };
constexpr unsigned maxQueues = 4;

// Modern IDs are 0x1040 + device ID; the only transitional one used here is the block device's 0x1001.
inline bool matches(uint32_t id, unsigned device)
{
  if ((id & 0xffff) != vendorId) return false;
  uint16_t pciDevice = static_cast<uint16_t>(id >> 16);
  return pciDevice == 0x1040 + device || (device == deviceBlock && pciDevice == 0x1001);
}

// Number of functions of the given virtio device type on bus 0 of the mapped ECAM window.
inline unsigned count(uintptr_t ecam, uint64_t ecamLength, unsigned device)
{
  unsigned found = 0;
  if (ecamLength < 0x100000) return 0;
  for (unsigned slot = 0; slot < 32; ++slot) found += matches(mmioRead<uint32_t>(ecam + (slot << 15)), device);
  return found;
}

class Transport {
  IOMemoryMap *maps[5] = {};
  uintptr_t window[5] = {};
  uint64_t windowLength[5] = {};
  uint64_t windowPhysical[5] = {};
  uintptr_t notifyAddress[maxQueues] = {};
  uint32_t notifyMultiplier = 0;
  uintptr_t function = 0;
  unsigned slot = 0;

  static uint32_t config32(uintptr_t function, unsigned offset) { return mmioRead<uint32_t>(function + offset); }

  static IOMemoryMap *mapPhysical(uint64_t physical, uint64_t length, uintptr_t *address) {
    uint64_t page = physical & ~static_cast<uint64_t>(4095);
    uint64_t end = (physical + length + 4095) & ~static_cast<uint64_t>(4095);
    if (!length || end <= page) return nullptr;
    IOMemoryDescriptor *descriptor = IOMemoryDescriptor::withPhysicalAddress(page, end - page, kIODirectionNone);
    if (!descriptor) return nullptr;
    IOMemoryMap *map = descriptor->createMappingInTask(kernel_task, 0, kIOMapAnywhere | kIOMapInhibitCache);
    descriptor->release();
    if (map) *address = static_cast<uintptr_t>(map->getVirtualAddress() + (physical - page));
    return map;
  }

public:
  template <typename T> T read(unsigned which, unsigned offset) const { return mmioRead<T>(window[which] + offset); }
  template <typename T> void write(unsigned which, unsigned offset, T value) { mmioWrite<T>(window[which] + offset, value); }
  bool isOpen() const { return window[capCommon] != 0; }
  unsigned pciSlot() const { return slot; }
  uint64_t commonPhysical() const { return windowPhysical[capCommon]; }

  // An enumerated IOPCIDevice owns its BAR mappings; use the bridge's assigned resources.
  template <typename PciDevice> bool open(PciDevice *pci) {
    if (isOpen()) return false;
    slot = pci->getDeviceNumber();
    pci->setMemoryEnable(true);
    pci->setBusMasterEnable(true);
    unsigned guard = 0;
    for (unsigned cap = pci->configRead32(0x34) & 0xfc; cap && guard < 48; ++guard) {
      uint32_t head = pci->configRead32(cap);
      unsigned type = (head >> 24) & 0xff, bar = pci->configRead32(cap + 4) & 0xff;
      if ((head & 0xff) == 0x09 && type >= capCommon && type <= capDevice && bar <= 5 && !maps[type]) {
        uint32_t offset = pci->configRead32(cap + 8), length = pci->configRead32(cap + 12);
        maps[type] = pci->mapDeviceMemoryWithRegister(0x10 + 4 * bar, kIOMapAnywhere | kIOMapInhibitCache);
        if (!maps[type] || !length || static_cast<uint64_t>(offset) + length > maps[type]->getLength()) {
          close();
          return false;
        }
        window[type] = maps[type]->getVirtualAddress() + offset;
        windowLength[type] = length;
        windowPhysical[type] = maps[type]->getPhysicalAddress() + offset;
        if (type == capNotify) notifyMultiplier = pci->configRead32(cap + 16);
      }
      cap = (head >> 8) & 0xfc;
    }
    if (!window[capCommon] || !window[capNotify]) { close(); return false; }
    return true;
  }

  // Open the index-th function of the given virtio device type on bus 0 of the mapped ECAM window.
  bool open(uintptr_t ecam, uint64_t ecamLength, unsigned device, unsigned index = 0) {
    if (isOpen() || ecamLength < 0x100000) return false;
    unsigned found = 0;
    for (unsigned candidate = 0; candidate < 32 && !function; ++candidate) {
      uintptr_t at = ecam + (candidate << 15);
      if (matches(config32(at, 0), device) && found++ == index) {
        function = at;
        slot = candidate;
      }
    }
    if (!function || !(config32(function, 4) & (0x10U << 16))) return false;
    uint64_t base[5] = {}, length[5] = {};
    unsigned guard = 0;
    for (unsigned cap = config32(function, 0x34) & 0xfc; cap && guard < 48; ++guard) {
      uint32_t head = config32(function, cap);
      unsigned type = (head >> 24) & 0xff, bar = config32(function, cap + 4) & 0xff;
      if ((head & 0xff) == 0x09 && type >= capCommon && type <= capDevice && bar <= 5 && !length[type]) {
        uint32_t low = config32(function, 0x10 + 4 * bar);
        uint64_t address = (low & 1) ? 0 : (low & ~static_cast<uint64_t>(15));
        if (address && ((low >> 1) & 3) == 2)
          address |= bar < 5 ? static_cast<uint64_t>(config32(function, 0x14 + 4 * bar)) << 32 : 0;
        uint32_t offset = config32(function, cap + 8), size = config32(function, cap + 12);
        if (address && size) {
          base[type] = address + offset;
          length[type] = size;
          if (type == capNotify) notifyMultiplier = config32(function, cap + 16);
        }
      }
      cap = (head >> 8) & 0xfc;
    }
    if (!length[capCommon] || !length[capNotify]) return false;
    // Memory space and bus master; the upper half (status) is write-one-to-clear, so it is written as zero.
    mmioWrite<uint32_t>(function + 4, (config32(function, 4) & 0xffff) | 0x6);
    for (unsigned type = capCommon; type <= capDevice; ++type) {
      if (!length[type]) continue;
      maps[type] = mapPhysical(base[type], length[type], &window[type]);
      if (!maps[type]) { close(); return false; }
      windowLength[type] = length[type];
      windowPhysical[type] = base[type];
    }
    return true;
  }

  void close() {
    for (auto &map : maps) if (map) { map->release(); map = nullptr; }
    for (auto &address : window) address = 0;
    for (auto &address : notifyAddress) address = 0;
    function = 0;
  }

  uint8_t status() const { return read<uint8_t>(capCommon, deviceStatus); }
  void setStatus(uint8_t value) { write<uint8_t>(capCommon, deviceStatus, value); }

  // Write 0 and wait for the device to acknowledge the reset, which also stops all DMA.
  bool reset(unsigned milliseconds = 1000) {
    if (!isOpen()) return true;
    setStatus(0);
    uint64_t deadline;
    clock_interval_to_deadline(milliseconds, kMillisecondScale, &deadline);
    while (status()) {
      if (mach_absolute_time() >= deadline) return false;
      IODelay(1);
    }
    return true;
  }

  uint32_t deviceFeatures(uint32_t select) {
    write<uint32_t>(capCommon, deviceFeatureSelect, select);
    return read<uint32_t>(capCommon, deviceFeature);
  }
  void setDriverFeatures(uint32_t select, uint32_t value) {
    write<uint32_t>(capCommon, driverFeatureSelect, select);
    write<uint32_t>(capCommon, driverFeature, value);
  }

  // Acknowledge, require VIRTIO_F_VERSION_1 plus the given low feature bits, and reach FEATURES_OK.
  bool negotiate(uint32_t requiredLow, uint32_t optionalLow = 0) {
    if (!reset()) return false;
    setStatus(statusAcknowledge);
    setStatus(statusAcknowledge | statusDriver);
    uint32_t low = deviceFeatures(0), high = deviceFeatures(1);
    if ((low & requiredLow) != requiredLow || !(high & 1)) return false;
    setDriverFeatures(0, requiredLow | (low & optionalLow));
    setDriverFeatures(1, 1);
    setStatus(statusAcknowledge | statusDriver | statusFeaturesOk);
    return (status() & statusFeaturesOk) != 0;
  }

  // Select a queue; its maximum size, or 0 when the queue does not exist or is already enabled.
  uint16_t queueMaximum(uint16_t queue) {
    if (queue >= maxQueues) return 0;
    write<uint16_t>(capCommon, queueSelect, queue);
    if (read<uint16_t>(capCommon, queueEnable)) return 0;
    return read<uint16_t>(capCommon, queueSize);
  }

  // Program and enable a split queue (descriptor table, driver/available ring, device/used ring).
  bool enableQueue(uint16_t queue, uint16_t size, uint64_t descriptors, uint64_t driver, uint64_t device) {
    if (queue >= maxQueues) return false;
    write<uint16_t>(capCommon, queueSelect, queue);
    uint64_t offset = static_cast<uint64_t>(read<uint16_t>(capCommon, queueNotifyOff)) * notifyMultiplier;
    if (offset + 2 > windowLength[capNotify]) return false;
    notifyAddress[queue] = window[capNotify] + offset;
    write<uint16_t>(capCommon, queueSize, size);
    write<uint32_t>(capCommon, queueDesc, static_cast<uint32_t>(descriptors));
    write<uint32_t>(capCommon, queueDesc + 4, static_cast<uint32_t>(descriptors >> 32));
    write<uint32_t>(capCommon, queueDriver, static_cast<uint32_t>(driver));
    write<uint32_t>(capCommon, queueDriver + 4, static_cast<uint32_t>(driver >> 32));
    write<uint32_t>(capCommon, queueDevice, static_cast<uint32_t>(device));
    write<uint32_t>(capCommon, queueDevice + 4, static_cast<uint32_t>(device >> 32));
    write<uint16_t>(capCommon, queueEnable, 1);
    return true;
  }

  void notify(uint16_t queue) {
    if (queue < maxQueues && notifyAddress[queue]) {
      mmioWrite<uint16_t>(notifyAddress[queue], queue);
    }
  }

  bool setQueueVector(uint16_t queue, uint16_t vector) {
    write<uint16_t>(capCommon, queueSelect, queue);
    write<uint16_t>(capCommon, queueMsixVector, vector);
    return read<uint16_t>(capCommon, queueMsixVector) == vector;
  }

  void disableConfigInterrupt() { write<uint16_t>(capCommon, configMsixVector, 0xffff); }

  // Reading the ISR status acknowledges (and deasserts) a pending INTx.
  void acknowledgeInterrupt() { if (window[capIsr]) (void)read<uint8_t>(capIsr, 0); }

  bool hasDeviceConfig() const { return window[capDevice] != 0; }
  uint8_t generation() const { return read<uint8_t>(capCommon, configGeneration); }
  template <typename T> T config(unsigned offset) const { return read<T>(capDevice, offset); }
  template <typename T> void setConfig(unsigned offset, T value) { write<T>(capDevice, offset, value); }
};

}  // namespace virtio_pci
