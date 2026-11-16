#!/usr/bin/env python3
"""Run pinned AppleClang under Darling on x86_64 Linux, without macOS.

fetch -> extract -> image -> start -> configure. Existing Linux LLVM/cctools
remain necessary for host programs and linking. Apple installers are extracted,
never executed. Docker's Ubuntu dependencies still require an apt repository.
"""
import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import shutil
import struct
import subprocess
import urllib.request
import zipfile

from probe_xnu_compiler import probe
from darling_mldr import prepare as prepare_mldr

DEVICE = Path(__file__).resolve().parents[1]
LOCK = json.loads((DEVICE / "linux/appleclang-sources.json").read_text())
PACKAGES = ("core", "system", "cli", "cli-gui-common", "cli-python2-common")
CLANG = "Library/Developer/CommandLineTools/usr/bin/clang"
KERNEL_RUNTIME = "Library/Developer/CommandLineTools/usr/lib/clang/15.0.0/lib/darwin/libclang_rt.cc_kext_ios.a"
KERNEL_RUNTIME_SHA256 = "1260c6dccc23da20a68fcd3991f74e968e00063837900b1b5bb30a0092ad1406"


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verified(directory, entry):
    path = directory / entry["file"]
    if path.stat().st_size != entry["size"] or sha256(path) != entry["sha256"]:
        raise ValueError(f"Package checksum mismatch: {path}")
    return path


def run(*args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def fetch(directory):
    for entry in LOCK.values():
        path = directory / entry["file"]
        if not path.exists():
            temporary = path.with_suffix(".download")
            with urllib.request.urlopen(entry["url"], timeout=90) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
            temporary.rename(path)
        verified(directory, entry)


def extract(directory):
    package = verified(directory, LOCK["apple"])
    archive = verified(directory, LOCK["darling"])
    with zipfile.ZipFile(archive) as zipped:
        for name in PACKAGES:
            filename = f"darling-{name}_{LOCK['darling']['package_version']}_amd64.deb"
            matches = [n for n in zipped.namelist() if Path(n).name == filename]
            if len(matches) != 1:
                raise ValueError(f"Missing/ambiguous package: {filename}")
            with zipped.open(matches[0]) as source, (directory / filename).open("wb") as target:
                shutil.copyfileobj(source, target)
    output = directory / "apple-tools"
    # Refuse an existing extraction: cpio otherwise skips newer files, which
    # would let stale or modified binaries masquerade as the pinned package.
    output.mkdir()
    patterns = []
    for prefix in ("./Library/Developer/CommandLineTools/", "Library/Developer/CommandLineTools/"):
        patterns.extend(prefix + p for p in ("usr/bin/clang*", "usr/lib/clang/*", "usr/lib/lib*.dylib"))
    meta = LOCK["apple"]
    with package.open("rb") as stream:
        stream.seek(meta["payload_offset"])
        if stream.read(4) != b"pbzx":
            raise ValueError("Expected PBZX payload")
        flags, = struct.unpack(">Q", stream.read(8))
        with subprocess.Popen(["cpio", "-id", "--no-absolute-filenames", "--quiet", *patterns],
                              cwd=output, stdin=subprocess.PIPE) as unpack:
            while flags & 0x1000000:
                flags, length = struct.unpack(">QQ", stream.read(16))
                data = stream.read(length)
                if len(data) != length:
                    raise ValueError("Truncated PBZX chunk")
                if data.startswith(b"\xfd7zXZ\x00"):
                    data = lzma.decompress(data)
                unpack.stdin.write(data)
            unpack.stdin.close()
            if unpack.wait() or stream.tell() != meta["payload_offset"] + meta["payload_length"]:
                raise ValueError("Payload extraction failed")
    (directory / "extracted.json").write_text(json.dumps(dict(
        sources=LOCK, clang_sha256=sha256(output / CLANG)), indent=2) + "\n")


def image(directory, tag):
    # Never send the Apple payload or workspace as Docker build context.
    context = directory / "docker-context"
    context.mkdir(exist_ok=True)
    shutil.copy2(DEVICE / "linux/Dockerfile.appleclang", context / "Dockerfile")
    verified(directory, LOCK["darling"])
    with zipfile.ZipFile(directory / LOCK["darling"]["file"]) as zipped:
        for name in PACKAGES:
            filename = f"darling-{name}_{LOCK['darling']['package_version']}_amd64.deb"
            member, = [n for n in zipped.namelist() if Path(n).name == filename]
            with zipped.open(member) as source, (context / filename).open("wb") as target:
                shutil.copyfileobj(source, target)
    prepare_mldr(context, directory)
    run("docker", "build", "--build-arg", f"BUILDER_UID={os.getuid()}", "-t", tag, context)


def start(directory, tag, container, workspace):
    if workspace == Path("/") or workspace == Path.home() or not workspace.is_dir():
        raise ValueError("Mount a project workspace, not the host root or home directory")
    extracted = json.loads((directory / "extracted.json").read_text())
    if extracted["sources"] != LOCK or sha256(directory / "apple-tools" / CLANG) != extracted["clang_sha256"]:
        raise ValueError("Extracted compiler does not match its extraction record")
    run("docker", "run", "-d", "--name", container,
        "--cap-add", "SYS_ADMIN", "--cap-add", "SYS_PTRACE",
        "--security-opt", "seccomp=unconfined", "--security-opt", "apparmor=unconfined",
        "--ulimit", "nofile=524288:524288",
        # Overlay upperdir AND sibling workdir must be on this same tmpfs.
        "--tmpfs", f"/home/builder:rw,uid={os.getuid()},gid={os.getuid()},size=768m",
        "--mount", f"type=bind,source={directory / 'apple-tools'},target=/opt/apple,readonly",
        "--mount", f"type=bind,source={workspace},target={workspace}", tag)
    run("docker", "exec", container, "timeout", "60", "darling", "shell", "/bin/mkdir", "-p", workspace.parent)
    # Create inside Darling's mounted overlay, never modify the upperdir behind
    # its back: that causes stale overlay directory handles on Linux.
    run("docker", "exec", container, "darling", "shell", "/bin/ln", "-s",
        "/Volumes/SystemRoot" + str(workspace), workspace)
    (directory / "runtime.json").write_text(json.dumps(dict(
        workspace=str(workspace), container=container, sources=LOCK,
        clang_sha256=extracted["clang_sha256"],
        mldr=json.loads(run("docker", "exec", container, "cat",
                            "/usr/share/darling-mldr-source.json",
                            capture_output=True, text=True).stdout),
        image_id=run("docker", "inspect", "--format", "{{.Image}}", container,
                     capture_output=True, text=True).stdout.strip()), indent=2) + "\n")


def configure(directory, toolchain):
    backend = json.loads((directory / "runtime.json").read_text())
    runtime = directory / "apple-tools" / KERNEL_RUNTIME
    if sha256(runtime) != KERNEL_RUNTIME_SHA256:
        raise ValueError("Apple kernel compiler runtime does not match the pinned CLT package")
    backend["kernel_runtime"] = dict(path=str(runtime), sha256=KERNEL_RUNTIME_SHA256)
    workspace = Path(backend["workspace"])
    if not toolchain.is_relative_to(workspace):
        raise ValueError("Toolchain and build tree must be in the mounted workspace")
    path = toolchain / "bin/linux-toolchain.json"
    original = path.read_text()
    config = json.loads(original)
    config["appleclang"] = backend
    path.write_text(json.dumps(config, indent=2) + "\n")
    previous = Path.cwd()
    try:
        os.chdir(workspace)
        version = run(toolchain / "bin/target-clang", "--version", capture_output=True, text=True).stdout
        if LOCK["apple"]["compiler_version"] not in version:
            raise ValueError(f"Unexpected compiler: {version}")
        (directory / "compiler-version.log").write_text(version)
        if not probe(toolchain / "bin", directory / "compiler-probe")["ready"]:
            raise ValueError("XNU compiler probe failed; original toolchain configuration restored")
    except BaseException:
        path.write_text(original)
        raise
    finally:
        os.chdir(previous)
    print("AppleClang configured; typed-allocation probes passed, full XNU build/boot remain unverified")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fetch", "extract", "image", "start", "configure"))
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--toolchain", type=Path)
    parser.add_argument("--image", default="gunyah-appleclang:20260608")
    parser.add_argument("--container", default="gunyah-appleclang")
    args = parser.parse_args()
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if args.action in ("fetch", "extract"):
        globals()[args.action](directory)
    elif args.action == "image":
        image(directory, args.image)
    elif args.action == "start":
        if not args.workspace:
            parser.error("start requires --workspace")
        start(directory, args.image, args.container, args.workspace.resolve())
    else:
        if not args.toolchain:
            parser.error("configure requires --toolchain")
        configure(directory, args.toolchain.resolve())


if __name__ == "__main__":
    main()
