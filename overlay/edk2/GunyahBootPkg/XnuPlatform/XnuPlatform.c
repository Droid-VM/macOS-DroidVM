// SPDX-License-Identifier: BSD-2-Clause-Patent
// Publish a complete source-kernel ADT only after checking this boot's FDT.
#include <Uefi.h>
#include <Guid/Fdt.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/FdtLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiLib.h>
#include <Protocol/LoadedImage.h>
#include <Protocol/SimpleFileSystem.h>

typedef struct {
  CONST CHAR8 *Path;
  CONST CHAR8 *Name;
  CONST UINT8 *Data;
  UINT32 Length;
} EXPECTED_PROPERTY;
typedef struct { CONST CHAR8 *Path; UINT32 Children; } EXPECTED_NODE;
#include <GunyahXnuInputs.h>

STATIC EFI_STATUS Refuse(EFI_STATUS Status) {
  // UniXNU continues after driver failures. Stop here so an older sidecar on
  // a reused disk cannot bypass validation. The host owns the run timeout.
  Print(L"GUNYAH-XNU: boot refused: %r\n", Status);
  CpuDeadLoop();
  return Status;
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
  // A partially written ADT must never become loader input.
  if (EFI_ERROR(Status)) { File->Delete(File); return Status; }
  return File->Close(File);
}

STATIC EFI_STATUS Validate(CONST VOID *Fdt) {
  UINTN Index;
  UINT64 Frequency, Mmfr1;
  if (FdtNodeOffsetByCompatible(Fdt, -1, "restricted-dma-pool") >= 0) return EFI_UNSUPPORTED;
  __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(Frequency));
  if (Frequency != ExpectedFrequency) return EFI_UNSUPPORTED;
  // The Gunyah kernel enables native PAN for copyin/copyout and context switches.
  __asm__ volatile("mrs %0, id_aa64mmfr1_el1" : "=r"(Mmfr1));
  if (((Mmfr1 >> 20) & 15) == 0 || ((Mmfr1 >> 20) & 15) > 3) return EFI_UNSUPPORTED;
  Print(L"GUNYAH-XNU: native PAN supported; ID_AA64MMFR1=0x%lx\n", Mmfr1);
  for (Index = 0; Index < ARRAY_SIZE(ExpectedNodes); Index++) {
    INT32 Node = FdtPathOffset(Fdt, ExpectedNodes[Index].Path);
    INT32 Child;
    UINT32 Count = 0;
    if (Node < 0) return EFI_NOT_FOUND;
    for (Child = FdtFirstSubnode(Fdt, Node); Child >= 0; Child = FdtNextSubnode(Fdt, Child)) Count++;
    if (Count != ExpectedNodes[Index].Children) return EFI_UNSUPPORTED;
  }
  for (Index = 0; Index < ARRAY_SIZE(ExpectedProperties); Index++) {
    CONST EXPECTED_PROPERTY *P = &ExpectedProperties[Index];
    INT32 Length, Node = FdtPathOffset(Fdt, P->Path);
    CONST VOID *Data;
    if (Node < 0) return EFI_NOT_FOUND;
    Data = FdtGetProp(Fdt, Node, P->Name, &Length);
    if (!Data || Length != (INT32)P->Length || CompareMem(Data, P->Data, P->Length)) {
      Print(L"GUNYAH-XNU: resource changed: %a/%a\n", P->Path, P->Name);
      return EFI_UNSUPPORTED;
    }
  }
  return EFI_SUCCESS;
}

EFI_STATUS EFIAPI XnuPlatformEntry(EFI_HANDLE Image, EFI_SYSTEM_TABLE *SystemTable) {
  VOID *Fdt;
  EFI_LOADED_IMAGE_PROTOCOL *Loaded;
  EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *Fs;
  EFI_FILE_PROTOCOL *Root;
  EFI_STATUS Status;
  EFI_PHYSICAL_ADDRESS PanicAddress = 0;
  (VOID)SystemTable;
  Status = EfiGetSystemConfigurationTable(&gFdtTableGuid, &Fdt);
  if (EFI_ERROR(Status) || FdtCheckHeader(Fdt) || FdtTotalSize(Fdt) > SIZE_2MB) return Refuse(EFI_NOT_FOUND);
  Status = gBS->HandleProtocol(Image, &gEfiLoadedImageProtocolGuid, (VOID **)&Loaded);
  if (EFI_ERROR(Status)) return Refuse(Status);
  Status = gBS->HandleProtocol(Loaded->DeviceHandle, &gEfiSimpleFileSystemProtocolGuid, (VOID **)&Fs);
  if (EFI_ERROR(Status)) return Refuse(Status);
  Status = Fs->OpenVolume(Fs, &Root);
  if (EFI_ERROR(Status)) return Refuse(Status);
  Status = Save(Root, L"\\xnu-final.dtb", Fdt, FdtTotalSize(Fdt));
  if (!EFI_ERROR(Status)) Status = Validate(Fdt);
  if (!EFI_ERROR(Status)) {
    Status = gBS->AllocatePages(AllocateAnyPages, EfiReservedMemoryType, EFI_SIZE_TO_PAGES(PanicBytes), &PanicAddress);
    if (!EFI_ERROR(Status)) {
      ZeroMem((VOID *)(UINTN)PanicAddress, PanicBytes);
      WriteUnaligned64((UINT64 *)(KernelAdt + PanicRegOffset), PanicAddress);
      Print(L"GUNYAH-XNU: reserved panic RAM 0x%lx + 0x%lx\n", PanicAddress, (UINT64)PanicBytes);
    }
  }
  if (!EFI_ERROR(Status)) Status = Save(Root, L"\\EFI\\UniXNU\\Payloads\\kernel.macho.adt", KernelAdt, sizeof(KernelAdt));
  Root->Close(Root);
  if (EFI_ERROR(Status)) return Refuse(Status);
  Print(L"GUNYAH-XNU: final FDT validated; publish ADT: %r; CNTFRQ=%lu\n", Status, ExpectedFrequency);
  return Status;
}
