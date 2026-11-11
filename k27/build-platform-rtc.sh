#!/usr/bin/env bash
# Build only ArmDTPlatform with the PL030 RTC patch; preserve the separately built ArmCpu archive.
set -euo pipefail
cd "$(dirname "$0")/.."
platform=out/x12377/un/build/platform-12377-arm64e/ArmDTPlatform
cp out/x12377/un/drivers/ArmDTPlatform/ArmDTPlatform.cpp "$platform/ArmDTPlatform.cpp"
git apply --directory="$platform" patches/drivers/ArmDTPlatform-pl030-rtc.patch
python3 scripts/build-native-kext.py ArmDTPlatform "$platform/ArmDTPlatform.cpp" --obj k27-obj
llvm-ar rcs "$platform/libArmDTPlatform.a" out/x12377/native-kexts/ArmDTPlatform/ArmDTPlatform.o
