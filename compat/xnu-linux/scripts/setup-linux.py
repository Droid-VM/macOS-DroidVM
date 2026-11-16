#!/usr/bin/env python3
"""Build pinned Linux Mach-O tools and configure an external iPhoneOS SDK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

DEVICE = Path(__file__).resolve().parents[1]
LOCK = json.loads((DEVICE / "linux/sources.json").read_text())
PARSER_URL = 'https://files.pythonhosted.org/packages/b5/29/c8212e5b3f7e0f164b425e19f0b58780751d744773805dc35c5b16487a30/openstep_parser-2.0.3-py3-none-any.whl'
PARSER_SHA256 = "f219954501e92ced2d3589781201786a930e9a8738128f193b4a425bbee517be"


def run(argv, cwd=None, log=None):
    if log:
        print(f"Running {log.name}", flush=True)
        with log.open("w") as stream:
            subprocess.run([str(x) for x in argv], cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, check=True)
    else:
        subprocess.run([str(x) for x in argv], cwd=cwd, check=True)


def fetch(sources, sdk_mirror):
    sources.mkdir(parents=True, exist_ok=True)
    for name, entry in LOCK.items():
        if "sparse_path" in entry and not sdk_mirror:
            continue
        path = sources / name
        if not path.exists():
            run(["git", "init", path])
            run(["git", "-C", path, "remote", "add", "origin", entry["url"]])
            run(["git", "-C", path, "fetch", "--depth", "1", "--filter=blob:none", "origin", entry["commit"]])
            if "sparse_path" in entry:
                run(["git", "-C", path, "sparse-checkout", "set", entry["sparse_path"]])
            run(["git", "-C", path, "checkout", "--detach", "FETCH_HEAD"])
        verify(path, entry["commit"])


def verify(path, commit):
    actual = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"], text=True)
    if actual != commit or dirty:
        raise ValueError(f"Expected clean pinned source {path}: {commit}")


def setup(sources, output, sdk, llvm_bin, host_bin, jobs):
    output.mkdir(parents=True, exist_ok=True)
    logs = output / "logs"
    logs.mkdir(exist_ok=True)
    prefix = output / "toolchain"
    for name in ("bootstrap_cmds-linux", "cctools-port-linux"):
        verify(sources / name, LOCK[name]["commit"])
    settings = json.loads((sdk / "SDKSettings.json").read_text())
    # macos/compat: any iPhoneOS SDK from 17 on (k27 builds with 26.5; the check only guards against a wrong SDK).
    if "iphoneos" not in settings.get("SupportedTargets", {}) or int(settings["Version"].split(".")[0]) < 17:
        raise ValueError("This stage requires an iPhoneOS 17 or later SDK")
    for name in ("usr/include/TargetConditionals.h", "usr/include/mach/mach_types.h", "usr/include/sys/cdefs.h"):
        if not (sdk / name).is_file():
            raise ValueError(f"Incomplete SDK: {name}")
    for name in ("mig", "cctools"):
        work = output / (name + "-work")
        source = sources / ("bootstrap_cmds-linux" if name == "mig" else "cctools-port-linux")
        if not work.exists():
            run(["git", "clone", "--no-hardlinks", source, work])
        if name == "mig":
            run(["autoreconf", "--install"], work, logs / "mig-autoreconf.log")
            run(["./configure", f"--prefix={prefix}"], work, logs / "mig-configure.log")
        else:
            work /= "cctools"
            run(["./configure", f"--prefix={prefix}", "--target=aarch64-apple-darwin", "--disable-tapi-support",
                 f"--with-llvm-config={llvm_bin / 'llvm-config'}", f"CC={llvm_bin / 'clang'}",
                 f"CXX={llvm_bin / 'clang++'}"], work, logs / "cctools-configure.log")
        run(["make", f"-j{jobs}"], work, logs / (name + "-build.log"))
        run(["make", "install"], work, logs / (name + "-install.log"))
    python_deps = output / "python-deps"
    wheel = output / "openstep_parser-2.0.3-py3-none-any.whl"
    if not wheel.exists():
        wheel.write_bytes(urllib.request.urlopen(PARSER_URL, timeout=60).read())
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != PARSER_SHA256:
        raise ValueError("OpenStep parser download hash mismatch")
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(python_deps)
    binpath = output / "bin"
    binpath.mkdir(exist_ok=True)
    for name in ("xcrun", "target-clang", "target-clang++", "plutil", "ditto"):
        path = binpath / name
        path.unlink(missing_ok=True)
        path.symlink_to(DEVICE / "linux/darwin-tool.py")
    tools = {}
    for name, binary in {"clang": binpath / "target-clang", "clang++": binpath / "target-clang++",
                         "mig": prefix / "bin/mig", "migcom": prefix / "bin/migcom"}.items():
        tools[name] = str(binary)
    for name in ("ar", "nm", "lipo", "libtool", "otool", "strip", "nmedit"):
        tools[name] = str(prefix / "bin" / ("aarch64-apple-darwin-" + name))
    for name in ("git", "cmake", "ninja", "unifdef", "python3"):
        value = shutil.which(name, path=str(host_bin) + os.pathsep + os.environ["PATH"])
        if not value:
            raise ValueError(f"Missing host tool: {name}")
        tools[name] = value
    tools["dsymutil"] = str(llvm_bin / "dsymutil")
    config = dict(sdk=str(sdk), sdk_version=settings["Version"], clang=str(llvm_bin / "clang"),
                  clangxx=str(llvm_bin / "clang++"), ld=str(prefix / "bin/aarch64-apple-darwin-ld"),
                  tools=tools, python_deps=str(python_deps), sources=LOCK,
                  sdk_settings_sha256=hashlib.sha256((sdk / "SDKSettings.json").read_bytes()).hexdigest(),
                  xnu_build_verified=False)
    for binary in (config["clang"], config["clangxx"], config["ld"], *tools.values()):
        if not os.access(binary, os.X_OK):
            raise ValueError(f"Missing executable {binary}")
    (binpath / "linux-toolchain.json").write_text(json.dumps(config, indent=2) + "\n")
    print(f"Linux tools ready: {binpath}; XNU compilation has not been verified")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fetch", "build"))
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--sdk-mirror", action="store_true")
    parser.add_argument("--sdk", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--llvm-bin", type=Path, default=Path("/usr/lib/llvm-21/bin"))
    parser.add_argument("--host-bin", type=Path, default=Path("/usr/bin"))
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if args.action == "fetch":
        fetch(args.sources.resolve(), args.sdk_mirror)
    else:
        if not args.sdk or not args.output or args.jobs < 1:
            parser.error("build requires --sdk, --output and positive --jobs")
        setup(args.sources.resolve(), args.output.resolve(), args.sdk.resolve(), args.llvm_bin.resolve(), args.host_bin.resolve(), args.jobs)


if __name__ == "__main__":
    main()
