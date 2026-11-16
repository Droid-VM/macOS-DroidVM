// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <Uefi.h>
#include <Guid/Fdt.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/FdtLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiLib.h>
#include <Protocol/LoadedImage.h>
#include <Protocol/SimpleFileSystem.h>
#include "../Include/ProbePlatform.h"

STATIC UINT8 Tree[1024];
STATIC UINTN Used;

STATIC VOID Word(UINT32 Value) {
  CopyMem(Tree + Used, &Value, sizeof(Value)); Used += sizeof(Value);
}

STATIC VOID Property(CONST CHAR8 *Name, CONST VOID *Data, UINT32 Length) {
  // Only the fixed bounded schema below is emitted (less than 512 bytes).
  ZeroMem(Tree + Used, 32); CopyMem(Tree + Used, Name, AsciiStrLen(Name)); Used += 32;
  Word(Length); CopyMem(Tree + Used, Data, Length); Used = ALIGN_VALUE(Used + Length, 4);
}

STATIC BOOLEAN Reg(CONST VOID *Fdt, INT32 Node, UINTN Index, UINT64 *Base, UINT64 *Size) {
  INT32 Length;
  CONST UINT32 *Cells = FdtGetProp(Fdt, Node, "reg", &Length);
  if (Node < 0 || !Cells || Length < (INT32)((Index + 1) * 16)) return FALSE;
  Cells += Index * 4;
  *Base = LShiftU64(Fdt32ToCpu(Cells[0]), 32) | Fdt32ToCpu(Cells[1]);
  *Size = LShiftU64(Fdt32ToCpu(Cells[2]), 32) | Fdt32ToCpu(Cells[3]);
  return *Size != 0;
}

STATIC BOOLEAN StringIs(CONST VOID *Fdt, INT32 Node, CONST CHAR8 *Key, CONST CHAR8 *Value) {
  INT32 Length;
  CONST CHAR8 *Data = FdtGetProp(Fdt, Node, Key, &Length);
  return Data && Length == (INT32)AsciiStrSize(Value) && CompareMem(Data, Value, Length) == 0;
}

STATIC EFI_STATUS Save(EFI_FILE_PROTOCOL *Root, CHAR16 *Name, CONST VOID *Data, UINTN Size) {
  EFI_FILE_PROTOCOL *File;
  EFI_STATUS Status;
  UINTN Actual = Size;
  Status = Root->Open(Root, &File, Name, EFI_FILE_MODE_READ, 0);
  if (!EFI_ERROR(Status)) { File->Close(File); return EFI_ALREADY_STARTED; }
  if (Status != EFI_NOT_FOUND) return Status;
  Status = Root->Open(Root, &File, Name, EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE | EFI_FILE_MODE_CREATE, 0);
  if (EFI_ERROR(Status)) return Status;
  Status = File->Write(File, &Actual, (VOID *)Data);
  if (!EFI_ERROR(Status) && Actual != Size) Status = EFI_DEVICE_ERROR;
  if (!EFI_ERROR(Status)) Status = File->Flush(File);
  EFI_STATUS Closed = File->Close(File);
  return EFI_ERROR(Status) ? Status : Closed;
}

EFI_STATUS EFIAPI PlatformEntry(EFI_HANDLE Image, EFI_SYSTEM_TABLE *SystemTable) {
  VOID *Fdt;
  PROBE_PLATFORM P = { .version = 1 };
  EFI_LOADED_IMAGE_PROTOCOL *Loaded;
  EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *Fs;
  EFI_FILE_PROTOCOL *Root;
  EFI_STATUS Status;
  INT32 Node, Length;
  UINT64 Size;
  CONST UINT32 *Cells;
  CONST CHAR8 *Path;
  UINT64 Window = SIZE_256MB;
  (VOID)SystemTable;
  Status = EfiGetSystemConfigurationTable(&gFdtTableGuid, &Fdt);
  if (EFI_ERROR(Status) || FdtCheckHeader(Fdt) || FdtTotalSize(Fdt) > SIZE_2MB) return EFI_NOT_FOUND;
  Cells = FdtGetProp(Fdt, 0, "#address-cells", &Length);
  if (!Cells || Length != 4 || Fdt32ToCpu(*Cells) != 2) return EFI_UNSUPPORTED;
  Cells = FdtGetProp(Fdt, 0, "#size-cells", &Length);
  if (!Cells || Length != 4 || Fdt32ToCpu(*Cells) != 2) return EFI_UNSUPPORTED;
  if (FdtNodeOffsetByCompatible(Fdt, -1, "restricted-dma-pool") >= 0) return EFI_UNSUPPORTED;
  Node = FdtPathOffset(Fdt, "/chosen");
  Path = FdtGetProp(Fdt, Node, "stdout-path", &Length);
  if (!Path || Length < 2 || Path[Length - 1] || Path[0] != '/') return EFI_UNSUPPORTED;
  Node = FdtPathOffset(Fdt, Path);
  if (!StringIs(Fdt, Node, "compatible", "ns16550a") || !Reg(Fdt, Node, 0, &P.uart, &Size) || Size != 8) return EFI_UNSUPPORTED;
  Cells = FdtGetProp(Fdt, Node, "reg-shift", &Length);
  if (Cells && (Length != 4 || Fdt32ToCpu(*Cells) != 0)) return EFI_UNSUPPORTED;
  Cells = FdtGetProp(Fdt, Node, "reg-io-width", &Length);
  if (Cells && (Length != 4 || Fdt32ToCpu(*Cells) != 1)) return EFI_UNSUPPORTED;
  Node = FdtNodeOffsetByCompatible(Fdt, -1, "arm,gic-v3");
  if (!Reg(Fdt, Node, 0, &P.gicd, &Size) || Size < 0x10000 ||
      !Reg(Fdt, Node, 1, &P.gicr, &Size) || Size < 0x20000) return EFI_UNSUPPORTED;
  Node = FdtPathOffset(Fdt, "/memory");
  if (!Reg(Fdt, Node, 0, &P.ram_base, &P.ram_size)) return EFI_UNSUPPORTED;
  Node = FdtNodeOffsetByCompatible(Fdt, -1, "simple-framebuffer");
  if (!Reg(Fdt, Node, 0, &P.fb_base, &P.fb_size) || !StringIs(Fdt, Node, "format", "a8r8g8b8")) return EFI_UNSUPPORTED;
  Node = FdtNodeOffsetByCompatible(Fdt, -1, "arm,armv8-timer");
  Cells = FdtGetProp(Fdt, Node, "interrupts", &Length);
  // Third interrupt specifier is the virtual timer. FDT PPI number + 16 = INTID.
  if (!Cells || Length < 36 || Fdt32ToCpu(Cells[6]) != 1 || Fdt32ToCpu(Cells[7]) >= 16 ||
      (Fdt32ToCpu(Cells[8]) & 15) != 8) return EFI_UNSUPPORTED;
  P.timer_irq = Fdt32ToCpu(Cells[7]) + 16;
  Node = FdtNodeOffsetByCompatible(Fdt, -1, "arm,psci-0.2");
  if (!StringIs(Fdt, Node, "method", "hvc")) return EFI_UNSUPPORTED;
  __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(P.counter_freq));
  // Scope this first payload to a single 32-bit-addressable crosvm RAM bank.
  if (P.uart >= 0x40000000 || P.gicd >= 0x40000000 || P.gicr >= 0x40000000 ||
      P.ram_base < 0x80000000 || P.ram_size > 0x40000000 ||
      P.ram_base + P.ram_size > 0xc0000000 || P.fb_base < P.ram_base + P.ram_size ||
      P.fb_size > SIZE_2MB || P.fb_base + P.fb_size > 0xc0000000) return EFI_UNSUPPORTED;
  Word(1); Word(1); Property("name", "device-tree", 12);
  Word(3); Word(0); Property("name", "chosen", 7);
  Property("darwinboot-memory-size", &Window, sizeof(Window));
  Property("gunyah-probe", &P, sizeof(P));
  Status = gBS->HandleProtocol(Image, &gEfiLoadedImageProtocolGuid, (VOID **)&Loaded);
  if (EFI_ERROR(Status)) return Status;
  Status = gBS->HandleProtocol(Loaded->DeviceHandle, &gEfiSimpleFileSystemProtocolGuid, (VOID **)&Fs);
  if (EFI_ERROR(Status)) return Status;
  Status = Fs->OpenVolume(Fs, &Root);
  if (EFI_ERROR(Status)) return Status;
  Status = Save(Root, L"\\p1-final.dtb", Fdt, FdtTotalSize(Fdt));
  if (!EFI_ERROR(Status)) Status = Save(Root, L"\\EFI\\UniXNU\\Payloads\\kernel.macho.adt", Tree, Used);
  Root->Close(Root);
  Print(L"GUNYAH-PLATFORM: final FDT -> sidecar ADT %r; UART=%lx GICD=%lx GICR=%lx timer=%lu\n",
        Status, P.uart, P.gicd, P.gicr, P.timer_irq);
  return Status;
}
