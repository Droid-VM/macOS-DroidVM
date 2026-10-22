#!/usr/bin/env python3
"""Small, strict adapters for Darwin build commands on a Linux host.

The generated tool links live beside linux-toolchain.json. Unsupported commands
fail; this adapter never substitutes successful no-ops for missing build tools.
"""
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys


def execute(argv):
    os.execv(str(argv[0]), [str(x) for x in argv])


def darling_command(config, program):
    backend = config["appleclang"]
    cwd = Path.cwd().resolve()
    if not cwd.is_relative_to(backend["workspace"]):
        raise ValueError("Darling working directory must be inside its mounted workspace")
    return ["/usr/bin/docker", "exec", "-i", backend["container"], "darling", "shell",
            "/bin/bash", "--noprofile", "--norc", "-c",
            'cd -- "$1" && shift && exec "$@"', "darling-tool", str(cwd), program]


def plist(path):
    data = Path(path).read_bytes()
    if data.startswith((b"bplist", b"<?xml")):
        return plistlib.loads(data)
    from openstep_parser import OpenStepDecoder
    return OpenStepDecoder.ParseFromString(data.decode())


def main():
    invoked = Path(sys.argv[0]).absolute()
    config = json.loads((invoked.parent / "linux-toolchain.json").read_text())
    sys.path.insert(0, config["python_deps"])
    args = sys.argv[1:]
    name = invoked.name
    if name == "target-iig":
        execute([*darling_command(config, config["apple_iig"]["binary"]), *args])
    if name in ("target-clang", "target-clang++"):
        command = [config["clangxx" if name.endswith("++") else "clang"]]
        compile_only = any(x in ("-c", "-E", "-S", "-fsyntax-only", "--version", "-v") for x in args)
        if config.get("appleclang") and compile_only:
            compiler = "/Volumes/SystemRoot/opt/apple/Library/Developer/CommandLineTools/usr/bin/"
            compiler += "clang++" if name.endswith("++") else "clang"
            # Keep host absolute paths valid in Darling, including response files,
            # dependency files and -MJ records. Never interpolate compiler args
            # into shell code. Native LLVM still drives the Linux Mach-O linker.
            command = darling_command(config, compiler)
        if not any(x in ("-target", "--target") or x.startswith("--target=") for x in args):
            command += ["-target", os.environ.get("GUNYAH_APPLE_TARGET", "arm64-apple-ios16.0")]
        if not compile_only:
            command += ["-fuse-ld=" + config["ld"]]
        # Newer UniXNU builders pass -Werror with -Wno-<flag> names the older Apple clang in Darling does not know.
        tail = ["-Wno-error=unknown-warning-option"] if compile_only else []
        execute([*command, *args, *tail])
    if name == "xcrun":
        while args and args[0] in ("-sdk", "--sdk", "-verbose", "--verbose"):
            option = args.pop(0)
            if option in ("-sdk", "--sdk"):
                sdk = args.pop(0)
                if sdk == "macosx" and args in (["--show-sdk-path"], ["-show-sdk-path"]):
                    # Only a header lookup (TargetConditionals.h); the iPhoneOS SDK carries the same file.
                    print(config["sdk"]); return
                if sdk == "macosx" and args in (["--show-sdk-version"], ["-show-sdk-version"]):
                    print(config["sdk_version"]); return   # recorded in an audit report only
                if sdk not in ("iphoneos", config["sdk"]):
                    raise ValueError(f"Unsupported SDK {sdk}; host programs must use native Linux tools")
        if args == ["--show-sdk-path"] or args == ["-show-sdk-path"]:
            print(config["sdk"]); return
        if args == ["--show-sdk-version"] or args == ["-show-sdk-version"]:
            print(config["sdk_version"]); return
        if args and args[0] in ("-find", "--find"):
            if len(args) != 2:
                raise ValueError("Invalid tool lookup")
            print(config["tools"][args[1]]); return
        if args and args[0] == "dwarfdump":
            # llvm-dwarfdump prints the same DW_AT_* records the storage ABI audit parses.
            execute([str(Path(config["clang"]).parent / "llvm-dwarfdump"), *args[1:]])
        if args and args[0] == "c++filt":
            # Itanium demangling is host-independent; the binding builders only pipe symbol names through it.
            execute([str(Path(config["clang"]).parent / "llvm-cxxfilt"), *args[1:]])
        if not args or args[0] not in config["tools"]:
            raise ValueError(f"Unsupported xcrun invocation: {args}")
        execute([config["tools"][args[0]], *args[1:]])
    if name == "plutil":
        if len(args) in (2, 3) and args[0] == "-lint":
            silent = args[1:2] == ["-s"]
            paths = args[2:] if silent else args[1:]
            if len(paths) != 1 or paths[0].startswith("-"):
                raise ValueError(f"Unsupported plutil invocation: {args}")
            if plist(paths[0]) is None:
                raise ValueError("Empty property list")
            if not silent:
                print(f"{paths[0]}: OK")
            return
        if len(args) == 4 and args[0] == "-convert" and args[2] == "-s":
            # XNU combines symbolsets in-place after checking their XML syntax.
            args = [args[0], args[1], "-o", args[3], args[3]]
        if len(args) == 5 and args[:1] == ["-convert"] and args[2] == "-o":
            value = plist(args[4])
            formats = {"binary1": plistlib.FMT_BINARY, "xml1": plistlib.FMT_XML}
            data = (json.dumps(value).encode() if args[1] == "json"
                    else plistlib.dumps(value, fmt=formats[args[1]]))
            if args[3] == "-":
                sys.stdout.buffer.write(data)
            else:
                Path(args[3]).write_bytes(data)
            return
        if len(args) == 5 and args[0] == "-extract" and args[2:4] == ["raw", "-n"]:
            value = plist(args[4])
            for key in args[1].split("."):
                value = value[key]
            print(value, end=""); return
        raise ValueError(f"Unsupported plutil invocation: {args}")
    if name == "ditto":
        if len(args) != 2 or args[0].startswith("-"):
            raise ValueError("Only directory/file copying is supported")
        source, destination = map(Path, args)
        if source.is_dir():
            shutil.copytree(source, destination, symlinks=True, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
        return
    raise ValueError(f"Unknown adapter: {name}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        sys.exit(f"Darwin tool adapter: {error}")
