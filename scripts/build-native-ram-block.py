#!/usr/bin/env python3
"""Build NativeRamBlock (the Data disk, overlay/kext/NativeRamBlock.json) as a native kext of the collection, with the Data store of
Droid-VM (overlay/kext/DroidVMDataStore.c: the changed pages go to /arm-io/data-store, crosvm's data-store.img).

    build-native-ram-block.py

The fork's driver opens its store when the kernel asks it for the Data volume (native_ram_block_volume_device). This kernel finds the
Data volume itself, by the UUID of its IOMedia (link_compat.c's native_ram_block_volume_seed), and never asks: the copy built here
opens the store at the end of start(), once the disk is published. Without the store every page written stayed in kernel memory
(kalloc.type.var4.4096 held 640 MiB by the login window). IOStorageFamily's ABI is the one of TARGET_OS_OSX (docs/xnu-12377-port.md,
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
if text.count(old) != 1:
    sys.exit(f'{SOURCE / "NativeRamBlock.cpp"}: the end of start() changed')
staged = OUT / 'NativeRamBlock.cpp'
staged.write_text(text.replace(old, '  registerService();\n  attachStore();   // build-native-ram-block.py: this kernel never asks the driver for the Data volume\n'
                                    '  return true;\n'))
subprocess.run(['python3', str(ROOT / 'scripts/build-native-kext.py'), 'NativeRamBlock', str(staged),
                str(ROOT / 'overlay/kext/NativeKextGlue.cpp'), str(ROOT / 'overlay/kext/DroidVMDataStore.c'),
                '-I', str(SOURCE), '-I', str(ROOT / 'out/x12377/storage-abi/include'), '-I', str(ROOT / 'out/x12377/xnu-m/osfmk'),
                '-D', 'U:TARGET_OS_OSX', '-D', 'TARGET_OS_OSX=1'], check=True)
