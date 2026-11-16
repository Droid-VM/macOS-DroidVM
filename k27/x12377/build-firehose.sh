#!/usr/bin/env bash
# libfirehose_kernel.a for XNU_ARCH (arm64|arm64e) from out/x12377/refer-libdispatch, into out/x12377/fakeroot/usr/local/lib/kernel-$XNU_ARCH/ (this was out/x12377/build-firehose.sh).
set -eu
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ARCH=${XNU_ARCH:-arm64}
. "$HERE/env.sh"
cd "$R/out/x12377"
export GUNYAH_APPLE_TARGET=$ARCH-apple-ios26.0
SDK=$(xcrun --sdk iphoneos --show-sdk-path); F=fakeroot; K=$F/System/Library/Frameworks/Kernel.framework/Versions/A
mkdir -p build/firehose-$ARCH fakeroot/usr/local/lib/kernel-$ARCH
xcrun clang -target $ARCH-apple-ios26.0 -isysroot $SDK -ffreestanding -nostdinc -fno-stack-protector -mno-implicit-float -fblocks -O2 -std=gnu11 \
  -DKERNEL=1 -DDISPATCH_USE_DTRACE=0 -DOS_ATOMIC_CONFIG_MEMORY_ORDER_DEPENDENCY=1 -DOS_ATOMIC_CONFIG_STARVATION_FREE_ONLY=0 -D__PTRAUTH_INTRINSICS__=1 -fptrauth-function-pointer-type-discrimination \
  -Wno-packed -Wno-deprecated-declarations -I refer-libdispatch -I $K/PrivateHeaders -I $K/Headers -I $F/usr/local/include/os -I $F/usr/local/include/firehose \
  -I xnu-m/EXTERNAL_HEADERS -I $SDK/usr/include -I $(xcrun clang -print-resource-dir)/include \
  -c refer-libdispatch/src/firehose/firehose_buffer.c -o build/firehose-$ARCH/firehose_buffer.o
rm -f fakeroot/usr/local/lib/kernel-$ARCH/libfirehose_kernel.a
xcrun ar rcs fakeroot/usr/local/lib/kernel-$ARCH/libfirehose_kernel.a build/firehose-$ARCH/firehose_buffer.o
