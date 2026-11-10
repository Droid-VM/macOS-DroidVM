#!/usr/bin/env python3
"""Build NativeRamBlock (the Data disk, overlay/kext/NativeRamBlock.json) as a native kext of the collection, with the Data store of
Droid-VM (overlay/kext/DroidVMDataStore.c: the changed pages go to /arm-io/data-store, crosvm's data-store.img).

    build-native-ram-block.py

The fork's driver opens its store when the kernel asks it for the Data volume (native_ram_block_volume_device). This kernel finds the
Data volume itself, by the UUID of its IOMedia (link_compat.c's native_ram_block_volume_seed), and never asks: the copy built here
opens the store once the disk is published (from a thread start() leaves, see publish below). Without the store every page written
stayed in kernel memory (kalloc.type.var4.4096 held 640 MiB by the login window). IOStorageFamily's ABI is the one of TARGET_OS_OSX (docs/xnu-12377-port.md,
NativeVirtioBlock): built without it, 35 slots of IOBlockStorageDevice's vtable differ and the storage stack panics.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'sources/UniXNU/drivers/NativeRamBlock'
OUT = ROOT / 'out/x12377/native-kexts/NativeRamBlock'
OUT.mkdir(parents=True, exist_ok=True)
text = (SOURCE / 'NativeRamBlock.cpp').read_text()
old = '  registerService();\n  return true;\n'
start = 'bool NativeRamBlock::start(IOService *provider)\n'
if text.count(old) != 1 or text.count(start) != 1:
    sys.exit(f'{SOURCE / "NativeRamBlock.cpp"}: the end of start() changed')
# The disk is published from a thread, once IOResources has matched IOBSD (start() runs inside that matching: NativeRamBlock and
# com_apple_filesystems_apfs both match IOResources with IOBSD). Published from start(), AppleAPFSContainer::start could run on the new
# disk first: it takes APFS's module lock and waits for IOResources matched with IOBSD, while that matching waits in
# com_apple_filesystems_apfs::start for the lock: a deadlock, and the root never appears. Once matched, the container never waits.
# docs/k27-real-disk-layout-plan.md P5: launchd's mount-phase-1 (apfs_boot_util) must mount the xART volume of
# the iBoot System Container and aborts without it; it takes for that container the APFS volume of role xART whose nearest plain
# IOMedia has the Content Hint of an ISC partition. This disk is a whole-disk container (IOBlockStorageDriver gives its IOMedia an
# empty hint), so the hint is put on that IOMedia once it appears, and the container holds the xART and Hardware volumes too.
publish = '''#include <kern/thread.h>
// build-native-ram-block.py: label the whole-disk IOMedia as an iBoot System Container partition (the union layout ignores it)
static void markSystemContainer(NativeRamBlock *ram)
{
  for (int i = 0; i < 300; i++) {
    IORegistryEntry *driver = ram->getChildEntry(gIOServicePlane);
    IORegistryEntry *media = driver ? driver->getChildEntry(gIOServicePlane) : nullptr;
    if (media && media->metaCast("IOMedia")) {
      media->setProperty("Content Hint", "69646961-6700-11AA-AA11-00306543ECAC");
      return;
    }
    IOSleep(100);
  }
}

// build-native-ram-block.py: publish the disk once IOResources has matched IOBSD (APFS deadlocks otherwise)
static void publishWhenBSDMatched(void *argument, wait_result_t)
{
  NativeRamBlock *ram = static_cast<NativeRamBlock *>(argument);
  if (OSDictionary *matching = IOService::resourceMatching(kIOBSDKey)) {
    if (IOService *resources = IOService::waitForMatchingService(matching)) resources->release();
    matching->release();
  }
  ram->registerService();
  ram->attachStore();   // this kernel never asks the driver for the Data volume
  markSystemContainer(ram);
  ram->release();
}

'''
staged = OUT / 'NativeRamBlock.cpp'
staged.write_text(text.replace(start, publish + start).replace(old, '''  retain();
  thread_t thread;
  if (kernel_thread_start(publishWhenBSDMatched, this, &thread) != KERN_SUCCESS) {
    release();
    return false;
  }
  thread_deallocate(thread);
  return true;
'''))
subprocess.run(['python3', str(ROOT / 'scripts/build-native-kext.py'), 'NativeRamBlock', str(staged),
                str(ROOT / 'overlay/kext/NativeKextGlue.cpp'), str(ROOT / 'overlay/kext/DroidVMDataStore.c'),
                '-I', str(SOURCE), '-I', str(ROOT / 'out/x12377/storage-abi/include'), '-I', str(ROOT / 'out/x12377/xnu-m/osfmk'),
                '-D', 'U:TARGET_OS_OSX', '-D', 'TARGET_OS_OSX=1'], check=True)
