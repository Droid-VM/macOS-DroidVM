#!/usr/bin/env bash
# Regenerate the SystemOS disk (shims), its owner policy and pins, and rebuild the kernel that embeds them.
#   [MACOS_TAG=27.0.1 OS_OFFSET=210763776 CRYPTEX=... ] rebuild-root.sh [JOBS]
# MACOS_TAG names artifacts/TAG (os.raw, systemos.img) and out/owner/{os,systemos}-TAG; the default is the 14.6.1 root.
set -euo pipefail
cd "$(dirname "$0")/.."
JOBS=${1:-16}
TAG=${MACOS_TAG:-23G93}
CRYPTEX=${CRYPTEX:-artifacts/23G93/090-91768-091.apfs}
SIZE_MIB=${SIZE_MIB:-7168}
LOG=research/runs/p1-linux-20261022
mkdir -p "$LOG"
rm -f "artifacts/$TAG/systemos.img"
bash scripts/make-macos-systemos.sh sources/apfsprogs sources/linux-apfs-rw/apfs.ko "$CRYPTEX" \
  "artifacts/$TAG/os.raw" "artifacts/$TAG/systemos.img" "$SIZE_MIB" > "$LOG/make-systemos-latest.log" 2>&1
rm -rf "out/owner/systemos-$TAG" out/owner/inputs out/owner/macos-root-pins.json
python3 scripts/local-root-policy.py --image "artifacts/$TAG/systemos.img" --volume-uuid 8846FE78-2910-4297-AF97-D59BB6F8FC16 \
  --output "out/owner/systemos-$TAG" --image-origin transformed | tail -1
python3 scripts/macos-root-pins.py > /dev/null
python3 scripts/macos-policy-inputs.py
python3 scripts/build-linux.py full -j "$JOBS" --legacy-display > "$LOG/full-build-latest.log" 2>&1
grep "kernel.macho sha256" "$LOG/full-build-latest.log" | cut -c1-200
