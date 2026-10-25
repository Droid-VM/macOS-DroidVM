// SPDX-License-Identifier: BSD-2-Clause-Patent
// DroidVMInput: the DroidVM app's input devices (crosvm --input: multi-touch screen, tablet, mouse, keyboard) as HID devices.
// They are virtio-input functions on bus 0 of crosvm's ECAM bridge, /arm-io/pcie in the ADT (scripts/run-macos-vm.py). The
// transport and the queue set-up are those of the iOS driver (overlay/droidvm/drivers/NativeVirtioInputPci); here each device
// becomes an IOHIDDevice with the report descriptor of QEMU's USB devices, which IOHIDFamily's event drivers turn into keyboard
// and pointer events:
//   - a keyboard: the boot keyboard report (modifiers and six keys), Linux key codes translated to HID usages;
//   - a multi-touch screen or an absolute pointer: the tablet report (absolute X/Y 0..32767, three buttons, wheel); a touch
//     screen's first finger is the pointer and any finger down is the left button;
//   - a relative mouse: the boot mouse report.
// No interrupts: a kernel thread polls every 4 ms. Headers: the SDK's IOKit/hid (out/x12377/inc-hid).
#include <IOKit/IOBufferMemoryDescriptor.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOService.h>
#include <IOKit/IOUserClient.h>
#include <IOKit/hid/IOHIDDevice.h>
#include <kern/thread.h>
#include "NativeVirtioPci.h"

namespace {

enum : uint16_t { evSyn = 0, evKey = 1, evRel = 2, evAbs = 3, synReport = 0 };
enum : uint16_t {
  absX = 0x00, absY = 0x01, absMtSlot = 0x2f, absMtPositionX = 0x35, absMtPositionY = 0x36, absMtTrackingId = 0x39,
  relX = 0x00, relY = 0x01, relWheel = 0x08, keyA = 30, btnLeft = 0x110, btnRight = 0x111, btnMiddle = 0x112, btnTouch = 0x14a,
};
enum : uint8_t { cfgSelect = 0, cfgSubsel = 1, cfgSize = 2, cfgData = 8 };
enum : uint8_t { cfgEvBits = 0x11, cfgAbsInfo = 0x12 };
enum class Kind : uint8_t { none, touch, pointer, mouse, keyboard };

constexpr unsigned maxDevices = 8, maxSlots = 10, maxQueue = 64, pollMs = 4;
constexpr int32_t tabletRange = 0x8000;

// usb_kbd_keycode of Linux (drivers/hid/usbhid/usbkbd.c): HID usage -> Linux key code; inverted at start.
const uint8_t hidToLinux[256] = {
    0,  0,  0,  0, 30, 48, 46, 32, 18, 33, 34, 35, 23, 36, 37, 38,
   50, 49, 24, 25, 16, 19, 31, 20, 22, 47, 17, 45, 21, 44,  2,  3,
    4,  5,  6,  7,  8,  9, 10, 11, 28,  1, 14, 15, 57, 12, 13, 26,
   27, 43, 43, 39, 40, 41, 51, 52, 53, 58, 59, 60, 61, 62, 63, 64,
   65, 66, 67, 68, 87, 88, 99, 70,119,110,102,104,111,107,109,106,
  105,108,103, 69, 98, 55, 74, 78, 96, 79, 80, 81, 75, 76, 77, 71,
   72, 73, 82, 83, 86,127,116,117,183,184,185,186,187,188,189,190,
  191,192,193,194,134,138,130,132,128,129,131,137,133,135,136,113,
  115,114,  0,  0,  0,121,  0, 89, 93,124, 92, 94, 95,  0,  0,  0,
  122,123, 90, 91, 85,  0,  0,  0,  0,  0,  0,  0,111,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
   29, 42, 56,125, 97, 54,100,126,164,166,165,163,161,115,114,113,
  150,158,159,128,136,177,178,176,142,152,173,140,
};
uint8_t linuxToHid[256];

// QEMU hw/input/hid.c / dev-hid.c report descriptors.
const uint8_t keyboardDescriptor[] = {
  0x05, 0x01, 0x09, 0x06, 0xa1, 0x01,
  0x75, 0x01, 0x95, 0x08, 0x05, 0x07, 0x19, 0xe0, 0x29, 0xe7, 0x15, 0x00, 0x25, 0x01, 0x81, 0x02,
  0x95, 0x01, 0x75, 0x08, 0x81, 0x01,
  0x95, 0x05, 0x75, 0x01, 0x05, 0x08, 0x19, 0x01, 0x29, 0x05, 0x91, 0x02,
  0x95, 0x01, 0x75, 0x03, 0x91, 0x01,
  0x95, 0x06, 0x75, 0x08, 0x15, 0x00, 0x26, 0xff, 0x00, 0x05, 0x07, 0x19, 0x00, 0x2a, 0xff, 0x00, 0x81, 0x00,
  0xc0,
};
const uint8_t tabletDescriptor[] = {
  0x05, 0x01, 0x09, 0x02, 0xa1, 0x01, 0x09, 0x01, 0xa1, 0x00,
  0x05, 0x09, 0x19, 0x01, 0x29, 0x03, 0x15, 0x00, 0x25, 0x01, 0x95, 0x03, 0x75, 0x01, 0x81, 0x02,
  0x95, 0x01, 0x75, 0x05, 0x81, 0x01,
  0x05, 0x01, 0x09, 0x30, 0x09, 0x31, 0x15, 0x00, 0x26, 0xff, 0x7f, 0x35, 0x00, 0x46, 0xff, 0x7f, 0x75, 0x10, 0x95, 0x02,
  0x81, 0x02,
  0x05, 0x01, 0x09, 0x38, 0x15, 0x81, 0x25, 0x7f, 0x35, 0x00, 0x45, 0x00, 0x75, 0x08, 0x95, 0x01, 0x81, 0x06,
  0xc0, 0xc0,
};
const uint8_t mouseDescriptor[] = {
  0x05, 0x01, 0x09, 0x02, 0xa1, 0x01, 0x09, 0x01, 0xa1, 0x00,
  0x05, 0x09, 0x19, 0x01, 0x29, 0x03, 0x15, 0x00, 0x25, 0x01, 0x95, 0x03, 0x75, 0x01, 0x81, 0x02,
  0x95, 0x01, 0x75, 0x05, 0x81, 0x01,
  0x05, 0x01, 0x09, 0x30, 0x09, 0x31, 0x09, 0x38, 0x15, 0x81, 0x25, 0x7f, 0x75, 0x08, 0x95, 0x03, 0x81, 0x06,
  0xc0, 0xc0,
};

struct Event { uint16_t type, code; int32_t value; };
struct Descriptor { uint64_t address; uint32_t length; uint16_t flags, next; };
static_assert(sizeof(Event) == 8 && sizeof(Descriptor) == 16, "VirtIO wire layout");
inline void dmaBarrier() { __asm__ volatile("dmb osh" ::: "memory"); }

}  // namespace

class DroidVMHIDDevice;

struct DroidVMInputDevice {
  virtio_pci::Transport transport;
  IOBufferMemoryDescriptor *memory = nullptr;   // event queue (page 0) and its buffers (page 1)
  IOBufferMemoryDescriptor *status = nullptr;   // status queue, never used: crosvm enables a device only with both
  unsigned char *base = nullptr;
  uint16_t size = 0, used = 0;
  Kind kind = Kind::none;
  int32_t minX = 0, spanX = 1, minY = 0, spanY = 1;
  unsigned slot = 0;
  struct { int32_t id = -1, x = 0, y = 0; } slots[maxSlots];
  int32_t x = 0, y = 0, dx = 0, dy = 0, wheel = 0;
  uint8_t buttons = 0, modifiers = 0, keys[6] = {};
  uint8_t last[8] = {};
  unsigned reports = 0;
  DroidVMHIDDevice *hid = nullptr;
  Descriptor *descriptors() { return reinterpret_cast<Descriptor *>(base); }
  volatile uint16_t *available() { return reinterpret_cast<volatile uint16_t *>(base + 1024); }
  volatile uint16_t *usedRing() { return reinterpret_cast<volatile uint16_t *>(base + 2048); }
  const volatile uint32_t *usedElements() { return reinterpret_cast<const volatile uint32_t *>(base + 2052); }
  Event *events() { return reinterpret_cast<Event *>(base + 4096); }
};

class DroidVMHIDDevice : public IOHIDDevice {
  OSDeclareDefaultStructors(DroidVMHIDDevice)

public:
  DroidVMInputDevice *fDevice = nullptr;
  unsigned fIndex = 0;

  IOReturn newReportDescriptor(IOMemoryDescriptor **descriptor) const override;
  OSString *newTransportString() const override { return OSString::withCString("Virtual"); }
  OSString *newManufacturerString() const override { return OSString::withCString("DroidVM"); }
  OSString *newProductString() const override;
  OSNumber *newVendorIDNumber() const override { return OSNumber::withNumber(virtio_pci::vendorId, 32); }
  OSNumber *newProductIDNumber() const override { return OSNumber::withNumber(0x1052, 32); }
  OSNumber *newLocationIDNumber() const override { return OSNumber::withNumber(0x44560000 | fIndex, 32); }
  OSNumber *newPrimaryUsagePageNumber() const override { return OSNumber::withNumber(kHIDPage_GenericDesktop, 32); }
  OSNumber *newPrimaryUsageNumber() const override;
};

OSDefineMetaClassAndStructors(DroidVMHIDDevice, IOHIDDevice)

IOReturn DroidVMHIDDevice::newReportDescriptor(IOMemoryDescriptor **descriptor) const
{
  const uint8_t *bytes = fDevice->kind == Kind::keyboard ? keyboardDescriptor : fDevice->kind == Kind::mouse ? mouseDescriptor
                                                                                                             : tabletDescriptor;
  size_t length = fDevice->kind == Kind::keyboard ? sizeof(keyboardDescriptor) : fDevice->kind == Kind::mouse ? sizeof(mouseDescriptor)
                                                                                                              : sizeof(tabletDescriptor);
  *descriptor = IOBufferMemoryDescriptor::withBytes(bytes, length, kIODirectionNone);
  return *descriptor ? kIOReturnSuccess : kIOReturnNoMemory;
}

OSString *DroidVMHIDDevice::newProductString() const
{
  return OSString::withCString(fDevice->kind == Kind::keyboard ? "DroidVM Keyboard" : fDevice->kind == Kind::touch ? "DroidVM Touch Screen"
                               : fDevice->kind == Kind::mouse ? "DroidVM Mouse" : "DroidVM Tablet");
}

OSNumber *DroidVMHIDDevice::newPrimaryUsageNumber() const
{
  return OSNumber::withNumber(fDevice->kind == Kind::keyboard ? kHIDUsage_GD_Keyboard : kHIDUsage_GD_Mouse, 32);
}

class DroidVMInput : public IOService {
  OSDeclareDefaultStructors(DroidVMInput)

  IOMemoryMap *fEcam = nullptr;
  DroidVMInputDevice fDevices[maxDevices];
  unsigned fCount = 0;

  static void pollThread(void *self, wait_result_t);
  void poll(DroidVMInputDevice &d);
  void event(DroidVMInputDevice &d, const Event &e);
  void report(DroidVMInputDevice &d);
  void describe();

public:
  bool start(IOService *provider) override;
};

OSDefineMetaClassAndStructors(DroidVMInput, IOService)

namespace {

unsigned configBytes(DroidVMInputDevice &d, uint8_t select, uint8_t subsel, uint8_t *out, unsigned capacity)
{
  d.transport.setConfig<uint8_t>(cfgSelect, select);
  d.transport.setConfig<uint8_t>(cfgSubsel, subsel);
  unsigned size = d.transport.config<uint8_t>(cfgSize);
  if (size > capacity) size = capacity;
  for (unsigned i = 0; i < size; ++i) out[i] = d.transport.config<uint8_t>(cfgData + i);
  return size;
}

bool bit(const uint8_t *bits, unsigned size, unsigned index) { return index / 8 < size && (bits[index / 8] >> (index % 8) & 1); }

bool axis(DroidVMInputDevice &d, uint8_t code, int32_t *minimum, int32_t *span)
{
  uint8_t info[20] = {};
  if (configBytes(d, cfgAbsInfo, code, info, sizeof(info)) < 8) return false;
  int32_t low, high;
  memcpy(&low, info, 4);
  memcpy(&high, info + 4, 4);
  if (high <= low) return false;
  *minimum = low;
  *span = high - low + 1;
  return true;
}

Kind identify(DroidVMInputDevice &d)
{
  uint8_t abs[16] = {}, rel[16] = {}, keys[64] = {};
  unsigned nabs = configBytes(d, cfgEvBits, evAbs, abs, sizeof(abs));
  unsigned nrel = configBytes(d, cfgEvBits, evRel, rel, sizeof(rel));
  unsigned nkeys = configBytes(d, cfgEvBits, evKey, keys, sizeof(keys));
  if (bit(abs, nabs, absMtPositionX) && bit(abs, nabs, absMtPositionY) &&
      axis(d, absMtPositionX, &d.minX, &d.spanX) && axis(d, absMtPositionY, &d.minY, &d.spanY)) return Kind::touch;
  if (bit(abs, nabs, absX) && bit(abs, nabs, absY) && axis(d, absX, &d.minX, &d.spanX) && axis(d, absY, &d.minY, &d.spanY))
    return Kind::pointer;
  if (bit(rel, nrel, relX) && bit(rel, nrel, relY)) return Kind::mouse;
  if (bit(keys, nkeys, keyA)) return Kind::keyboard;
  return Kind::none;
}

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

bool configure(DroidVMInputDevice &d)
{
  if (!d.transport.hasDeviceConfig() || !d.transport.negotiate(0)) return false;
  d.kind = identify(d);
  if (d.kind == Kind::none) return false;
  uint16_t maximum = d.transport.queueMaximum(0), statusMaximum = d.transport.queueMaximum(1);
  d.size = maximum < maxQueue ? maximum : static_cast<uint16_t>(maxQueue);
  uint16_t statusSize = statusMaximum < 8 ? statusMaximum : 8;
  if (d.size < 2 || !statusSize) return false;
  uint64_t physical = 0, statusPhysical = 0;
  d.memory = contiguous(8192, &physical);
  d.status = contiguous(4096, &statusPhysical);
  if (!d.memory || !d.status) return false;
  d.base = static_cast<unsigned char *>(d.memory->getBytesNoCopy());
  for (uint16_t i = 0; i < d.size; ++i) {
    d.descriptors()[i] = {physical + 4096 + i * sizeof(Event), sizeof(Event), 2, 0};   // device-writable
    d.available()[2 + i] = i;
  }
  d.available()[0] = 1;   // VIRTQ_AVAIL_F_NO_INTERRUPT: polled
  d.available()[1] = d.size;
  reinterpret_cast<volatile uint16_t *>(static_cast<unsigned char *>(d.status->getBytesNoCopy()) + 1024)[0] = 1;
  dmaBarrier();
  if (!d.transport.enableQueue(0, d.size, physical, physical + 1024, physical + 2048) ||
      !d.transport.enableQueue(1, statusSize, statusPhysical, statusPhysical + 1024, statusPhysical + 2048)) return false;
  d.transport.setStatus(virtio_pci::statusAcknowledge | virtio_pci::statusDriver | virtio_pci::statusFeaturesOk |
                        virtio_pci::statusDriverOk);
  d.transport.notify(0);
  return (d.transport.status() & 15) == 15;
}

int32_t scale(int32_t value, int32_t minimum, int32_t span)
{
  int64_t v = static_cast<int64_t>(value - minimum) * tabletRange / span;
  return v < 0 ? 0 : v >= tabletRange ? tabletRange - 1 : static_cast<int32_t>(v);
}

int8_t clamp8(int32_t value) { return static_cast<int8_t>(value < -127 ? -127 : value > 127 ? 127 : value); }

const char *kindName(Kind kind)
{
  return kind == Kind::touch ? "touch screen" : kind == Kind::pointer ? "tablet" : kind == Kind::mouse ? "mouse" : "keyboard";
}

}  // namespace

bool DroidVMInput::start(IOService *provider)
{
  if (!IOService::start(provider))
    return false;
  for (unsigned usage = 0; usage < 0xe8; ++usage)
    if (hidToLinux[usage] && !linuxToHid[hidToLinux[usage]] && (usage < 0x80 || usage >= 0xe0))
      linuxToHid[hidToLinux[usage]] = static_cast<uint8_t>(usage);
  fEcam = provider->mapDeviceMemoryWithIndex(0, kIOMapAnywhere | kIOMapInhibitCache);
  if (!fEcam) {
    IOLog("DroidVMInput: cannot map the ECAM window\n");
    return false;
  }
  unsigned functions = 0;
  for (unsigned index = 0; index < maxDevices && fCount < maxDevices; ++index) {
    DroidVMInputDevice &d = fDevices[fCount];
    if (!d.transport.open(static_cast<uintptr_t>(fEcam->getVirtualAddress()), fEcam->getLength(), virtio_pci::deviceInput, index))
      break;
    ++functions;
    if (!configure(d)) {
      d.transport.reset();
      d.transport.close();
      OSSafeReleaseNULL(d.memory);
      OSSafeReleaseNULL(d.status);
      d = DroidVMInputDevice();
      continue;
    }
    DroidVMHIDDevice *hid = OSTypeAlloc(DroidVMHIDDevice);
    if (hid) {
      hid->fDevice = &d;
      hid->fIndex = fCount;
    }
    if (!hid || !hid->init(nullptr) || !hid->attach(this)) {
      OSSafeReleaseNULL(hid);
    } else if (!hid->start(this)) {
      hid->detach(this);
      OSSafeReleaseNULL(hid);
    }
    d.hid = hid;
    IOLog("DroidVMInput: function %u: %s, x %d+%d, y %d+%d%s\n", d.transport.pciSlot(), kindName(d.kind), d.minX, d.spanX, d.minY,
          d.spanY, hid ? "" : " (no HID device)");
    ++fCount;
  }
  IOLog("DroidVMInput: %u device(s) of %u virtio-input function(s)\n", fCount, functions);
  if (!fCount)
    return false;
  thread_t thread;
  if (kernel_thread_start(pollThread, this, &thread) != KERN_SUCCESS)
    return false;
  thread_deallocate(thread);
  registerService();
  return true;
}

void DroidVMInput::pollThread(void *self, wait_result_t)
{
  DroidVMInput *input = static_cast<DroidVMInput *>(self);
  for (unsigned tick = 0;; ++tick) {
    if (tick == 30000 / pollMs || tick == 240000 / pollMs)   // bring-up: who attached to the HID devices, and the event services user space can see
      input->describe();
    for (unsigned i = 0; i < input->fCount; ++i)
      input->poll(input->fDevices[i]);
    IOSleep(pollMs);
  }
}

// Takes what the device wrote and gives the buffers back.
void DroidVMInput::poll(DroidVMInputDevice &d)
{
  unsigned returned = 0;
  uint16_t head = d.available()[1];
  while (d.usedRing()[1] != d.used) {
    dmaBarrier();
    uint32_t id = d.usedElements()[(d.used % d.size) * 2];
    if (id < d.size) {
      event(d, d.events()[id]);
      d.available()[2 + (head + returned) % d.size] = static_cast<uint16_t>(id);
      ++returned;
    }
    ++d.used;
  }
  if (returned) {
    dmaBarrier();
    d.available()[1] = static_cast<uint16_t>(head + returned);
    dmaBarrier();
    d.transport.notify(0);
  }
  d.transport.acknowledgeInterrupt();
}

void DroidVMInput::event(DroidVMInputDevice &d, const Event &e)
{
  if (e.type == evSyn) {
    if (e.code == synReport)
      report(d);
    return;
  }
  if (d.kind == Kind::keyboard) {
    if (e.type != evKey || e.code > 255 || e.value == 2)   // 2: autorepeat, the event system repeats on its own
      return;
    uint8_t usage = linuxToHid[e.code];
    if (usage >= 0xe0) {
      uint8_t mask = static_cast<uint8_t>(1 << (usage - 0xe0));
      d.modifiers = e.value ? d.modifiers | mask : d.modifiers & ~mask;
    } else if (usage) {
      for (auto &key : d.keys)
        if (key == usage)
          key = 0;
      for (auto &key : d.keys)
        if (e.value && !key) {
          key = usage;
          break;
        }
    }
    return;
  }
  if (e.type == evKey) {
    uint8_t mask = e.code == btnLeft || e.code == btnTouch ? 1 : e.code == btnRight ? 2 : e.code == btnMiddle ? 4 : 0;
    if (d.kind != Kind::touch)
      d.buttons = e.value ? d.buttons | mask : d.buttons & ~mask;
  } else if (e.type == evRel) {
    if (e.code == relX) d.dx += e.value;
    else if (e.code == relY) d.dy += e.value;
    else if (e.code == relWheel) d.wheel += e.value;
  } else if (e.type == evAbs && d.kind == Kind::touch) {
    if (e.code == absMtSlot) d.slot = e.value >= 0 && e.value < static_cast<int32_t>(maxSlots) ? static_cast<unsigned>(e.value) : maxSlots;
    else if (d.slot < maxSlots) {
      if (e.code == absMtTrackingId) d.slots[d.slot].id = e.value < 0 ? -1 : e.value;
      else if (e.code == absMtPositionX) d.slots[d.slot].x = e.value;
      else if (e.code == absMtPositionY) d.slots[d.slot].y = e.value;
    }
  } else if (e.type == evAbs) {
    if (e.code == absX) d.x = e.value;
    else if (e.code == absY) d.y = e.value;
  }
}

// At the end of a frame: one report if anything changed.
void DroidVMInput::report(DroidVMInputDevice &d)
{
  uint8_t bytes[8] = {};
  unsigned length;
  if (d.kind == Kind::keyboard) {
    bytes[0] = d.modifiers;
    memcpy(bytes + 2, d.keys, sizeof(d.keys));
    length = 8;
  } else if (d.kind == Kind::mouse) {
    do {
      int8_t x = clamp8(d.dx), y = clamp8(d.dy), wheel = clamp8(d.wheel);
      d.dx -= x;
      d.dy -= y;
      d.wheel -= wheel;
      uint8_t mouse[4] = {d.buttons, static_cast<uint8_t>(x), static_cast<uint8_t>(y), static_cast<uint8_t>(wheel)};
      if (d.hid && (x || y || wheel || d.buttons != d.last[0])) {
        IOBufferMemoryDescriptor *report = IOBufferMemoryDescriptor::withBytes(mouse, sizeof(mouse), kIODirectionNone);
        if (report) {
          d.hid->handleReport(report);
          report->release();
        }
      }
      d.last[0] = d.buttons;
    } while (d.dx || d.dy || d.wheel);
    return;
  } else {
    int32_t x = d.x, y = d.y;
    uint8_t buttons = d.buttons;
    if (d.kind == Kind::touch) {
      // The first finger down (else the last position) is the pointer; any finger down is the left button.
      buttons = 0;
      for (const auto &s : d.slots)
        if (s.id >= 0) {
          x = s.x;
          y = s.y;
          buttons = 1;
          break;
        }
      if (!buttons) {
        x = d.x;
        y = d.y;
      }
      d.x = x;
      d.y = y;
    }
    int32_t sx = scale(x, d.minX, d.spanX), sy = scale(y, d.minY, d.spanY), wheel = clamp8(d.wheel);
    d.wheel = 0;
    bytes[0] = buttons;
    bytes[1] = static_cast<uint8_t>(sx);
    bytes[2] = static_cast<uint8_t>(sx >> 8);
    bytes[3] = static_cast<uint8_t>(sy);
    bytes[4] = static_cast<uint8_t>(sy >> 8);
    bytes[5] = static_cast<uint8_t>(wheel);
    length = 6;
  }
  if (!d.hid || !memcmp(bytes, d.last, length))
    return;
  memcpy(d.last, bytes, length);
  if (++d.reports <= 20 || d.reports % 500 == 0)   // bring-up: are the events getting through
    IOLog("DroidVMInput: %s report %u: %02x %02x %02x %02x %02x %02x %02x %02x\n", kindName(d.kind), d.reports, bytes[0], bytes[1],
          bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7]);
  IOBufferMemoryDescriptor *report = IOBufferMemoryDescriptor::withBytes(bytes, length, kIODirectionNone);
  if (report) {
    d.hid->handleReport(report);
    report->release();
  }
}

void DroidVMInput::describe()
{
  for (unsigned i = 0; i < fCount; ++i) {
    if (!fDevices[i].hid)
      continue;
    OSIterator *interfaces = fDevices[i].hid->getChildIterator(gIOServicePlane);
    while (OSObject *object = interfaces ? interfaces->getNextObject() : nullptr) {
      IOService *interface = OSDynamicCast(IOService, object);
      if (!interface)
        continue;
      OSIterator *clients = interface->getChildIterator(gIOServicePlane);
      unsigned n = 0;
      while (OSObject *client = clients ? clients->getNextObject() : nullptr) {
        IOLog("DroidVMInput: %s: %s -> %s\n", kindName(fDevices[i].kind), interface->getMetaClass()->getClassName(),
              client->getMetaClass()->getClassName());
        ++n;
      }
      if (!n)
        IOLog("DroidVMInput: %s: %s has no client\n", kindName(fDevices[i].kind), interface->getMetaClass()->getClassName());
      OSSafeReleaseNULL(clients);
    }
    OSSafeReleaseNULL(interfaces);
  }
  OSIterator *services = IOService::getMatchingServices(IOService::serviceMatching("IOHIDEventService"));
  while (OSObject *object = services ? services->getNextObject() : nullptr) {
    IOService *service = OSDynamicCast(IOService, object);
    IOService *provider = service ? service->getProvider() : nullptr;
    OSIterator *clients = service ? service->getClientIterator() : nullptr;
    unsigned users = 0;
    while (OSObject *client = clients ? clients->getNextObject() : nullptr)
      users += OSDynamicCast(IOUserClient, client) != nullptr;
    OSSafeReleaseNULL(clients);
    IOLog("DroidVMInput: event service %s on %s, %u user client(s)\n", object->getMetaClass()->getClassName(),
          provider ? provider->getMetaClass()->getClassName() : "-", users);
  }
  OSSafeReleaseNULL(services);
}
