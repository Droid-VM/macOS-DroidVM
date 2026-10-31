#!/usr/bin/env bash
# The panic text of the running k27 VM (boot with panic-spin=1 so it stays): xnu's debug buffer, debug_buf_base .. debug_buf_ptr.
# scripts/kc-panic.sh reads a fixed guest PA that the k27 kernel does not use. Saves it to out/k27/panic.txt.   k27/panic.sh [LINES]
cd "$(dirname "$0")/.."
export MACOS_KERNEL=$PWD/out/k27/kc-k27.bin
ID=3307dca0-8a10-59af-8abf-1a1501cd5b40
LOG=/tmp/k27-serial.log
adb shell "su -c 'cat /data/data/cn.classfun.droidvm/cache/console_${ID}_serial1.log'" > $LOG 2>/dev/null
word() { python3 scripts/rig-dmesg.py --peek "$1" $LOG 8 2>/dev/null | tail -1 | python3 -c "import sys; print(hex(int.from_bytes(bytes.fromhex(''.join(sys.stdin.read().split(':',1)[1].split()[:8])), 'little')))"; }
BASE=$(word debug_buf_base); PTR=$(word debug_buf_ptr)
LEN=$((PTR - BASE))
[ "$LEN" -gt 0 ] || { echo "no panic (debug buffer empty: $BASE)"; exit 0; }
python3 scripts/rig-dmesg.py --peek va:${BASE#0x} $LOG $LEN 2>/dev/null | python3 -c "
import re, sys
b = bytearray()
for l in sys.stdin:
    m = re.match(r'0x[0-9a-f]+: ((?:[0-9a-f]{2} ?){1,16})', l)
    if m:
        b += bytes.fromhex(m.group(1).replace(' ', ''))
open('out/k27/panic.txt', 'wb').write(b)
sys.stdout.write(b.decode(errors='replace'))
" | grep -a -v '^\s*$' | head -${1:-70}
