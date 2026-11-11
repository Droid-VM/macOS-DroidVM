#!/usr/bin/env bash
# Rebuild ArmCpu with the existing SMP/SPI patches and MSI CPU affinity.
set -euo pipefail
cd "$(dirname "$0")/.."
platform=out/x12377/un/build/platform-12377-arm64e/ArmCpu
cp out/x12377/un/drivers/ArmCpu/ArmCpu.cpp "$platform/ArmCpu.cpp"
for patch in ArmCpu-arm64-assembly ArmCpu-12377-boot-interrupt ArmCpu-idle-wfi ArmCpu-park-wfi-latency ArmCpu-spi-controller ArmCpu-msi-affinity; do
    git apply --directory="$platform" "patches/drivers/$patch.patch"
done
python3 scripts/build-native-kext.py ArmCpu "$platform/ArmCpu.cpp" --obj k27-obj
llvm-ar rcs "$platform/libArmCpu.a" out/x12377/native-kexts/ArmCpu/ArmCpu.o
