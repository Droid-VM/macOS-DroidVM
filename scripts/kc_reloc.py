"""Rebind the references of borrowed kexts (a macOS 26.5 fileset kernelcache) from Apple's kernel to a source-built one.

The kexts carry no relocation records. What they reference in the kernel is of two kinds, both recoverable by symbol name:
  * direct b/bl into the old kernel (functions): retargeted here, instruction by instruction;
  * chained data pointers (vtables, __got/__auth_got entries, which is also how the kexts reach kernel data): the target of the
    chain entry is remapped (kc-build.py carries the signature fields over unchanged).
No kext of the 26.5 cache forms a kernel data address with adrp (checked over all 217: zero adrp into the kernel's pages), so
nothing like an adrp/add pair has to be rewritten; relocate_text reports one if it ever shows up.
"""
import bisect
from collections import Counter, defaultdict


class Unresolvable(Exception):
    pass


class Remap:
    """Old kernel address -> new kernel address, by symbol name (+ offset inside the symbol)."""

    def __init__(self, old_ranges, old_symbols, new_symbols):
        self.ranges = old_ranges                       # [(low, high)] of the old kernel's segments (old addresses)
        self.names = defaultdict(list)                 # old address -> names defined there
        for address, name in old_symbols:
            if name not in self.names[address]:
                self.names[address].append(name)
        self.addresses = sorted(self.names)
        self.new = new_symbols                         # name -> [addresses] (all defined symbols of the new kernel)
        self.stats = Counter()
        self.interior = defaultdict(int)               # (name, delta) -> uses

    def in_old_kernel(self, va):
        return any(low <= va < high for low, high in self.ranges)

    def is_symbol(self, va):
        return va in self.names

    def map(self, va, exact=False):
        index = bisect.bisect_right(self.addresses, va) - 1
        if index < 0:
            raise Unresolvable(f'{va:#x}: no old kernel symbol below')
        address = self.addresses[index]
        delta = va - address
        if exact and delta:
            raise Unresolvable(f'{va:#x}: {self.names[address][0]}+{delta:#x} is not a symbol')
        for name in self.names[address]:
            found = self.new.get(name, [])
            if len(found) == 1:
                self.stats['exact' if not delta else 'interior'] += 1
                if delta:
                    self.interior[(name, delta)] += 1
                return found[0] + delta
        raise Unresolvable(f'{va:#x}: none of {self.names[address]} is (uniquely) defined by the new kernel')


def sext(value, bits):
    return value - (1 << bits) if value >> (bits - 1) else value


def branch_target(word, pc):
    if word & 0x7c000000 == 0x14000000:
        return pc + sext(word & 0x3ffffff, 26) * 4
    return None


def adrp_page(word, pc):
    if word & 0x9f000000 != 0x90000000:
        return None
    imm = sext((word >> 5 & 0x7ffff) << 2 | word >> 29 & 3, 21)
    return (pc & ~0xfff) + (imm << 12)


def relocate_text(words, base, shift, remap, report):
    """Retarget the b/bl of WORDS (instruction words at old address BASE) that go into the old kernel. SHIFT moves the kext's own
    code from its old to its new address. Returns {index: new word}.

    A kext cannot call an unexported kernel function, so a branch into the kernel that is not exactly a symbol is data: kexts such as
    corecrypto keep constant tables inside __text (and list them as function starts), and some of those words decode as branches."""
    changes = {}
    for i, word in enumerate(words):
        pc = base + i * 4
        target = branch_target(word, pc)
        if target is not None and remap.in_old_kernel(target):
            if not remap.is_symbol(target):
                report['skipped'].append((pc, 'branch', target))
                continue
            delta = remap.map(target, exact=True) - (pc + shift)
            if delta & 3 or not -(1 << 27) <= delta < (1 << 27):
                raise Unresolvable(f'branch at {pc:#x} cannot reach its new target')
            changes[i] = word & 0xfc000000 | (delta >> 2) & 0x3ffffff
            report['branch'] += 1
            continue
        page = adrp_page(word, pc)
        if page is not None and remap.in_old_kernel(page):
            report['skipped'].append((pc, 'adrp', page))
    return changes


# CoreEntitlements (inside AMFI) guards its recursion with `sp & ((1 << PAGE_SHIFT_CONST) - 1) < 128`: on Apple's kernel the stack is 16 KiB, aligned to it
# and the page is 16 KiB, so that means "less than 128 bytes of stack left" (CEElementIterate then fails with an error, and the entitlement
# dictionary of that process cannot be built: AMFI panics "failed to create OSDictionary copy"). This kernel's stacks sit one 4 KiB guard page
# above an aligned boundary, so the test also fires for a stack pointer in the first 128 bytes above any aligned boundary inside the stack: a
# perfectly good place, 4 KiB below the top for the exec path (seputil's entitlements failed this way). The stack has a guard page of its own: the
# comparison is made one that never holds.
STACK_CHECK = (0x12800009,   # movn w9, #0
               0x1ac82128,   # lsl  w8, w9, w8      <- w8 holds PAGE_SHIFT_CONST
               0x2a2803e8,   # mvn  w8, w8
               0x910003e9,   # mov  x9, sp
               0x8a090108,   # and  x8, x8, x9
               0xf102011f)   # cmp  x8, #128        (followed by b.lo to the error exit)
CMP_X8_ZERO = 0xf100011f     # cmp  x8, #0: x8 < 0 never holds


def patch_stack_checks(words):
    """Returns {index: new word} for every stack check of the idiom above (the limit becomes 0)."""
    changes = {}
    for i in range(len(words) - len(STACK_CHECK) + 1):
        if tuple(words[i:i + len(STACK_CHECK)]) == STACK_CHECK:
            changes[i + 5] = CMP_X8_ZERO
    return changes
