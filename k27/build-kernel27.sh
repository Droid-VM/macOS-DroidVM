#!/usr/bin/env bash
# The k27 kernel: out/x12377/build-full.sh with XNU_KC=1 XNU_KEXT_CRYPTO=1, but the source tree out/k27/xnu (branch k27, a worktree of
# xnu-m), its own objects (out/k27/obj, -sym, -dst) and the kc27 segment layout (k27/segaddrs.sh). Output: out/k27/kernel-k27.macho.
set -u
K27=$(cd "$(dirname "$0")" && pwd); M=$(dirname "$K27"); X=$M/out/x12377; O=$M/out/k27
mkdir -p $O/obj $O/sym $O/dst $X/build/xnu
for d in obj sym dst; do [ -e $X/build/xnu/k27-$d ] || ln -s $O/$d $X/build/xnu/k27-$d; done   # build-kernel.sh puts them under build/xnu/OBJ-*
cd $X
# iig (DriverKit headers and .iig.cpp from the tree's *.iig) needs Xcode's iig (an Apple ID download) in the Darling container: k27
# changes no .iig, so its output for this tree is kept in k27/iig (generated for xnu-m, same relative directories) and copied in, newer
# than the sources so make keeps it.
( cd $K27/iig && find DEVELOPMENT_ARM64_BCM2837 -type f ) | while read -r f; do
  [ -e $O/obj/$f ] || { mkdir -p $O/obj/$(dirname $f); cp $K27/iig/$f $O/obj/$f; }
  touch -c $O/obj/$f
done
export XNU_ARCH=arm64e
U=$PWD/un; FR=$PWD/fakeroot
. $K27/x12377/env.sh
export CCC_OVERRIDE_OPTIONS='+-Wno-error=missing-designated-field-initializers'
DT=$U/build/platform-12377-arm64e/ArmDTPlatform/libArmDTPlatform.a; CPU=$U/build/platform-12377-arm64e/ArmCpu/libArmCpu.a
FH=$FR/usr/local/lib/kernel-arm64e
LDX="-Wl,-no_fixup_chains -Wl,-threaded_starts_section"
export XNU_SOURCE_CORECRYPTO14=0
T=$O/xnu
touch $T/osfmk/prng/prng_random.c $T/pexpert/arm/pe_init.c
OWNER="-DXNU_NATIVE_RAM_BLOCK=1 -DXNU_OWNER_CACHE_MOUNT=1 -DXNU_OWNER_BOOT_MANIFEST=1 -DXNU_OWNER_CACHE_STARTUP=1"
export XNU_EXTRA_CFLAGS="-DXNU_NATIVE_CS_HASH_CACHE=1 $OWNER ${XNU_EXTRA_CFLAGS:-}"
touch $T/bsd/kern/ubc_subr.c $T/bsd/kern/kern_exec.c $T/osfmk/kern/link_compat.c $T/iokit/bsddev/IOKitBSDInit.cpp
export XNU_KC_SEGADDRS="$(bash $K27/segaddrs.sh)"
kbuild() {
  XNU_ARM_DT_PLATFORM=1 XNU_ARMCPU=1 XNU_TREE=../k27/xnu KDK=kdk XNU_OBJ=k27 \
    XNU_DEPLOYMENT_TARGET_FLAGS="-miphoneos-version-min=26.0 -DXNU_TARGET_OS_OSX" bash $K27/x12377/build-kernel.sh
}
# ArmDTPlatform and ArmCpu compile with the flags of the kernel's own objects (build-native-kext.py reads their compile records), so a
# new object tree is built once without them first (its link is allowed to fail), then they are, then the kernel links (make -k).
if [ ! -e $O/obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPlatformExpert.cpo.json ]; then
  echo "first build of $O/obj: the kernel's objects before ArmDTPlatform and ArmCpu"
  XNU_LD_ARCHIVES="$LDX -L$FH -lfirehose_kernel" kbuild > $O/build-bootstrap.log 2>&1
fi
bash "$K27/build-platform-rtc.sh"
bash "$K27/build-platform-cpu.sh"
export XNU_LD_ARCHIVES="$LDX -L$FH -lfirehose_kernel -Wl,-force_load,$DT -Wl,-force_load,$CPU" XNU_ARCHIVE_DEPS="$DT $CPU"
kbuild 2>&1 | tee $O/build-raw.log | grep -a -v "warning:" | grep -a -E "error:|Undefined|^  \"|duplicate" | cut -c1-200 | head -30
rc=${PIPESTATUS[0]}
[ "$rc" = 0 ] || { echo "kernel build failed ($rc): the kernel was not copied"; exit "$rc"; }
cp $O/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped.noctf $O/kernel-k27.macho
ls -la $O/kernel-k27.macho
