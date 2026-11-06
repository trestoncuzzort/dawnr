#!/usr/bin/env python3
"""Compare the C library models with the C library, plain and under ASan and UBSan.

    python3 t/native_models/cross_check.py --out NEW_DIR

The domain is in cross_check.c: exhaustive over bounded strings. A model that differs from the C library on the stated
domain fails here, whatever it does elsewhere. The native replay of a counterexample runs the same C library.
Sanitizer flags: gcc.gnu.org/onlinedocs/gcc/Instrumentation-Options.html.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
STRING_NAMES = ("strnlen", "strspn", "strcspn", "strpbrk", "strstr", "memchr", "memrchr", "strchrnul", "strsep", "strtok_r", "strtok", "strndup")
NUMBER_NAMES = ("strtol", "strtoll", "strtoul", "strtoull", "atoi", "atol", "atoll")
TABLE_NAMES = ("__ctype_b_loc", "__ctype_tolower_loc", "__ctype_toupper_loc")


def build(out: Path, name: str, flags: list[str], compiler: str) -> Path:
    """Each model file with its functions renamed, so that the driver can call both it and the C library."""
    objects = []
    plans = [("string.c", {item: "model_" + item for item in STRING_NAMES}), ("stdlib.c", {item: "model_" + item for item in NUMBER_NAMES}),
             ("ctype.c", {item: "model" + item[len("__ctype"):].replace("_", "_ctype_", 1) for item in TABLE_NAMES}),
             ("ctype_strict.c", {item: "strict" + item[len("__ctype"):].replace("_", "_ctype_", 1) for item in TABLE_NAMES})]
    for source, renames in plans:
        target = out / f"{name}-{source}.o"
        subprocess.run([compiler, "-std=gnu11", "-fno-builtin", "-c", *flags, *[f"-D{old}={new}" for old, new in renames.items()], str(HERE / source), "-o", str(target)], check=True, capture_output=True, text=True)
        objects.append(str(target))
    program = out / name
    subprocess.run([compiler, "-std=gnu11", "-fno-builtin", "-w", *flags, str(HERE / "cross_check.c"), *objects, "-o", str(program)], check=True, capture_output=True, text=True)
    return program


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True, help="new artifact directory; existing directories are refused")
    parser.add_argument("--compiler", default="gcc")
    parser.add_argument("--string-length", type=int, default=5)
    parser.add_argument("--set-length", type=int, default=3)
    parser.add_argument("--number-length", type=int, default=5)
    parser.add_argument("--sanitized-number-length", type=int, default=4)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=False)
    report = {"format": "dawnr-native-models-cross-check", "runs": {}}
    passed = True
    # A run under the sanitizers takes longer, so its longest strings are shorter.
    for name, flags, length in (("plain", ["-O2"], args.number_length), ("sanitized", ["-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all"], args.sanitized_number_length)):
        try:
            program = build(args.out, name, flags, args.compiler)
        except subprocess.CalledProcessError as error:
            print(f"{name}: did not build:\n{error.stderr[:2000]}")
            report["runs"][name] = {"built": False}
            passed = False
            continue
        # ASan's strtol interceptor sets the end pointer on an invalid base, where glibc leaves it alone. That would compare
        # the model with the sanitizer, and this run is here to find undefined behaviour in the models.
        environment = {**os.environ, "ASAN_OPTIONS": "replace_str=0"}
        run = subprocess.run([str(program), str(args.string_length), str(args.set_length), str(length)], capture_output=True, text=True, errors="replace", env=environment)
        lines = run.stdout.splitlines()
        counts = json.loads(lines[-1]) if lines and lines[-1].startswith("{") else None
        report["runs"][name] = {"exit": run.returncode, "counts": counts, "differences": lines[:-1][:40] if counts else lines[:40],
                                "domain": {"string_length": args.string_length, "set_length": args.set_length, "number_length": length}, "stderr": run.stderr[:2000]}
        passed = passed and run.returncode == 0
        print(name, "exit", run.returncode, json.dumps(counts))
        for line in report["runs"][name]["differences"]:
            print("  ", line[:170])
        if run.stderr:
            print("  stderr:", run.stderr[:800])
    (args.out / "cross-check.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
