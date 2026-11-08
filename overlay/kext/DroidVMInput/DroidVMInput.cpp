// SPDX-License-Identifier: BSD-2-Clause-Patent
// DroidVMInput: the DroidVM app's input devices (crosvm --input: multi-touch screen, tablet, mouse, keyboard) as HID devices.
// They are virtio-input functions on bus 0 of crosvm's ECAM bridge, /arm-io/pcie in the ADT (scripts/run-macos-vm.py). The
// transport and the queue set-up are those of the iOS driver (overlay/droidvm/drivers/NativeVirtioInputPci); here each device
// becomes an IOHIDDevice with the report descriptor of QEMU's USB devices, which IOHIDFamily's event drivers turn into keyboard
// and pointer events:
//   - a keyboard: the boot keyboard report (modifiers and six keys), Linux key codes translated to HID usages;
//   - a multi-touch screen: the tablet report, the first finger the pointer and any finger down the left button. Boot argument
//     droidvm-touch-digitizer=1: a built-in touch screen instead, as a touch screen Mac's: the report descriptor of
//     Virtualization's "Virtual USB Touch Screen" (VzCore::Hardware::UsbTouchScreen, macOS 27) for AppleMultitouchDriver to take
//     it, then Apple's multitouch protocol (feature reports and path frames, below) for HSTouchHIDService.plugin;
//   - an absolute pointer: the tablet report (absolute X/Y 0..32767, three buttons, wheel);
//   - a relative mouse: the boot mouse report.
// No interrupts: a kernel thread polls every 4 ms. Headers: the SDK's IOKit/hid (out/x12377/inc-hid).
#include <IOKit/IOBufferMemoryDescriptor.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOService.h>
#include <IOKit/IOUserClient.h>
#include <IOKit/hid/IOHIDDevice.h>
#include <IOKit/pwr_mgt/RootDomain.h>
#include <kern/clock.h>
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

constexpr unsigned maxDevices = 8, maxSlots = 10, maxQueue = 64, pollMs = 4, fingers = 4;
constexpr int32_t tabletRange = 0x8000;
bool gTouchTablet = true;   // false with droidvm-touch-digitizer=1
char gDisplayUUID[40];      // the built-in digitizer's displayUUID, empty for Sidecar's

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
// Virtualization's USB touch screen: four Finger collections of contact identifier (6 bits), in range, tip switch and X/Y
// 0..32767; five bytes a finger, no report ID.
#define FINGER \
  0x05, 0x0d, 0x09, 0x22, 0xa1, 0x02, 0x09, 0x38, 0x75, 0x06, 0x95, 0x01, 0x81, 0x02, \
  0x09, 0x32, 0x09, 0x33, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x02, 0x81, 0x02, \
  0x05, 0x01, 0x09, 0x30, 0x09, 0x31, 0x15, 0x00, 0x26, 0xff, 0x7f, 0x75, 0x10, 0x95, 0x02, 0x81, 0x02, 0xc0,
const uint8_t touchDescriptor[] = {0x05, 0x0d, 0x09, 0x04, 0xa1, 0x01, FINGER FINGER FINGER FINGER 0xc0};
#undef FINGER
static_assert(sizeof(touchDescriptor) == 191, "Virtualization's descriptor");

// The built-in digitizer speaks Apple's multitouch protocol, as a touch screen Mac's does to AppleMultitouchDriver (its
// AppleMultitouchHIDService takes the device's IOHIDInterface) and to HSTouchHIDService.plugin in WindowServer (whose frame parser
// reads path frames, as the frames its sensing algorithms make of the touch controller's images):
//   - feature reports by mtReportID, the report ID echoed in front: 0xDB all of them at once ([1] then [u16 length with the ID][ID]
//     [payload] each), 0xD1 family ID, 0xD3 rDEVICE_BASIC_INFO (endianness 1 = little, rows, columns, bcdVersion big-endian, max
//     packet size), 0xD9 the surface in hundredths of a mm (width, height, then the s16 bounds xmin ymin xmax ymax that contacts are
//     normalized against), 0x7F status;
//   - input reports 0x44, a path frame: a 25-byte header (ID, frame number, header length, version 2, u32 milliseconds, image
//     length 0, path count, path size) and a 30-byte path each (path ID, stage, finger 1-5, hand, s16 X/Y in hundredths of a mm with
//     Y up, s16 velocities in eighths of a mm/s, radii, orientation, Q8 size and density).
// No region descriptor (0xD0): MultitouchSupport makes one of rows x columns; the family is none of its known ones (their pitch
// tables are a trackpad's), so the default.
namespace mt {
enum : uint8_t { status = 0x7f, family = 0xd1, basicInfo = 0xd3, surface = 0xd9, all = 0xdb, pathFrame = 0x44 };
enum : uint8_t { startInRange = 1, makeTouch = 3, touching = 4, breakTouch = 5, outOfRange = 7 };   // path stages
constexpr uint8_t familyId = 0x30, rows = 20, columns = 32;
constexpr unsigned headerSize = 25, pathSize = 30;
constexpr uint32_t width = 30200, height = 19600;   // a 14-inch touch screen's, hundredths of a mm

void put16(uint8_t *p, uint32_t value) { p[0] = static_cast<uint8_t>(value); p[1] = static_cast<uint8_t>(value >> 8); }
void put32(uint8_t *p, uint32_t value) { put16(p, value); put16(p + 2, value >> 16); }

// A feature report's payload (no report ID) and its length, 0 if there is no such report.
unsigned property(uint8_t id, uint8_t *p)
{
  switch (id) {
  case status:
    memset(p, 0, 4);
    return 4;
  case family:
    p[0] = familyId;
    return 1;
  case basicInfo:
    memset(p, 0, 14);
    p[0] = 1;
    p[1] = rows;
    p[2] = columns;
    p[3] = 0x01;   // bcdVersion 1.00
    put32(p + 8, 1024);
    return 14;
  case surface:
    put32(p, width);
    put32(p + 4, height);
    put16(p + 8, 0);
    put16(p + 10, 0);
    put16(p + 12, width);
    put16(p + 14, height);
    return 16;
  case all: {
    unsigned n = 1;
    p[0] = 1;
    static const uint8_t ids[] = {family, basicInfo, surface, status};
    for (uint8_t each : ids) {
      unsigned length = property(each, p + n + 3);
      put16(p + n, length + 1);
      p[n + 2] = each;
      n += 3 + length;
    }
    return n;
  }
  }
  return 0;
}
}  // namespace mt

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
  uint8_t last[5 * fingers] = {};
  // The digitizer's paths as last sent: where (virtio-input's units, then hundredths of a mm) and when.
  struct { bool down = false; int32_t x = 0, y = 0, mmX = 0, mmY = 0; uint32_t milliseconds = 0; } sent[maxSlots];
  uint8_t frame = 0;
  uint32_t milliseconds = 0;
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
  // The digitizer is Apple's as Virtualization's touch screen: AppleMultitouchDriver's "AppleMultitouchHIDService (0x0D,0x04)"
  // personality takes an IOHIDInterface of that usage and manufacturer, and its own product ID keeps it from DroidVMHIDEventDriver's.
  OSString *newManufacturerString() const override { return OSString::withCString(digitizer() ? "Apple" : "DroidVM"); }
  OSString *newProductString() const override;
  OSNumber *newVendorIDNumber() const override { return OSNumber::withNumber(virtio_pci::vendorId, 32); }
  OSNumber *newProductIDNumber() const override { return OSNumber::withNumber(digitizer() ? 0x1053 : 0x1052, 32); }
  OSNumber *newLocationIDNumber() const override { return OSNumber::withNumber(0x44560000 | fIndex, 32); }
  OSNumber *newPrimaryUsagePageNumber() const override { return OSNumber::withNumber(digitizer() ? 0x0d : kHIDPage_GenericDesktop, 32); }
  OSNumber *newPrimaryUsageNumber() const override;
  IOReturn getReport(IOMemoryDescriptor *report, IOHIDReportType reportType, IOOptionBits options) override;
  IOReturn setReport(IOMemoryDescriptor *report, IOHIDReportType reportType, IOOptionBits options) override;
  bool digitizer() const { return fDevice->kind == Kind::touch && !gTouchTablet; }
};

OSDefineMetaClassAndStructors(DroidVMHIDDevice, IOHIDDevice)

// AppleMultitouchHIDService's feature reports (the report ID in the options): the reply goes in front of the buffer it lends,
// whose length then says how much there is.
IOReturn DroidVMHIDDevice::getReport(IOMemoryDescriptor *report, IOHIDReportType reportType, IOOptionBits options)
{
  if (!digitizer() || !report)
    return IOHIDDevice::getReport(report, reportType, options);
  uint8_t bytes[128];
  const uint8_t id = static_cast<uint8_t>(options);
  unsigned length = mt::property(id, bytes + 1);
  if (!length)
    return kIOReturnUnsupported;
  bytes[0] = id;
  ++length;
  if (length > report->getLength())
    return kIOReturnNoSpace;
  report->writeBytes(0, bytes, length);
  if (IOBufferMemoryDescriptor *buffer = OSDynamicCast(IOBufferMemoryDescriptor, report))
    buffer->setLength(length);
  return kIOReturnSuccess;
}

IOReturn DroidVMHIDDevice::setReport(IOMemoryDescriptor *report, IOHIDReportType reportType, IOOptionBits options)
{
  if (!digitizer() || !report)
    return IOHIDDevice::setReport(report, reportType, options);
  return kIOReturnSuccess;   // nothing to set: the device has no modes
}

IOReturn DroidVMHIDDevice::newReportDescriptor(IOMemoryDescriptor **descriptor) const
{
  const uint8_t *bytes = fDevice->kind == Kind::keyboard ? keyboardDescriptor : fDevice->kind == Kind::mouse ? mouseDescriptor
                         : digitizer() ? touchDescriptor : tabletDescriptor;
  size_t length = fDevice->kind == Kind::keyboard ? sizeof(keyboardDescriptor) : fDevice->kind == Kind::mouse ? sizeof(mouseDescriptor)
                  : digitizer() ? sizeof(touchDescriptor) : sizeof(tabletDescriptor);
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
  return OSNumber::withNumber(fDevice->kind == Kind::keyboard ? kHIDUsage_GD_Keyboard : digitizer() ? 0x04 : kHIDUsage_GD_Mouse, 32);
}

class DroidVMInput : public IOService {
  OSDeclareDefaultStructors(DroidVMInput)

  IOMemoryMap *fEcam = nullptr;
  DroidVMInputDevice fDevices[maxDevices];
  unsigned fCount = 0;
  // droidvm-input-times=1 (diagnostics, research/debug-2026-10-28): the times (mach_absolute_time) of the last 256 pointer and touch
  // reports, published as the ReportTimes property (the count, then the ring) for WindowServer's latency rows.
  bool fRecordTimes = false;
  uint64_t fUserActiveAt = 0;   // mach_absolute_time of the last requestUserActive
  uint64_t fTimes[257] = {};
  unsigned fPublished = 0;

  void recordTime(DroidVMInputDevice &d) { if (fRecordTimes && d.kind != Kind::keyboard) fTimes[1 + fTimes[0]++ % 256] = mach_absolute_time(); }
  static void pollThread(void *self, wait_result_t);
  void poll(DroidVMInputDevice &d);
  void event(DroidVMInputDevice &d, const Event &e);
  void report(DroidVMInputDevice &d);
  void multitouch(DroidVMInputDevice &d);
  void userActive();
  void pathFrame(DroidVMInputDevice &d, const uint8_t *stages);
  void describe();
  static bool multitouchPublished(void *target, void *refCon, IOService *service, IONotifier *notifier);

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

OSDictionary *multitouchProperties()
{
  OSDictionary *properties = OSDictionary::withCapacity(3), *plugins = OSDictionary::withCapacity(1);
  OSDictionary *algs = OSDictionary::withCapacity(4);
  OSArray *config = OSArray::withCapacity(1);
  OSString *framework = OSString::withCString("SensingAlgsService.framework"), *interface = OSString::withCString("SASInterfaceTouch");
  OSNumber *platform = OSNumber::withNumber(0xe0, 32), *packet = OSNumber::withNumber(0xff60, 32);
  const bool made = properties && plugins && algs && config && framework && interface && platform && packet;
  if (made) {
    algs->setObject("SAFrameworkName", framework);
    algs->setObject("SASInterfaceClassName", interface);
    algs->setObject("PlatformID", platform);
    algs->setObject("MaxPacketSize", packet);
    config->setObject(algs);
    properties->setObject("HSTouchHIDService", kOSBooleanTrue);
    properties->setObject("IOCFPlugInTypes", plugins);
    properties->setObject("SensingAlgsConfig", config);
  }
  OSSafeReleaseNULL(plugins);
  OSSafeReleaseNULL(algs);
  OSSafeReleaseNULL(config);
  OSSafeReleaseNULL(framework);
  OSSafeReleaseNULL(interface);
  OSSafeReleaseNULL(platform);
  OSSafeReleaseNULL(packet);
  if (!made)
    OSSafeReleaseNULL(properties);
  return properties;
}

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
  uint32_t touchDigitizer = 0;
  gTouchTablet = !(PE_parse_boot_argn("droidvm-touch-digitizer", &touchDigitizer, sizeof(touchDigitizer)) && touchDigitizer);
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
    const bool ready = hid && hid->init(nullptr);
    uint32_t touchSidecar = 0;
    if (ready && hid->digitizer() && !(PE_parse_boot_argn("droidvm-touch-sidecar", &touchSidecar, sizeof(touchSidecar)) && touchSidecar)) {
      hid->setProperty(kIOHIDBuiltInKey, true);   // the touch processor takes a display's touches from a built-in one only
      // SkyLight's handle_digitizer_added drops a digitizer whose displayUUID (a CFUUID string) names no display it knows:
      // DroidVMDisplay's IOMFBUUID unless droidvm-touch-display-uuid says otherwise.
      strlcpy(gDisplayUUID, "44726F69-6456-4D00-0000-000000000001", sizeof(gDisplayUUID));
      PE_parse_boot_argn("droidvm-touch-display-uuid", gDisplayUUID, sizeof(gDisplayUUID) - 1);
      hid->setProperty("displayUUID", gDisplayUUID);
      // What the touch MacBook Pro's touch controller (its firmware's "kiwi" interface) has AppleMultitouchHIDService give its
      // AppleMultitouchDevice, which looks for the property up its providers: HSTouchHIDService.plugin rather than the personality's
      // MultitouchHID.plugin, whose sensing algorithms stage is the generic touch one (the second of the controller's; the first,
      // SensingAlgsKiwi_AP, makes path frames of its images).
      if (OSDictionary *properties = multitouchProperties()) {
        hid->setProperty("DefaultMultitouchProperties", properties);
        properties->release();
      }
    }
    // droidvm-touch-sidecar=1: neither, as Sidecar's digitizer: WindowServer (WSSidecar2) then makes it a WSSidecar2HIDService on
    // the main display at its first event, whose touches its modern Sidecar processor delivers as direct touches.
    if (!ready || !hid->attach(this)) {
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
  // The event service WindowServer gets for the digitizer is AppleMultitouchDevice (under AppleMultitouchHIDService, on the device's
  // IOHIDInterface): SkyLight's handle_digitizer_added takes a digitizer only with a displayUUID, which on a Mac with a touch screen
  // its display has given it.
  if (gDisplayUUID[0]) {
    OSDictionary *matching = IOService::serviceMatching("AppleMultitouchDevice");
    if (matching)
      IOService::addMatchingNotification(gIOFirstPublishNotification, matching, multitouchPublished, this, nullptr);
    OSSafeReleaseNULL(matching);
  }
  if (!fCount)
    return false;
  uint32_t recordTimes = 0;
  fRecordTimes = PE_parse_boot_argn("droidvm-input-times", &recordTimes, sizeof(recordTimes)) && recordTimes;
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
    if (input->fRecordTimes && tick % (100 / pollMs) == 0 && input->fTimes[0] != input->fPublished) {
      input->fPublished = static_cast<unsigned>(input->fTimes[0]);
      if (OSData *times = OSData::withBytes(input->fTimes, sizeof(input->fTimes))) {
        input->setProperty("ReportTimes", times);
        times->release();
      }
    }
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
  uint8_t bytes[sizeof(d.last)] = {};
  unsigned length;
  if (d.kind == Kind::touch && !gTouchTablet) {
    multitouch(d);
    return;
  } else if (d.kind == Kind::keyboard) {
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
          recordTime(d);
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
    recordTime(d);
    d.hid->handleReport(report);
    report->release();
  }
}

// The digitizer's slots as multitouch paths (slot i is path i + 1), a frame when any finger lands, lifts or moves. A finger
// that lands starts in range and makes touch, one that lifts breaks touch and goes out of range: two frames, a millisecond apart.
void DroidVMInput::multitouch(DroidVMInputDevice &d)
{
  uint8_t first[maxSlots] = {}, second[maxSlots] = {};
  bool changed = false, twice = false, landed = false;
  for (unsigned i = 0; i < maxSlots; ++i) {
    const auto &s = d.slots[i];
    auto &sent = d.sent[i];
    const bool down = s.id >= 0;
    if (down && !sent.down) {
      first[i] = mt::startInRange;
      second[i] = mt::makeTouch;
      changed = twice = landed = true;
    } else if (!down && sent.down) {
      first[i] = mt::breakTouch;
      second[i] = mt::outOfRange;
      changed = twice = true;
    } else if (down) {
      first[i] = second[i] = mt::touching;
      changed |= s.x != sent.x || s.y != sent.y;
    }
    if (down) {
      sent.x = s.x;
      sent.y = s.y;
    }
    sent.down = down;
  }
  if (!changed || !d.hid)
    return;
  if (landed)
    userActive();
  pathFrame(d, first);
  if (twice)
    pathFrame(d, second);
}

// A finger landing is user activity, as a key or a click is. The touch screen's events are not to the power manager: with the display
// off after the idle time (DroidVMDisplay's "display off"), the screen stayed dark under the finger and the VM looked frozen. powerd
// turns the display on for requestUserActive; at most once a second.
void DroidVMInput::userActive()
{
  const uint64_t now = mach_absolute_time();
  uint64_t since = 0;
  absolutetime_to_nanoseconds(now - fUserActiveAt, &since);
  if (fUserActiveAt && since < NSEC_PER_SEC)
    return;
  fUserActiveAt = now;
  if (IOPMrootDomain *root = getPMRootDomain())
    root->requestUserActive(this, "touch");
}

void DroidVMInput::pathFrame(DroidVMInputDevice &d, const uint8_t *stages)
{
  uint64_t nanoseconds;
  absolutetime_to_nanoseconds(mach_absolute_time(), &nanoseconds);
  const uint32_t now = static_cast<uint32_t>(nanoseconds / 1000000);
  d.milliseconds = now > d.milliseconds ? now : d.milliseconds + 1;
  uint8_t bytes[mt::headerSize + mt::pathSize * maxSlots] = {};
  unsigned paths = 0;
  for (unsigned i = 0; i < maxSlots; ++i) {
    if (!stages[i])
      continue;
    auto &sent = d.sent[i];
    uint8_t *p = bytes + mt::headerSize + mt::pathSize * paths++;
    const int64_t sx = scale(sent.x, d.minX, d.spanX), sy = scale(sent.y, d.minY, d.spanY);
    const int32_t x = static_cast<int32_t>(sx * mt::width / (tabletRange - 1));
    const int32_t y = static_cast<int32_t>(mt::height - sy * mt::height / (tabletRange - 1));
    // The velocity since the last frame a finger was touching in, eighths of a mm/s: 80 per hundredth of a mm a millisecond.
    int32_t vx = 0, vy = 0;
    if (stages[i] == mt::touching && d.milliseconds > sent.milliseconds) {
      const int32_t dt = static_cast<int32_t>(d.milliseconds - sent.milliseconds);
      vx = (x - sent.mmX) * 80 / dt;
      vy = (y - sent.mmY) * 80 / dt;
      vx = vx < -32767 ? -32767 : vx > 32767 ? 32767 : vx;
      vy = vy < -32767 ? -32767 : vy > 32767 ? 32767 : vy;
    }
    sent.mmX = x;
    sent.mmY = y;
    sent.milliseconds = d.milliseconds;
    p[0] = static_cast<uint8_t>(i + 1);
    p[1] = stages[i];
    p[2] = static_cast<uint8_t>(i < 4 ? i + 2 : 1);   // index, middle, ring, little finger, then thumbs
    p[3] = 1;                                         // a hand
    mt::put16(p + 4, static_cast<uint32_t>(x));
    mt::put16(p + 6, static_cast<uint32_t>(y));
    mt::put16(p + 8, static_cast<uint32_t>(vx));
    mt::put16(p + 10, static_cast<uint32_t>(vy));
    mt::put16(p + 12, 400);     // radii: 4 and 3.5 mm
    mt::put16(p + 14, 350);
    mt::put16(p + 16, 16384);   // upright
    mt::put16(p + 18, 256);     // size 1
    mt::put16(p + 20, 256);     // density 1
  }
  bytes[0] = mt::pathFrame;
  bytes[1] = d.frame++;
  bytes[2] = mt::headerSize;
  bytes[3] = 2;
  mt::put32(bytes + 4, d.milliseconds);
  bytes[16] = static_cast<uint8_t>(paths);
  bytes[17] = mt::pathSize;
  const unsigned length = mt::headerSize + mt::pathSize * paths;
  IOBufferMemoryDescriptor *report = IOBufferMemoryDescriptor::withBytes(bytes, length, kIODirectionNone);
  if (report) {
    recordTime(d);
    d.hid->handleReport(report);
    report->release();
  }
}

bool DroidVMInput::multitouchPublished(void *, void *, IOService *service, IONotifier *)
{
  for (IOService *provider = service->getProvider(); provider; provider = provider->getProvider())
    if (OSDynamicCast(DroidVMHIDDevice, provider)) {
      service->setProperty("displayUUID", gDisplayUUID);
      IOLog("DroidVMInput: %s gets displayUUID %s\n", service->getMetaClass()->getClassName(), gDisplayUUID);
      break;
    }
  return true;
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
    OSNumber *page = service ? OSDynamicCast(OSNumber, service->getProperty(kIOHIDPrimaryUsagePageKey)) : nullptr;
    OSNumber *usage = service ? OSDynamicCast(OSNumber, service->getProperty(kIOHIDPrimaryUsageKey)) : nullptr;
    IOLog("DroidVMInput: event service %s on %s, %u user client(s), usage %#x/%#x, built-in %d\n", object->getMetaClass()->getClassName(),
          provider ? provider->getMetaClass()->getClassName() : "-", users, page ? page->unsigned32BitValue() : 0,
          usage ? usage->unsigned32BitValue() : 0, service && service->getProperty(kIOHIDBuiltInKey) == kOSBooleanTrue);
  }
  OSSafeReleaseNULL(services);
}
