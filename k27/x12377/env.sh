# The kernel build's environment (sourced): the Linux adapters of toolchains/linux/bin26, the host LLVM 21, the headers-only SDK root
# out/x12377/fakeroot. Made by scripts/setup-env.py (toolchain, x12377); this was out/x12377/env.sh.
R=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
TC=$R/toolchains/linux
export TMPDIR=$R/out/linux/tmp XDG_CACHE_HOME=$R/out/linux/cache
mkdir -p "$TMPDIR" "$XDG_CACHE_HOME"
export PATH=$R/compat/droidvm-linux/shims:$TC/bin26:$TC/host-deps/usr/bin:/usr/lib/llvm-21/bin:$PATH
export PYTHONPATH=$R/compat/droidvm-linux/pyhook:$TC/python-deps
export GUNYAH_APPLE_TARGET=arm64-apple-ios26.0 GUNYAH_LINUX_BIN=$TC/bin26
export KERNEL_SDKROOT=$R/out/x12377/fakeroot
