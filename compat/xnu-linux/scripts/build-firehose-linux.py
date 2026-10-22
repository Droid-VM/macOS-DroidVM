#!/usr/bin/env python3
"""Build the pinned libdispatch kernel firehose target without xcodebuild."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--fakeroot", type=Path)
    args = parser.parse_args()
    tree = args.tree.resolve()
    fakeroot = args.fakeroot.resolve() if args.fakeroot else tree / ".cache/fakeroot"
    sdk = subprocess.check_output(["xcrun", "--sdk", "iphoneos", "--show-sdk-path"], text=True).strip()
    source = tree / "refer/libdispatch"
    # This source list is deliberately bound to the pinned project. Fail if the
    # Xcode target changes instead of silently omitting a compilation unit.
    from openstep_parser import OpenStepDecoder
    project = OpenStepDecoder.ParseFromFile((source / "libdispatch.xcodeproj/project.pbxproj").open())
    objects = project["objects"]
    target = next(value for value in objects.values() if value.get("isa") == "PBXNativeTarget" and value.get("name") == "libfirehose_kernel")
    phase = next(objects[key] for key in target["buildPhases"] if objects[key]["isa"] == "PBXSourcesBuildPhase")
    units = [objects[objects[key]["fileRef"]]["path"] for key in phase["files"]]
    if units != ["firehose_buffer.c"]:
        raise ValueError(f"Unexpected firehose sources: {units}")
    output = fakeroot / "usr/local/lib/kernel"
    output.mkdir(parents=True, exist_ok=True)
    work = tree / "build/firehose-linux" / fakeroot.name
    work.mkdir(parents=True, exist_ok=True)
    framework = fakeroot / "System/Library/Frameworks/Kernel.framework/Versions/A"
    obj = work / "firehose_buffer.o"
    resource = subprocess.check_output(["xcrun", "clang", "-print-resource-dir"], text=True).strip()
    includes = [source, framework / "PrivateHeaders", framework / "Headers", fakeroot / "usr/local/include/os",
                fakeroot / "usr/local/include/firehose", tree / ".cache/xnu-work/EXTERNAL_HEADERS",
                Path(sdk) / "usr/include", Path(resource) / "include"]
    command = ["xcrun", "clang", "-target", "arm64-apple-ios17.0", "-isysroot", sdk,
               "-mkernel", "-ffreestanding", "-nostdinc", "-fno-stack-protector", "-mno-implicit-float", "-fblocks",
               "-O2", "-std=gnu11", "-DKERNEL=1", "-DDISPATCH_USE_DTRACE=0",
               "-DOS_ATOMIC_CONFIG_MEMORY_ORDER_DEPENDENCY=1", "-DOS_ATOMIC_CONFIG_STARVATION_FREE_ONLY=0",
               "-Wno-packed", "-Wno-deprecated-declarations"]
    for path in includes:
        command.extend(["-I", str(path)])
    command.extend(["-c", str(source / "src/firehose/firehose_buffer.c"), "-o", str(obj)])
    (work / "compile-command.json").write_text(json.dumps(command, indent=2) + "\n")
    subprocess.run(command, check=True)
    if struct.unpack_from("<4I", obj.read_bytes()) != (0xfeedfacf, 0x100000c, 0, 1):
        raise ValueError("Firehose object must be ordinary ARM64 Mach-O")
    archive = output / "libfirehose_kernel.a"
    archive.unlink(missing_ok=True)
    subprocess.run(["xcrun", "ar", "rcs", archive, obj], check=True)
    symbols = subprocess.check_output(["xcrun", "nm", "-g", "-U", "-j", archive], text=True)
    if not {"___firehose_buffer_create", "___firehose_buffer_tracepoint_reserve", "___firehose_buffer_tracepoint_flush"} <= set(symbols.split()):
        raise ValueError("Missing expected real firehose implementation")
    (work / "build-result.json").write_text(json.dumps(dict(archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        sources=units, architecture="arm64", compiled=True, xnu_build_verified=False), indent=2) + "\n")
    print(f"Built real kernel firehose archive: {archive}")


if __name__ == "__main__":
    main()
