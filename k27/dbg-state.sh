#!/usr/bin/env bash
# The debugger/panic state of a frozen k27 VM (a panic that hung in its own path parks the other CPUs in DebuggerXCall).
cd "$(dirname "$0")/.."
export MACOS_KERNEL=$PWD/out/k27/kc-k27.bin
LOG=/tmp/k27-serial.log; ID=3307dca0-8a10-59af-8abf-1a1501cd5b40
adb shell "su -c 'cat /data/data/cn.classfun.droidvm/cache/console_${ID}_serial1.log'" > $LOG 2>/dev/null
for s in debugger_cpu:4 kernel_debugger_entry_count:4 debugger_current_op:4 debugger_panic_str:8 debugger_message:8 debugger_panic_options:8 debug_buf_base:8 debug_buf_ptr:8 initproc:8; do
  printf '%-28s ' ${s%%:*}; python3 scripts/rig-dmesg.py --peek ${s%%:*} $LOG ${s##*:} 2>&1 | tail -1 | cut -d: -f2 | cut -c1-26
done
