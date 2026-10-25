#!/usr/bin/env python3
"""Generate the C++ declarations of IOMobileFramebuffer and IOMobileFramebufferLegacy (IOMobileGraphicsFamily) from a kernelcache,
so a display driver can derive from IOMobileFramebufferLegacy as AppleParavirtDisplay does.

    gen-iomfb-abi.py KC OUTPUT.h

Every virtual slot is declared in the class that introduces it. The arm64e PAC diversity of a slot in a derived class's vtable is
the string discriminator (scripts/ptrauth_disc.py) of the introducing declaration's mangled name, so each slot's declaration is the
method of the collection's symbol tables (IOMobileGraphicsFamily, AppleParavirtGPU) that, qualified by the introducing class,
hashes to the diversity AppleParavirtDisplay's vtable has there: the name and parameter types are checked, not guessed, and
identical-code-folded aliases do not mislead it. The vtable a derived class emits names the base class's functions, which the
kext linker resolves in IOMobileGraphicsFamily. Mangled names carry no return type: a slot returns
IOReturn unless RETURNS says otherwise, which matters only for the slots a driver overrides or calls. The instance sizes come
from the classes' OSMetaClass constructors.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fileset_kc  # noqa: E402
from ptrauth_disc import discriminator  # noqa: E402

KEXT = 'com.apple.iokit.IOMobileGraphicsFamily'
IOSERVICE_SLOTS = 272
CLASSES = ('IOMobileFramebuffer', 'IOMobileFramebufferLegacy')
# Return types of the slots a driver overrides or calls (from AppleParavirtDisplay's and IOMobileFramebufferLegacy's code).
RETURNS = {
    'has_multiple_dcp': 'void', 'supports_write_debug_info': 'bool', 'is_main_display': 'bool', 'display_width': 'uint32_t',
    'display_height': 'uint32_t', 'start_hardware': 'bool', 'are_timings_enabled': 'bool', 'async_swap_supported': 'bool',
    'swap_begin_gated': 'IOReturn', 'stop_hardware_gated': 'IOReturn', 'do_power_state_change_gated': 'IOReturn',
    'get_current_absolute_time': 'uint64_t', 'global_index': 'uint32_t', 'keep_swaps_on_disconnect': 'bool',
    'getDisplayedDataAP': 'void *', 'get_diags_handler': 'void *', 'protection_bits': 'uint32_t', 'syncRate': 'uint32_t',
    'getActivePeriod_us': 'uint32_t', 'getDefaultVBLDelta': 'uint64_t', 'isReplaying': 'bool', 'aot_enabled': 'bool',
    'vmaod_enabled': 'bool', 'is_dual_pipe_config': 'bool', 'need_swap_notify': 'bool', 'flush_rtps': 'void',
    'idle_surface_release': 'void', 'finfo_support_io_shared_queue': 'bool', 'is_ready_to_notify_power_on': 'bool',
    'is_power_on_pending': 'bool', 'set_power_on_pending': 'void', 'get_clamshell_state': 'bool', 'get_second_external_state': 'bool',
}
# IOService methods IOMobileFramebufferLegacy overrides, as IOService.h declares them (slots below IOSERVICE_SLOTS).
IOSERVICE_OVERRIDES = {
    'free': 'void free()', 'init': 'bool init(OSDictionary *)', 'setProperties': 'IOReturn setProperties(OSObject *)',
    'systemWillShutdown': 'void systemWillShutdown(IOOptionBits)', 'probe': 'IOService *probe(IOService *, SInt32 *)',
    'start': 'bool start(IOService *)', 'stop': 'void stop(IOService *)', 'getWorkLoop': 'IOWorkLoop *getWorkLoop() const',
    'newUserClient': 'IOReturn newUserClient(task_t, void *, UInt32, IOUserClient **)',
    'setPowerState': 'IOReturn setPowerState(unsigned long, IOService *)',
}
IGNORED = {0, 1, 7, 16}   # destructors and getMetaClass come from OSDeclare*Structors; 16 is OSMetaClassBase::Dispatch (kc-build ignores it)
BUILTIN = {'void', 'bool', 'char', 'signed', 'unsigned', 'short', 'int', 'long', 'float', 'double', 'const', 'volatile', '__int128'}
KNOWN = {'IOService', 'IOUserClient', 'OSDictionary', 'OSObject', 'IOMemoryMap', 'IOMemoryDescriptor', 'task', 'OSString', 'OSData',
         'IOSurface', 'OSArray', 'OSNumber', 'OSSymbol', 'IOWorkLoop', 'IOCommandGate'}


def demangle(name):
    return subprocess.run(['llvm-cxxfilt', '-n', name], capture_output=True, text=True, check=True).stdout.strip()


def instance_size(kc, cls):
    """The size an OSMetaClass constructor passes: mov w3, #SIZE before its call to OSMetaClass::OSMetaClass."""
    symbol = f'__ZN{len(cls)}{cls}9MetaClassC2Ev'
    va = next(v for n, k, s, d, v in kc.symbols(kc.macho(KEXT)) if n == symbol)
    off = kc.file_offset(va)
    for i in range(32):
        word = int.from_bytes(kc.data[off + 4 * i:off + 4 * i + 4], 'little')
        if word & 0xffe0001f == 0x52800003:       # movz w3, #imm16
            return (word >> 5) & 0xffff
    sys.exit(f'{symbol}: no instance size')


def slots(kc_path, cls):
    out = subprocess.run(['python3', str(Path(__file__).parent / 'kc-vtable.py'), str(kc_path), cls], capture_output=True, text=True,
                         check=True).stdout.splitlines()[1:]
    return [(int(line.split()[0]), int(line.split()[1], 16), line.split()[2]) for line in out]


def declaration(symbol, owner):
    text = demangle(symbol)
    m = re.match(r'^(?:\w+::)*?(\w+)::(~?\w+)\((.*)\)( const)?$', text)
    if not m:
        sys.exit(f'cannot declare {symbol}: {text}')
    _, method, params, const = m.groups()
    params = params if params != 'void' else ''
    ret = RETURNS.get(method, 'IOReturn')
    return method, f'    virtual {ret} {method}({params}){const or ""};', params


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('kc', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    kc = fileset_kc.Kernelcache(args.kc.read_bytes())
    base = slots(args.kc, 'IOMobileFramebuffer')
    legacy = slots(args.kc, 'IOMobileFramebufferLegacy')
    sizes = {cls: instance_size(kc, cls) for cls in CLASSES}
    bodies, used, comments = {cls: [] for cls in CLASSES}, set(), []
    derived = slots(args.kc, 'AppleParavirtDisplay')
    tails = {}   # method name + parameters of every member function of the two kexts, by its own mangling tail
    for entry in (KEXT, 'com.apple.driver.AppleParavirtGPUIOGPUFamily'):
        for name, *_ in kc.symbols(kc.macho(entry)):
            m = re.match(r'^__ZN(K?)(\d+)(\w+)$', name)
            if m and len(m.group(3)) > int(m.group(2)) and m.group(3)[:int(m.group(2))] in CLASSES + ('AppleParavirtDisplay',):
                tails.setdefault(m.group(1) + '|' + m.group(3)[int(m.group(2)):], name)
    picked = []
    for slot, diversity, _ in legacy[IOSERVICE_SLOTS:]:
        owner = 'IOMobileFramebuffer' if slot < len(base) else 'IOMobileFramebufferLegacy'
        want = derived[slot][1]
        def mangled(key):
            const, tail = key.split('|')
            # a parameter type nested in the owner class: once the owner qualifies the method, it is the first substitution
            return f'_ZN{const}{len(owner)}{owner}' + tail.replace(f'N{len(owner)}{owner}', 'NS_')
        match = [name for key, name in tails.items() if discriminator(mangled(key)) == want]
        if len(match) != 1:
            sys.exit(f'slot {slot} ({owner}, diversity {want:#06x}): {len(match)} methods hash to it: {match[:4]}')
        picked.append((slot, want, match[0], owner))
    def implementer(name):
        if name.startswith('___cxa_pure_virtual'):
            return None
        m = re.match(r'^__ZNK?(\d+)', name)
        return name[len(m.group(0)):len(m.group(0)) + int(m.group(1))] if m else name

    for slot, diversity, symbol in legacy[:IOSERVICE_SLOTS]:
        if slot in IGNORED or implementer(symbol) != 'IOMobileFramebufferLegacy':
            continue
        method = re.match(r'^__ZNK?\d+IOMobileFramebufferLegacy(\d+)', symbol)
        method = symbol[method.end():method.end() + int(method.group(1))]
        if method not in IOSERVICE_OVERRIDES:
            sys.exit(f'slot {slot}: IOMobileFramebufferLegacy overrides {symbol}, which IOSERVICE_OVERRIDES does not declare')
        bodies['IOMobileFramebufferLegacy'].append(f'{"    virtual " + IOSERVICE_OVERRIDES[method] + " override;":<130} // {slot} {diversity:#06x}')
    for slot, diversity, symbol, owner in picked:
        method, line, params = declaration(symbol, owner)
        # pure where the introducing class's own vtable has __cxa_pure_virtual; IOMobileFramebufferLegacy redeclares the slots of
        # IOMobileFramebuffer it implements (the derived vtable must name its functions) or leaves pure (a driver implements them)
        own = implementer((base if owner == 'IOMobileFramebuffer' else legacy)[slot][2])
        if own is None:
            line = line[:-1] + ' = 0;'
        bodies[owner].append(f'{line:<130} // {slot} {diversity:#06x}')
        if owner == 'IOMobileFramebuffer':
            final = implementer(legacy[slot][2])
            if final not in ('IOMobileFramebuffer', 'IOMobileFramebufferLegacy', None):
                sys.exit(f'slot {slot}: IOMobileFramebufferLegacy holds {legacy[slot][2]}')
            if final != 'IOMobileFramebuffer':
                redeclared = line.replace(' = 0;', ';')[:-1] + (' override = 0;' if final is None else ' override;')
                bodies['IOMobileFramebufferLegacy'].append(f'{redeclared:<130} // {slot} {diversity:#06x}')
        used.update(re.findall(r'[A-Za-z_][\w:]*', params))
    types = sorted(t for t in used if t.split('::')[0] not in BUILTIN | KNOWN and t not in BUILTIN and not t.startswith('IOMobileFramebufferLegacy::'))
    nested = sorted({t.split('::', 1)[1] for t in used if t.startswith('IOMobileFramebufferLegacy::')})
    lines = ['// Generated by scripts/gen-iomfb-abi.py from the IOMobileFramebuffer classes of the macOS 26.5 kernelcache (vma2). Do not edit.',
             '// Slot numbers and PAC diversities are the kernelcache\'s; return types are IOReturn where the mangled name says nothing.',
             '#pragma once', '#include <IOKit/IOService.h>', '#include <IOKit/IOUserClient.h>', '#include <IOKit/IOMemoryDescriptor.h>',
             '#include <stdint.h>', '', 'class IOSurface;']
    by_value = {t for t in types if re.search(r'[(,]\s*' + re.escape(t) + r'\s*[,)]', ' '.join(
        declaration(s, '')[2].join('()') for _, _, s, _ in picked))}
    namespaces = {}
    for t in types:
        *ns, name = t.split('::')
        kind = f'enum {name} : uint32_t;' if t in by_value else f'struct {name};'
        namespaces.setdefault('::'.join(ns), []).append(kind)
    for ns, decls in sorted(namespaces.items()):
        if ns:
            lines.append('namespace ' + ' { namespace '.join(ns.split('::')) + ' { ' + ' '.join(decls) + ' ' + '}' * len(ns.split('::')))
        else:
            lines += decls
    lines += ['', 'class IOMobileFramebuffer : public IOService {', '    OSDeclareAbstractStructors(IOMobileFramebuffer)', 'public:']
    lines += bodies['IOMobileFramebuffer'] + ['};', '']
    lines += ['class IOMobileFramebufferLegacy : public IOMobileFramebuffer {', '    OSDeclareAbstractStructors(IOMobileFramebufferLegacy)', 'public:']
    lines += [f'    struct {name};' for name in nested]
    # inside the class a nested type hides the global one of its name (SwapInfoBlob): spell the global one ::Name, else the mangled
    # name and with it the slot's PAC diversity change
    shadowed = [name for name in nested if name in types]
    lines += [re.sub(r'(?<![\w:])(' + '|'.join(shadowed) + r')\b', r'::\1', line) if shadowed else line
              for line in bodies['IOMobileFramebufferLegacy']]
    lines += [f'    uint8_t iomfbLegacyState[{sizes["IOMobileFramebufferLegacy"]:#x} - sizeof(IOService)];   // the instance size of its MetaClass',
              '};', '',
              f'static_assert(sizeof(IOMobileFramebufferLegacy) == {sizes["IOMobileFramebufferLegacy"]:#x}, "IOMobileFramebufferLegacy instance size");',
              f'enum : unsigned {{IOMobileFramebufferLegacySlots = {len(legacy)}}};', '']
    args.output.write_text('\n'.join(lines))
    print(f'{args.output}: IOMobileFramebuffer {len(bodies["IOMobileFramebuffer"])} + IOMobileFramebufferLegacy '
          f'{len(bodies["IOMobileFramebufferLegacy"])} virtual methods, instance sizes {sizes}, {len(types)} types')


main()
