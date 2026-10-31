#!/usr/bin/env python3
"""Where each CPU of a frozen k27 VM is: its active thread's kernel stack (and, when in an interrupt, the interrupt stack), scanned for
frame records (fp, lr) whose fp chain climbs to the top of the stack; prints the deepest such chain symbolized.   k27/cpu-stacks.py
Reads live guest memory with scripts/rig-dmesg.py --peek (log /tmp/k27-serial.log, refreshed by k27/panic.sh or the poll).
Offsets: cpu_data (dSYM) cpu_active_thread 0x30, intstack_top 0x18, cpu_int_state 0xd0; thread kernel_stack 160 (k27_stall_check).
"""
import os, re, struct, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
os.environ['MACOS_KERNEL'] = str(ROOT / 'out/k27/kc-k27.bin')
LOG = '/tmp/k27-serial.log'
sys.path.insert(0, str(ROOT / 'k27'))


def peek(what, length):
    out = subprocess.run([sys.executable, str(ROOT / 'scripts/rig-dmesg.py'), '--peek', what, LOG, str(length)],
                         capture_output=True, text=True).stdout
    b = bytearray()
    for l in out.splitlines():
        m = re.match(r'0x[0-9a-f]+: ((?:[0-9a-f]{2} ?){1,16})', l)
        if m:
            b += bytes.fromhex(m.group(1).replace(' ', ''))
    return bytes(b)


def q(b, o=0):
    return struct.unpack_from('<Q', b, o)[0]


def strip(v):
    return v | 0xffffff8000000000 if v >> 39 else v


import importlib.util
spec = importlib.util.spec_from_file_location('sym', ROOT / 'k27/sym.py')
import contextlib, io
argv, sys.argv = sys.argv, [sys.argv[0], '0']   # sym.py symbolizes its arguments (else reads stdin) when loaded
sym = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(sym)
sys.argv = argv
stack_size = struct.unpack_from('<I', peek('kernel_stack_size', 4))[0]
entries = peek('CpuDataEntries', 16 * 8)


def chains(base, size):
    data = peek('va:%x' % base, size)
    best = None
    for o in range(0, size - 16, 8):
        fp0 = base + o
        chain, fp = [], fp0
        while base <= fp < base + size - 8 and len(chain) < 40:
            nxt, lr = q(data, fp - base), strip(q(data, fp - base + 8))
            if not (0xfffffff007004000 <= lr < 0xfffffff00c000000):
                break
            chain.append(lr)
            if nxt == 0 or nxt <= fp:
                break
            fp = nxt
        if len(chain) >= 3 and (best is None or len(chain) > len(best[1])):
            best = (fp0, chain)
    return best


for cpu in range(8):
    cd = q(entries, cpu * 16 + 8)
    if not cd:
        continue
    d = peek('va:%x' % cd, 0x100)
    thread, intstack, intstate = q(d, 0x30), q(d, 0x18), q(d, 0xd0)
    print(f'CPU {cpu}: cpu_data {cd:#x} thread {thread:#x} int_state {intstate:#x}')
    if intstate:
        r = chains(intstack - 0x4000, 0x4000)
        if r:
            print('  interrupt stack:'); [print('    ', sym.name(a)) for a in r[1]]
    if thread:
        ks = q(peek('va:%x' % (thread + 160), 8))
        if ks:
            r = chains(ks, stack_size)
            if r:
                print(f'  thread stack {ks:#x} (chain at {r[0]:#x}):'); [print('    ', sym.name(a)) for a in r[1]]

# The interrupted context of each CPU in an interrupt (cpu_int_state: arm_saved_state, 8-byte header, then x0..x28, fp, lr, sp, pc).
print('--- interrupted contexts')
for cpu in range(8):
    cd = q(entries, cpu * 16 + 8)
    intstate = q(peek('va:%x' % (cd + 0xd0), 8)) if cd else 0
    if not intstate:
        continue
    s = peek('va:%x' % intstate, 0x118)
    fp, lr, sp, pc = (q(s, 8 + 8 * i) for i in (29, 30, 31, 32))
    print(f'CPU {cpu}: pc {sym.name(strip(pc))}  lr {sym.name(strip(lr))}')
    for _ in range(14):
        if not fp:
            break
        f = peek('va:%x' % fp, 16)
        if len(f) < 16:
            break
        fp, ret = q(f), strip(q(f, 8))
        print('     ', sym.name(ret))
