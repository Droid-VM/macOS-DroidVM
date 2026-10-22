#!/usr/bin/env python3
"""Fetch and replay a pinned DriverKit-286 source snapshot; not an IIG compiler.

The snapshot is a third-party HTML rendering of Apple's generated sources.
Its 18 .iig inputs match our XNU inputs byte for byte. Generator command-line
provenance and runtime ABI compatibility are NOT independently authenticated.
Only the fixed Gunyah build inputs/arguments are accepted.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import sys
import urllib.request

DEVICE = Path(__file__).resolve().parents[1]
LOCK = DEVICE / "linux/iig-cache.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


class CodeTable(HTMLParser):
    """Read only numbered source cells, preserving whitespace and entities."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_table = self.in_cell = False
        self.lines = []
        self.number = None
        self.cell = []
        self.hint_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.hint_depth:
            self.hint_depth += 1
            return
        if tag == "table" and attrs.get("class") == "code":
            if self.lines or self.in_table:
                raise ValueError("Multiple code tables")
            self.in_table = True
        if not self.in_table:
            return
        if tag == "th":
            self.number = int(attrs["id"])
        if tag == "td":
            if self.number != len(self.lines) + 1:
                raise ValueError("Missing/duplicate source line")
            self.in_cell = True
            self.cell = []
        # Browser-added parameter labels are not part of the source.
        if tag == "span" and attrs.get("class") == "inlayHint":
            self.hint_depth = 1

    def handle_endtag(self, tag):
        if self.hint_depth:
            self.hint_depth -= 1
            return
        if tag == "td" and self.in_cell:
            self.lines.append("".join(self.cell))
            self.in_cell = False
            self.number = None
        if tag == "table":
            self.in_table = False

    def handle_data(self, data):
        if self.in_cell and not self.hint_depth:
            self.cell.append(data)


def extract(data):
    parser = CodeTable()
    parser.feed(data.decode("utf-8"))
    parser.close()
    if not parser.lines or parser.in_cell or parser.in_table:
        raise ValueError("Incomplete source table")
    return ("\n".join(parser.lines) + "\n").encode()


def verify(cache, xnu, require_kernel_compatibility=False):
    lock = json.loads(LOCK.read_text())
    definitions = xnu / "iokit/DriverKit"
    expected = {name for name in lock["inputs"] if name.endswith(".iig")}
    if {str(p.relative_to(xnu)) for p in definitions.glob("*.iig")} != expected:
        raise ValueError("DriverKit interface set changed; cached IIG cannot regenerate it")
    for name, digest in lock["inputs"].items():
        if sha((xnu / name).read_bytes()) != digest:
            raise ValueError(f"IIG cache input mismatch: {name}")
    for name, entry in lock["outputs"].items():
        if sha((cache / name).read_bytes()) != entry["source_sha256"]:
            raise ValueError(f"IIG cache output mismatch: {name}")
    if require_kernel_compatibility and lock.get("known_kernel_abi_incompatibilities"):
        raise ValueError("IIG snapshot is incompatible with the target kernel ABI: " +
                         "; ".join(lock["known_kernel_abi_incompatibilities"]) +
                         ". Header/source research remains available with --prepare-only; full builds need a compatible IIG via --iig.")
    return lock


def fetch(cache, xnu):
    lock = json.loads(LOCK.read_text())
    cache.mkdir(parents=True, exist_ok=True)
    raw = cache / "html"
    raw.mkdir(exist_ok=True)
    for name, entry in lock["outputs"].items():
        page = raw / (name + ".html")
        if not page.exists():
            page.write_bytes(urllib.request.urlopen(entry["url"], timeout=60).read())
        data = page.read_bytes()
        if sha(data) != entry["html_sha256"]:
            raise ValueError(f"Downloaded HTML changed: {page}")
        source = extract(data)
        if sha(source) != entry["source_sha256"]:
            raise ValueError(f"Source extraction mismatch: {name}")
        (cache / name).write_bytes(source)
    verify(cache, xnu)
    (cache / "provenance.json").write_text(json.dumps(lock, indent=2) + "\n")
    print(f"Verified 36 generated source files: {cache}")


def emit(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--def", dest="definition", required=True, type=Path)
    parser.add_argument("--header", required=True, type=Path)
    parser.add_argument("--impl", required=True, type=Path)
    parser.add_argument("--framework-name", choices=("DriverKit",), required=True)
    split = argv.index("--")
    args = parser.parse_args(argv[:split])
    flags = argv[split + 1:]
    cache = Path(os.environ["GUNYAH_IIG_CACHE"])
    xnu = Path(os.environ["GUNYAH_IIG_XNU"])
    sdk = Path(os.environ["GUNYAH_IIG_SDK"])
    lock = verify(cache, xnu)
    if sha((sdk / "SDKSettings.json").read_bytes()) != lock["sdk_settings_sha256"]:
        raise ValueError("Unsupported SDK for this IIG snapshot")
    defines = {"-D__IIG=1", "-DDRIVERKIT_PRIVATE=1", "-DPRIVATE_WIFI_ONLY=1", "-DXNU_PLATFORM_iPhoneOS"}
    found = set()
    includes = set()
    rest = []
    for flag in flags:
        if flag.startswith("-I"):
            includes.add(Path(flag[2:]).resolve())
        elif flag in defines:
            found.add(flag)
        else:
            rest.append(flag)
    required = {xnu / p for p in ("iokit", "osfmk", "bsd", "EXTERNAL_HEADERS")}
    # The remaining -I is OBJROOT/bsd; no other search paths are accepted.
    obj_bsd = includes - required
    tree = xnu.parent.parent
    if (found != defines or not required <= includes or len(obj_bsd) != 1 or
            any(p.name != "bsd" or not p.is_relative_to(tree / "build") for p in obj_bsd) or
            rest != ["-isysroot", str(sdk), "-x", "c++", "-std=gnu++2b"]):
        raise ValueError(f"Unreviewed IIG arguments: {flags}")
    definition = args.definition.resolve()
    if definition.parent != xnu / "iokit/DriverKit":
        raise ValueError("IIG definition must come from the verified source directory")
    for destination, name in ((args.header, definition.stem + ".h"),
                              (args.impl, definition.name + ".cpp")):
        if name not in lock["outputs"]:
            raise ValueError(f"Unknown generated output: {name}")
        shutil.copyfile(cache / name, destination)


def main():
    if "--def" in sys.argv:
        emit(sys.argv[1:])
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fetch", "verify"))
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--xnu", required=True, type=Path)
    args = parser.parse_args()
    if args.action == "fetch":
        fetch(args.cache.resolve(), args.xnu.resolve())
    else:
        verify(args.cache.resolve(), args.xnu.resolve())
        print("IIG snapshot bytes verified; known target kernel ABI incompatibilities prevent full builds")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        sys.exit(f"IIG snapshot rejected: {error}")
