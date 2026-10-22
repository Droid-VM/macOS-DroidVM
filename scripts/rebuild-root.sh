#!/usr/bin/env bash
# Regenerate the SystemOS disk (shims), its owner policy and pins, and rebuild the kernel that embeds them.
#   rebuild-root.sh [JOBS]
set -euo pipefail
cd "$(dirname "$0")/.."
JOBS=${1:-16}
LOG=research/runs/p1-linux-20261022
rm -f artifacts/23G93/systemos.img
bash scripts/make-macos-systemos.sh sources/apfsprogs sources/linux-apfs-rw/apfs.ko artifacts/23G93/090-91768-091.apfs \
  artifacts/23G93/os.raw artifacts/23G93/systemos.img > "$LOG/make-systemos-latest.log" 2>&1
rm -rf out/owner/systemos-23G93 out/owner/inputs out/owner/macos-root-pins.json
python3 scripts/local-root-policy.py --image artifacts/23G93/systemos.img --volume-uuid 8846FE78-2910-4297-AF97-D59BB6F8FC16 \
  --output out/owner/systemos-23G93 --image-origin transformed | tail -1
python3 scripts/macos-root-pins.py > /dev/null
python3 scripts/macos-policy-inputs.py
python3 scripts/build-linux.py full -j "$JOBS" --legacy-display > "$LOG/full-build-latest.log" 2>&1
grep "kernel.macho sha256" "$LOG/full-build-latest.log" | cut -c1-200
