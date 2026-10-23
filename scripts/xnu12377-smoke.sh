#!/usr/bin/env bash
# Boot out/x12377/kernel12377m-osx.macho (or $MACOS_KERNEL) in the App's persistent VM and print its message buffer.
#   xnu12377-smoke.sh [SECONDS] [extra kernel args...]       peeks: PEEKS="port_crumb gDramBase" (8 bytes each)
set -u
cd "$(dirname "$0")/.."
export MACOS_KERNEL=${MACOS_KERNEL:-$PWD/out/x12377/kernel12377m-osx.macho} MACOS_TAG=${MACOS_TAG:-27.0.1}
SECONDS_WAIT=${1:-30}; shift || true
ARGS=(--kernel-arg=-v --kernel-arg=vm_compression_limit=1572864)
for a in "$@"; do ARGS+=("--kernel-arg=$a"); done
ID=3307dca0-8a10-59af-8abf-1a1501cd5b40
python3 scripts/droidvm-app.py stop >/dev/null 2>&1
python3 scripts/droidvm-app.py boot "${ARGS[@]}" | tail -1 | cut -c1-60
adb shell "su -c ': > /data/data/cn.classfun.droidvm/cache/console_${ID}_serial1.log'" >/dev/null 2>&1
python3 scripts/droidvm-app.py start | tail -1
sleep "$SECONDS_WAIT"
LOG=/tmp/xnu12377-serial.log
adb shell "su -c 'cat /data/data/cn.classfun.droidvm/cache/console_${ID}_serial1.log'" > "$LOG" 2>/dev/null
adb shell "su -c 'tail -n 3 /data/data/cn.classfun.droidvm/cache/console_${ID}_stderr.log'" | cut -c1-200
python3 scripts/rig-dmesg.py "$LOG" 2>&1 | tail -${DMESG_LINES:-40}
for s in ${PEEKS:-port_crumb}; do echo -n "$s: "; python3 scripts/rig-dmesg.py --peek "$s" "$LOG" 8 2>&1 | tail -1; done
