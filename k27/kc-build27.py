#!/usr/bin/env python3
"""scripts/kc-build.py for the macOS 27 kernelcache: same arguments (KC KERNEL OUTPUT --keep ... --native ...), with kc27's layout.

The top-level segment starts come from k27/segaddrs.json (k27/kc27-layout.py, the layout the kernel was linked with).
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('kc_build', HERE.parent / 'scripts/kc-build.py')
source = spec.loader.get_data(spec.origin).decode()
source = source[:source.rindex('\nmain()')]          # the module without its trailing main() call
module = importlib.util.module_from_spec(spec)
sys.modules['kc_build'] = module
sys.path.insert(0, str(HERE.parent / 'scripts'))
exec(compile(source, spec.origin, 'exec'), module.__dict__)

layout = json.loads((HERE / 'segaddrs.json').read_text())
module.DATA_CONST_START = layout['DATA_CONST_START']
module.DATA_START = layout['DATA_START']
# No kept kext's bytes are patched: Sandbox's Data volume prefix (/System/Volumes/Data) was rewritten to /private/var/.data until
# the root's writable entries became real firmlinks (kern_exec.c native_owner_firmlinks_prepare).
# AMFI's only reference to PAGE_SHIFT_CONST (its GOT slot, used by CoreEntitlements' CEElementIterate alone) goes to the kernel's
# k27_amfi_page_shift (31): that check fails when sp is within 0x80 of a page start, a fixed outcome on a fixed call chain over page
# aligned kernel stacks, and with our kernel's frames every spawn's entitlement dictionary copy failed ("failed to create OSDictionary
# copy: 14" panic). The kext's bytes stay as shipped.
# The slot is the second of AMFI's __DATA_CONST,__got in the 27.2 vma2 kernelcache (0xfffffe0007b439c8 in 27.0.1's).
module.KEPT_POINTER_REBINDS = [(0xfffffe0007b4bbc8, '_k27_amfi_page_shift')]

# Symbols of the native kexts as linked (for k27/sym.py), next to the output: OUTPUT.natives.json {symbol: address}.
natives = {}
link = module.kc_native.link


def recording_link(*args, **kwargs):
    linked = link(*args, **kwargs)
    natives.update(linked['symbols'])
    return linked


module.kc_native.link = recording_link
module.main()
output = Path([a for a in sys.argv[1:] if not a.startswith('-')][2])
output.with_suffix('.natives.json').write_text(json.dumps(natives))
