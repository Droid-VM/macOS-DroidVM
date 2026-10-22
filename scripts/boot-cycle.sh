#!/usr/bin/env bash
# Boot the macOS VM once with the diagnostic arguments, wait, read the kernel log and print what happened.
#   boot-cycle.sh LABEL [SECONDS] [extra run-macos-vm.py arguments...]
set -euo pipefail
cd "$(dirname "$0")/.."
SERIAL=${PHONE_SERIAL:-192.168.1.188:33445}
LABEL=$1
SECONDS_TO_RUN=${2:-90}
shift $(( $# > 1 ? 2 : 1 ))
adb -s "$SERIAL" shell "pkill -x crosvm-mmio" || true
sleep 5
LOG=research/runs/p3-boot-20261022/run-$LABEL.log
python3 scripts/run-macos-vm.py --serial "$SERIAL" --seconds "$SECONDS_TO_RUN" --keep --mem-mb "${MEM_MB:-2560}" --label "$LABEL" \
  --kernel-arg exec-log=1 --kernel-arg crash-log=1 --kernel-arg syscall-err-log=1 \
  --kernel-arg mac-sandbox-permissive=1 --kernel-arg mac-amfi-launch-permissive=1 "$@" > "$LOG" 2>&1
DIR=$(ls -d research/runs/*-"$LABEL" | tail -1)
python3 scripts/rig-dmesg.py "$DIR/serial.log" --serial "$SERIAL" > "$DIR/dmesg.txt" 2> "$DIR/dmesg.err" || true
echo "evidence: $DIR"
grep -n "exec:\|syscall-err\|crash:\|exited\|panic" "$DIR/dmesg.txt" | cut -c1-220 | tail -${TAIL_LINES:-60}
