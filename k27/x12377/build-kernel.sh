#!/usr/bin/env bash
# make of an xnu-12377 tree (XNU_TREE, relative to out/x12377) into out/x12377/build/xnu/XNU_OBJ-{obj,sym,dst}, with the UniXNU series feature flags
# (defaults: droidvm_defconfig). k27/build-kernel27.sh is the k27 entry; this was out/x12377/build-kernel.sh.
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
. "$HERE/env.sh"
cd "$R/out/x12377"
TC=$R/toolchains/linux
export GUNYAH_APPLE_TARGET=${XNU_ARCH:-arm64}-apple-ios26.0
export GUNYAH_LINUX=1 GUNYAH_LINUX_MAKEFILE=${GUNYAH_LINUX_MAKEFILE:-$PWD/gunyah-linux.mk} GUNYAH_LINUX_CC=$TC/bin26/target-clang GUNYAH_LINUX_CXX=$TC/bin26/target-clang++ GUNYAH_LINUX_C_SUPPORT=0
# Per-object feature flags of the UniXNU xnu-12377 series (patches/xnu-12377): defaults are the DroidVM board's droidvm_defconfig.
# make does not track per-object flags, so those objects are dropped on every run.
OBJDIR=$PWD/build/xnu/${XNU_OBJ:-ios}-obj/DEVELOPMENT_ARM64_BCM2837
X_ARCH_TIMER=${XNU_NATIVE_ARCH_TIMER:-1}; X_VTIMER=${XNU_VIRTUAL_TIMER_ONLY:-0}; X_PAN=${XNU_NATIVE_PAN:-1}
X_DTPANIC=${XNU_DT_PANIC_REGION:-1}; X_TRUST=${XNU_TRUST_CACHE_RUNTIME:-1}; X_DTPLAT=${XNU_ARM_DT_PLATFORM:-0}; X_ARMCPU=${XNU_ARMCPU:-0}
for o in osfmk/DEVELOPMENT/start.o osfmk/DEVELOPMENT/machine_routines.o pexpert/DEVELOPMENT/pe_init.o osfmk/DEVELOPMENT/startup.o \
  osfmk/DEVELOPMENT/copyio.o osfmk/DEVELOPMENT/pcb.o osfmk/DEVELOPMENT/platform_tests.o iokit/DEVELOPMENT/KernelConfigTables.cpo \
  osfmk/DEVELOPMENT/prng_random.o pexpert/DEVELOPMENT/pe_serial.o osfmk/DEVELOPMENT/rtclock.o; do rm -f "$OBJDIR/$o"; done
FLAG_ARGS=("start.o_SFLAGS_ADD=-DXNU_NATIVE_ARCH_TIMER=$X_ARCH_TIMER" "machine_routines.o_CFLAGS_ADD=-DXNU_VIRTUAL_TIMER_ONLY=$X_VTIMER"
  "pe_init.o_CFLAGS_ADD=-DXNU_DT_PANIC_REGION=$X_DTPANIC" "startup.o_CFLAGS_ADD=-DXNU_NATIVE_TRUST_CACHE=$X_TRUST")
[ "$X_PAN" = 1 ] && FLAG_ARGS+=("copyio.o_CFLAGS_ADD=-march=armv8.1-a" "pcb.o_CFLAGS_ADD=-march=armv8.1-a" "platform_tests.o_CFLAGS_ADD=-march=armv8.1-a")
X_CRYPTO=${XNU_SOURCE_CORECRYPTO14:-0}; X_PTHREAD=${XNU_SOURCE_PTHREAD:-0}
[ "${XNU_ARCH:-arm64}" = arm64e ] && ARM64E_FLAGS="-D__PTRAUTH_INTRINSICS__=1 -fptrauth-function-pointer-type-discrimination" || ARM64E_FLAGS=""   # Apple clang defines it; upstream LLVM only has __PTRAUTH__
X_CFLAGS="$ARM64E_FLAGS -DXNU_SOURCE_CORECRYPTO14=$X_CRYPTO -DXNU_SOURCE_PTHREAD=$X_PTHREAD -DXNU_NATIVE_PAN=$X_PAN -DXNU_ARM_DT_PLATFORM=$X_DTPLAT -DXNU_ARMCPU=$X_ARMCPU -Wno-reserved-identifier -Wno-pre-c11-compat -Wno-missing-designated-field-initializers -Wno-suggest-override -Wno-unnecessary-virtual-specifier -Wno-suggest-destructor-override -Wno-ms-bitfield-padding"
make -C ${XNU_TREE:-xnu-work} ${XNU_BUILD_TARGET:-build} SDKROOT=${XNU_SDKROOT:-iphoneos} ARCH_CONFIGS=ARM64 \
  MACHINE_CONFIGS=BCM2837 KERNEL_CONFIGS=DEVELOPMENT ${KDK:+KDKROOT=$PWD/$KDK} CFLAGS_EXTRA="$X_CFLAGS ${XNU_EXTRA_CFLAGS:-}" "${FLAG_ARGS[@]}" ${XNU_LD_ARCHIVES:+"LD_KERNEL_ARCHIVES=$XNU_LD_ARCHIVES" "XNU_EXTERNAL_KERNEL_ARCHIVES=${XNU_ARCHIVE_DEPS:-}"} \
  ARCH_STRING_FOR_CURRENT_MACHINE_CONFIG=${XNU_ARCH:-arm64} LARGE_MEMORY_DEFINE=-UARM_LARGE_MEMORY \
  ARM64_LINK_ADDR=0xfffffff007004000 ARM64_PLKSEG_ADDR=0xfffffff004004000 \
  DEPLOYMENT_TARGET_FLAGS="${XNU_DEPLOYMENT_TARGET_FLAGS:--miphoneos-version-min=26.0 -DXNU_TARGET_OS_IOS}" \
  DEPLOYMENT_LINKER_FLAGS="-Wl,-ios_version_min,26.0" \
  RC_DARWIN_KERNEL_VERSION=25.5.0 RC_ProjectSourceVersion=12377.121.6 \
  BUILD_LTO=0 BOUND_CHECKS=0 BUILD_WERROR=0 MAKEJOBS=-j${JOBS:-16} -k \
  OBJROOT=$PWD/build/xnu/${XNU_OBJ:-ios}-obj SYMROOT=$PWD/build/xnu/${XNU_OBJ:-ios}-sym DSTROOT=$PWD/build/xnu/${XNU_OBJ:-ios}-dst
