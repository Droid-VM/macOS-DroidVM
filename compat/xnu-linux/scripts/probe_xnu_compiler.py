#!/usr/bin/env python3
"""Check the typed-allocation compiler extensions required by XNU 10063.

Ordinary ARM64 Mach-O output does not imply that a compiler can build XNU.
These are real type-layout checks, not fallback definitions of Apple builtins.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess

BUILTINS = ("__builtin_xnu_type_signature", "__builtin_xnu_type_summary",
            "__builtin_xnu_types_compatible")
SOURCE = r'''
#if !__has_builtin(__builtin_xnu_type_signature) || \
    !__has_builtin(__builtin_xnu_type_summary) || \
    !__has_builtin(__builtin_xnu_types_compatible)
#error XNU typed-allocation builtins are required
#else
#ifdef __cplusplus
#define CHECK static_assert
#else
#define CHECK _Static_assert
#endif
struct data { unsigned long long value; };
struct pointer { void *value; };
struct mixed { unsigned long long data; void *pointer; };
union overlap { unsigned long long data; void *pointer; };
CHECK(sizeof(void *) == 8, "64-bit target required");
CHECK((__builtin_xnu_type_summary(struct data) & 0xffff) == 4, "data granule");
CHECK((__builtin_xnu_type_summary(struct pointer) & 0xffff) == 2, "pointer granule");
CHECK((__builtin_xnu_type_summary(struct mixed) & 0xffff) == 6, "mixed granules");
CHECK((__builtin_xnu_type_summary(union overlap) & 0xffff) == 8, "overlap granule");
CHECK(__builtin_xnu_types_compatible(struct data, struct data), "same type");
CHECK(!__builtin_xnu_types_compatible(struct data, struct pointer), "different layouts");
/* kalloc.h implements the void-pointer wildcard with a separate OR check;
 * the builtin itself does not treat an arbitrary type as compatible with void. */
CHECK(!__builtin_xnu_types_compatible(struct data, void), "data is not void");
CHECK(__builtin_xnu_types_compatible(void, struct data) ||
      __builtin_xnu_types_compatible(void, void), "void pointer wildcard");
const char *xnu_layout_signature = __builtin_xnu_type_signature(struct mixed);
#ifdef __cplusplus
template<class T> struct layout {
    static constexpr unsigned summary = __builtin_xnu_type_summary(T);
};
CHECK((layout<struct mixed>::summary & 0xffff) == 6, "dependent type");
#endif
#endif
'''


def probe(tools, output):
    output.mkdir(parents=True, exist_ok=True)
    clang = tools / "target-clang"
    feature_source = "\n".join(f"{name} __has_builtin({name})" for name in BUILTINS)
    feature_source += "\nxnu_usage_semantics __has_attribute(xnu_usage_semantics)\n"
    result = subprocess.run([clang, "-E", "-P", "-x", "c", "-"], input=feature_source,
                            capture_output=True, text=True, timeout=60)
    (output / "features.log").write_text(result.stdout + result.stderr)
    values = dict(line.split() for line in result.stdout.splitlines() if len(line.split()) == 2)
    features = {name: values.get(name) == "1" for name in (*BUILTINS, "xnu_usage_semantics")}
    tests = {}
    for language, compiler, extension, standard in (("C", clang, "c", "gnu17"),
            ("C++", tools / "target-clang++", "cpp", "gnu++2b")):
        source, obj = output / ("typed-allocations." + extension), output / (extension + ".o")
        source.write_text(SOURCE)
        obj.unlink(missing_ok=True)
        command = [str(compiler), "-mkernel", "-ffreestanding", "-std=" + standard,
                   "-c", str(source), "-o", str(obj)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (output / (extension + ".log")).write_text(result.stdout + result.stderr)
        arm64 = obj.is_file() and obj.stat().st_size >= 16 and struct.unpack_from(
            "<4I", obj.read_bytes()) == (0xfeedfacf, 0x100000c, 0, 1)
        tests[language] = dict(command=command, returncode=result.returncode, arm64_object=arm64)
    report = dict(features=features, tests=tests,
                  ready=all(features.values()) and all(t["returncode"] == 0 and t["arm64_object"] for t in tests.values()),
                  xnu_build_verified=False, xnu_boot_verified=False)
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = probe(args.tools.resolve(), args.output.resolve())
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ready"] else 2)


if __name__ == "__main__":
    main()
