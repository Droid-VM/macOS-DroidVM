#!/usr/bin/env python3
"""Build the prepared Gunyah XNU tree with native Linux tools and an Apple SDK."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from iig_cache import verify as verify_iig_cache
from probe_xnu_compiler import probe as probe_xnu_compiler

DEVICE = Path(__file__).resolve().parents[1]


def prepare(tree, toolchain, deps, iig=None):
    config = json.loads((toolchain / "bin/linux-toolchain.json").read_text())
    work = tree / ".cache/xnu-work"
    for target, patches in ((work, "patches"), (tree, "project-patches")):
        for patch in sorted((DEVICE / "linux" / patches).glob("*.patch")):
            reverse = subprocess.run(["git", "-C", str(target), "apply", "--reverse", "--check", str(patch)], capture_output=True)
            if reverse.returncode:
                subprocess.run(["git", "-C", str(target), "apply", "--check", str(patch)], check=True)
                subprocess.run(["git", "-C", str(target), "apply", str(patch)], check=True)
    include = toolchain / "cctools-work/cctools/include"
    libraries = toolchain / "cctools-work/cctools/libmacho/.libs/libmacho.a"
    # Header exports need native ELF tools, never an iOS or macOS host binary.
    host_flags = f"-I{DEVICE / 'linux'} -I{include} -idirafter {include / 'foreign'} -I{deps / 'usr/include'} -I{deps / 'usr/include/x86_64-linux-gnu'} -include bsd/stdlib.h -include bsd/unistd.h -D__private_extern__=extern"
    host_libs = f"{libraries} {toolchain / 'cctools-work/cctools/libstuff/.libs/libstuff.a'} {deps / 'usr/lib/x86_64-linux-gnu/libbsd.a'} {deps / 'usr/lib/x86_64-linux-gnu/libmd.a'} -luuid"
    variables = dict(XCRUN=toolchain / "bin/xcrun", SDKROOT_RESOLVED=config["sdk"],
                     HOST_SDKROOT_RESOLVED="/", SDKVERSION=config["sdk_version"], PLATFORM="iPhoneOS",
                     HOST_PLATFORM="Linux", HOST_OS_VERSION="", HOST_CC=config["clang"],
                     HOST_FLEX=shutil.which("flex"), HOST_BISON=shutil.which("bison"), HOST_GM4=shutil.which("m4"),
                     CC=toolchain / "bin/target-clang", CXX=toolchain / "bin/target-clang++",
                     PLUTIL=toolchain / "bin/plutil", PAX=deps / "usr/bin/pax",
                     LINUX_HOST_CFLAGS=host_flags, LINUX_HOST_LIBS=host_libs,
                     MEMORY_SIZE=os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
                     SYSCTL_HW_PHYSICALCPU=os.cpu_count(), SYSCTL_HW_LOGICALCPU=os.cpu_count(),
                     DO_CTFMERGE="0", IIG=iig or "", SCAN_BUILD="", CTFINSERT="", CTFCONVERT="", CTFMERGE="", CTFDUMP="", DOCC="", HOST_CODESIGN_ALLOCATE="")
    if config.get("appleclang"):
        runtime = config["appleclang"].get("kernel_runtime")
        if not runtime:
            raise ValueError("Re-run setup-appleclang.py configure to select the Apple kernel compiler runtime")
        archive = Path(runtime["path"])
        if hashlib.sha256(archive.read_bytes()).hexdigest() != runtime["sha256"]:
            raise ValueError("Modified Apple kernel compiler runtime")
        # Native upstream clang drops -lcc_kext and cannot supply Apple's stack
        # probes or XNU's profile-buffer ABI. Link the matching kernel archive
        # explicitly; do not use the userspace profile runtime or dummy stubs.
        variables["LD_KERNEL_LIBS"] = archive
    for name in ("MIG", "MIGCOM", "STRIP", "LIPO", "LIBTOOL", "OTOOL", "NM", "UNIFDEF", "DSYMUTIL", "NMEDIT", "GIT", "PYTHON"):
        variables[name] = config["tools"]["python3" if name == "PYTHON" else name.lower()]
    fragment = tree / "gunyah-linux.mk"
    fragment.write_text("# Generated Linux host/Apple target tool selection.\n" + "".join(
        f"override {key} := {value}\n" for key, value in variables.items()))
    # The original libfirehose xcodebuild step is replaced, not emulated.
    firehose = tree / "scripts/build-firehose.sh"
    replacement = '#!/usr/bin/env bash\nset -euo pipefail\nexec python3 "$GUNYAH_LINUX_DEVICE/scripts/build-firehose-linux.py" --tree "$(cd "$(dirname "$0")/.." && pwd)"\n'
    firehose.write_text(replacement)
    return config, dict(GUNYAH_LINUX="1", GUNYAH_LINUX_MAKEFILE=str(fragment),
                        GUNYAH_LINUX_CC=str(toolchain / "bin/target-clang"),
                        GUNYAH_LINUX_CXX=str(toolchain / "bin/target-clang++"),
                        GUNYAH_LINUX_C_SUPPORT="0",
                        GUNYAH_LINUX_DEVICE=str(DEVICE),
                        PATH=os.pathsep.join([str(toolchain / "bin"), str(deps / "usr/bin"), os.environ["PATH"]]),
                        PYTHONPATH=str(toolchain / "python-deps"))


def support(tree, config, overrides, jobs):
    """Build C dependency headers/archive in a separate, explicitly partial SDK."""
    env = {**os.environ, **overrides, "GUNYAH_LINUX_C_SUPPORT": "1"}
    root = tree / ".cache/linux-support-sdk"
    root.mkdir(parents=True, exist_ok=True)
    (root / "INCOMPLETE-XNU-HEADERS").write_text("C dependency SDK only; excludes generated DriverKit interfaces.\n")
    logs = tree / "build/linux-support"
    logs.mkdir(parents=True, exist_ok=True)

    def run(command, name):
        print(f"Running {name}", flush=True)
        with (logs / name).open("w") as stream:
            subprocess.run([str(x) for x in command], cwd=tree, env=env, stdout=stream, stderr=subprocess.STDOUT, check=True)

    run(["make", "-C", "refer/AvailabilityVersions", "install", f"-j{jobs}",
         f"OBJROOT={logs / 'availability'}", f"SYMROOT={logs / 'availability'}", f"DSTROOT={root}",
         f"CMAKE={config['tools']['cmake']}", f"NINJA={config['tools']['ninja']}"], "01-availability.log")
    env["XNU_AVAILABILITY_PL"] = str(root / "usr/local/libexec/availability.pl")
    run([config["tools"]["python3"], "scripts/prepare-xnu-source.py"], "02-restored-headers.log")
    for source, destination in (("include", "usr/local/include"), ("private", "usr/local/include"),
                                ("private/platform", "System/Library/Frameworks/Kernel.framework/Versions/A/PrivateHeaders/platform")):
        shutil.copytree(tree / "refer/libplatform" / source, root / destination, dirs_exist_ok=True, symlinks=True)
    headers = root / "usr/local/include/os"
    headers.mkdir(parents=True, exist_ok=True)
    for header in (tree / "refer/libdispatch/os").glob("*.h"):
        result = subprocess.run([config["tools"]["unifdef"], "-DKERNEL=1", "-DOS_FIREHOSE_SPI=1",
                                 "-DOS_VOUCHER_ACTIVITY_SPI_TYPES=1", "-UOS_VOUCHER_ACTIVITY_SPI", str(header)], capture_output=True)
        if result.returncode not in (0, 1):
            raise ValueError(result.stderr.decode())
        (headers / header.name).write_bytes(result.stdout)
    run(["make", "-C", ".cache/xnu-work", "installhdrs", "SDKROOT=iphoneos", "ARCH_CONFIGS=ARM64",
         "MACHINE_CONFIGS=BCM2837", "KERNEL_CONFIGS=DEVELOPMENT", "RC_DARWIN_KERNEL_VERSION=23.6.0",
         "RC_ProjectSourceVersion=10063.141.1", f"MAKEJOBS=-j{jobs}", f"OBJROOT={logs / 'obj'}",
         f"SYMROOT={logs / 'sym'}", f"DSTROOT={root}"], "03-c-headers.log")
    run([config["tools"]["python3"], DEVICE / "scripts/build-firehose-linux.py", "--tree", tree,
         "--fakeroot", root], "04-firehose.log")
    archive = root / "usr/local/lib/kernel/libfirehose_kernel.a"
    report = dict(stage="support", host="Linux", sdk=config["sdk"], generated_driverkit=False,
                  firehose_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                  xnu_build_verified=False, xnu_boot_verified=False)
    (logs / "build-result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Linux C dependencies built: {logs}; complete XNU still requires IIG")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--toolchain", required=True, type=Path)
    parser.add_argument("--host-deps", required=True, type=Path)
    parser.add_argument("--stage", choices=("support", "baseline", "platform"), default="support")
    iig_options = parser.add_mutually_exclusive_group()
    iig_options.add_argument("--iig", type=Path, help="IOKit interface generator executable runnable on Linux")
    iig_options.add_argument("--iig-cache", type=Path, help="Pinned DriverKit-286 generated source snapshot (experimental ABI compatibility)")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        parser.error("The currently verified host is x86_64 Linux")
    tree = args.tree.resolve()
    if not (tree / "gunyah-inputs.json").is_file():
        parser.error("Run workspace.py prepare first")
    for path in (tree, args.toolchain.resolve(), args.host_deps.resolve(), DEVICE,
                 *([args.iig.absolute()] if args.iig else []),
                 *([args.iig_cache.resolve()] if args.iig_cache else [])):
        if any(c in str(path) for c in " \t\n#$"):
            parser.error("XNU make paths must not contain whitespace or make metacharacters")
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if args.iig and not os.access(args.iig, os.X_OK):
        parser.error("--iig must be an executable")
    if args.iig and args.iig.read_bytes()[:4] in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"):
        parser.error("A Mach-O IIG binary cannot run natively on Linux; provide a Linux executable or a validated launcher")
    if args.stage != "support" and not (args.iig or args.iig_cache):
        parser.error("Complete XNU requires IIG for 18 DriverKit interfaces; the Apple SDK does not include this executable. Use --stage support for independently buildable C dependencies.")
    if args.stage != "support" and not shutil.which("tcsh", path=os.pathsep.join([
            str(args.host_deps.resolve() / "usr/bin"), os.environ["PATH"]])):
        parser.error("XNU doconf requires native tcsh; install it or unpack it under --host-deps")
    # Multi-call launchers select their tool/configuration from argv[0].
    # Preserve the requested executable symlink rather than its Python target.
    iig = args.iig.absolute() if args.iig else None
    if args.iig_cache:
        try:
            verify_iig_cache(args.iig_cache.resolve(), tree / ".cache/xnu-work",
                             require_kernel_compatibility=args.stage != "support" and not args.prepare_only)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        iig = f"{sys.executable} {DEVICE / 'scripts/iig_cache.py'}"
    config, env = prepare(tree, args.toolchain.resolve(), args.host_deps.resolve(), iig)
    if args.iig_cache:
        env.update(GUNYAH_IIG_CACHE=str(args.iig_cache.resolve()),
                   GUNYAH_IIG_XNU=str(tree / ".cache/xnu-work"), GUNYAH_IIG_SDK=config["sdk"])
        config = {**config, "iig_snapshot": json.loads((DEVICE / "linux/iig-cache.json").read_text())}
    (tree / "gunyah-linux-inputs.json").write_text(json.dumps(config, indent=2) + "\n")
    if args.prepare_only:
        print(f"Prepared Linux tool selections: {tree}"); return
    if args.stage == "support":
        support(tree, config, env, args.jobs); return
    compiler_report = probe_xnu_compiler(args.toolchain.resolve() / "bin", tree / "build/linux-compiler-probe")
    if not compiler_report["ready"]:
        parser.error("Compiler lacks working XNU typed-allocation extensions; see build/linux-compiler-probe/result.json. Apple SDK headers alone do not provide these compiler builtins.")
    spec = importlib.util.spec_from_file_location("builder", DEVICE / "scripts/build-macos.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.build(tree, args.stage, args.jobs, extra_env=env)


if __name__ == "__main__":
    main()
