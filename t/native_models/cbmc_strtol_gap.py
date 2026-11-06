#!/usr/bin/env python3
"""Does CBMC's strtol model agree with the C library? Compile the model's own text natively beside it.

    python3 t/native_models/cbmc_strtol_gap.py --out NEW_DIR

The model is fetched from CBMC's source at the pinned tag, or read from --library, cut out of stdlib.c unchanged, and
renamed by a macro. Both are run on the same strings. C11 7.22.1.4 says which is right where they differ.
The source: github.com/diffblue/cbmc, src/ansi-c/library/stdlib.c at tag cbmc-6.11.0.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

URL = "https://raw.githubusercontent.com/diffblue/cbmc/cbmc-6.11.0/src/ansi-c/library/stdlib.c"
DRIVER = r'''
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define strtol cbmc_strtol
MODEL
#undef strtol
extern long strtol(const char *, char **, int);
static const char *const strings[] = {"", "+", "-", " ", "  +", "0", "00", "9", "19", "08", "0x", "0X", "0xg", "0x1", "-0x", "+0x1g", "12", "-12", " 12", "12 ", "1a", "z",
    "9223372036854775807", "9223372036854775808", "-9223372036854775808", "-9223372036854775809", "99999999999999999999x",
    "0000000000000000000000000000000000001", "00000000000000000000000000000000000000000000012"};
static const int bases[] = {0, 2, 8, 10, 16, 36};
int main(void) {
    int total = 0, differ = 0, unset_total = 0;
    for (size_t s = 0; s < sizeof strings / sizeof *strings; ++s) {
        for (size_t b = 0; b < sizeof bases / sizeof *bases; ++b) {
            const char *in = strings[s];
            char *end_m = (char *)1, *end_c = (char *)1;
            errno = 0; long m = cbmc_strtol(in, &end_m, bases[b]); int em = errno;
            errno = 0; long c = strtol(in, &end_c, bases[b]); int ec = errno;
            int unset = end_m == (char *)1;
            ++total;
            unset_total += unset;
            if (m != c || unset || end_m != end_c || em != ec) {
                ++differ;
                printf("base %2d \"%s\": model %ld end %ld errno %d; C library %ld end %ld errno %d\n", bases[b], in, m, unset ? -1L : (long)(end_m - in), em, c, (long)(end_c - in), ec);
            }
        }
    }
    printf("%d of %d differ; the end pointer is left unset on %d\n", differ, total, unset_total);
    return 0;
}
'''


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True, help="new artifact directory; existing directories are refused")
    parser.add_argument("--library", type=Path, help="a copy of CBMC's stdlib.c; fetched from the pinned tag when absent")
    parser.add_argument("--compiler", default="gcc")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=False)
    if args.library:
        text = args.library.read_text()
    else:
        with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "dawnr-native-models"}), timeout=60) as response:
            text = response.read().decode()
    block = next(part for part in re.split(r"(?m)^/\* FUNCTION: ", text) if part.startswith("strtol "))
    # Compiled as it stands, with only the marker that means something to CBMC removed.
    model = block[block.index("long strtol("):].replace("__CPROVER_HIDE:;", "")
    (args.out / "compare.c").write_text(DRIVER.replace("MODEL", model))
    subprocess.run([args.compiler, "-std=gnu11", "-O0", "-w", "compare.c", "-o", "compare"], cwd=args.out, check=True, capture_output=True, text=True)
    run = subprocess.run([str((args.out / "compare").resolve())], capture_output=True, text=True, check=True)
    (args.out / "strtol-gap.txt").write_text(run.stdout)
    lines = run.stdout.splitlines()
    print("\n".join(lines[:12]))
    print("...")
    print(lines[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
