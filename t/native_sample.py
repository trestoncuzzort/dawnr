#!/usr/bin/env python3
"""Run a case's harness natively over many generated inputs, under ASan and UBSan.

    python3 t/native_sample.py CASE_DIR --variant fixed --count 1000000 --out NEW_DIR

A `complete` verdict rests on CBMC's models, and a counterexample is the only result the real code ever sees. This compiles the
same prelude, definitions and harness natively, so that the real C library and compiler get a say over the case's whole
domain: not proof, a sample of it. An assumption rejects a draw. A failed assertion is counted and its input kept. A sanitizer
report or a stop ends the run and names the input.

Prior art: libFuzzer's in-process loop (llvm.org/docs/LibFuzzer.html), without coverage feedback, because this samples the stated
domain. __sanitizer_set_death_callback and handle_abort: github.com/google/sanitizers/wiki/SanitizerCommonFlags.
INVENTED: the mix of values drawn; t/PREDICT-2026-11-05-native-sample.md measures it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_case as cases
import native_check as native

FORMAT = "dawnr-native-sample-v1"
RUNTIME = r'''
#include <limits.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern void __sanitizer_set_death_callback(void (*)(void));
const char *__asan_default_options(void) { return "detect_leaks=0:handle_abort=1:allocator_may_return_null=1"; }
const char *__ubsan_default_options(void) { return "print_stacktrace=0"; }
'''
LOOP = r'''
static jmp_buf dawnr_jump;
static unsigned long long dawnr_state, dawnr_ran, dawnr_rejected, dawnr_failures, dawnr_draw_number;
static int dawnr_inside;
static const char *const dawnr_names[] = {NAMES};
static unsigned long long dawnr_values[COUNT + 1];
static int dawnr_failed_this_draw, dawnr_profile;

static void dawnr_show_input(const char *label)
{
    printf("%s draw %llu:", label, dawnr_draw_number);
    for (int i = 0; i < COUNT; ++i) {
        printf(" %s=%llx", dawnr_names[i], dawnr_values[i]);
    }
    printf("\n");
}

static void dawnr_failure(const char *name)
{
    ++dawnr_failures;
    dawnr_failed_this_draw = 1;
    static unsigned long long shown;
    if (shown++ < 20) {
        printf("native-sample: assertion failed: %s\n", name);
        dawnr_show_input("native-sample: input");
    }
}

static void dawnr_on_death(void)
{
    dawnr_show_input("native-sample: died on");
}

/* UBSan reports through this hook and does not call the death callback (compiler-rt's ubsan_diag). */
void __ubsan_on_report(void)
{
    dawnr_show_input("native-sample: died on");
}

static void dawnr_at_exit(void)
{
    if (dawnr_inside) {
        dawnr_show_input("native-sample: stopped on");
    }
}

/* xorshift64*, from Vigna, arXiv:1402.6246: a seeded stream, so a run can be repeated. */
static unsigned long long dawnr_random(void)
{
    dawnr_state ^= dawnr_state >> 12;
    dawnr_state ^= dawnr_state << 25;
    dawnr_state ^= dawnr_state >> 27;
    return dawnr_state * 2685821657736338717ULL;
}

/* Edges of a type, small values and uniform ones, and for a byte, the text that parsers read. */
static unsigned long long dawnr_draw(int bytes)
{
    static const unsigned long long edges[] = {0, 1, 2, 3, 7, 8, 10, 15, 16, 31, 32, 63, 64, 100, 127, 128, 255, 256, 1023, 1024, 32767, 32768, 65535, 65536,
                                               2147483647ULL, 2147483648ULL, 4294967295ULL, 4294967296ULL, 9223372036854775807ULL, 9223372036854775808ULL, 18446744073709551615ULL, 18446744073709551614ULL};
    static const char text[] = "0123456789 +-\t\nabfxzAFXZ.%";
    unsigned long long pick = dawnr_random() >> 8, value;
    /* Drawing each byte alone rarely satisfies a harness that needs several digits at once, so a whole draw can lean one way. */
    if (dawnr_profile == 1 && bytes == 1) {
        return (unsigned long long)'0' + (pick >> 8) % 10;
    }
    if (dawnr_profile == 2 && bytes == 1) {
        return (unsigned char)text[(pick >> 8) % (sizeof text - 1)];
    }
    if (dawnr_profile == 3) {
        return (pick >> 8) % 16;
    }
    switch (pick % 8) {
    case 0: case 1: case 2:
        value = edges[(pick >> 8) % (sizeof edges / sizeof *edges)];
        break;
    case 3:
        value = dawnr_random() >> 60;
        break;
    case 4: case 5:
        value = bytes == 1 ? (unsigned char)text[(pick >> 8) % (sizeof text - 1)] : dawnr_random() >> (64 - 8 * (((pick >> 8) % 8) + 1));
        break;
    default:
        value = dawnr_random();
        break;
    }
    return bytes >= 8 ? value : value & ((1ULL << (8 * bytes)) - 1);
}

static unsigned long long dawnr_between(unsigned long long low, unsigned long long high)
{
    return low + dawnr_random() % (high - low + 1);
}

static unsigned long long dawnr_not_zero(int bytes)
{
    unsigned long long value = dawnr_draw(bytes);
    return value ? value : 97;
}
'''
MAIN = r'''
int main(int argc, char **argv)
{
    if (argc != 3) {
        return 2;
    }
    unsigned long long total = strtoull(argv[1], 0, 10);
    dawnr_state = strtoull(argv[2], 0, 10) * 2 + 1;
    setvbuf(stdout, 0, _IONBF, 0);
    __sanitizer_set_death_callback(dawnr_on_death);
    atexit(dawnr_at_exit);
    for (dawnr_draw_number = 0; dawnr_draw_number < total; ++dawnr_draw_number) {
        dawnr_profile = (int)(dawnr_random() >> 62);
DRAWS
        dawnr_failed_this_draw = 0;
        dawnr_inside = 1;
        if (setjmp(dawnr_jump) == 0) {
            dawnr_body(ARGUMENTS);
            ++dawnr_ran;
        } else {
            ++dawnr_rejected;
        }
        dawnr_inside = 0;
    }
    printf("{\"draws\": %llu, \"reached_the_end\": %llu, \"rejected\": %llu, \"failed_assertions\": %llu}\n", total, dawnr_ran, dawnr_rejected, dawnr_failures);
    return 0;
}
'''


def draw_statement(case: dict, item: dict, index: int) -> str:
    """How one scalar is drawn. A length draws inside its stated range, and an element of a string draws no NUL."""
    name, kind = item["name"], item["type"]
    shapes = {source["name"]: cases.shape_of(source) for source in case["inputs"] if cases.shape_of(source) is not None}
    strings = {source["name"] for source in case["inputs"] if "string" in source}
    if name.endswith("_len") and name[:-4] in shapes:
        shape = shapes[name[:-4]]
        value = f"dawnr_between({shape.get('min', 0)}, {shape['max']})"
    else:
        value = f"dawnr_draw((int)sizeof({kind}))"
        owner = re.fullmatch(r"(.+)_e[0-9]+", name)
        if owner and owner.group(1) in strings:
            value = f"dawnr_not_zero((int)sizeof({kind}))"
    return f"        dawnr_values[{index}] = {value};\n        memcpy(&{name}, &dawnr_values[{index}], sizeof {name});\n"


def sample_unit(case: dict, parts: dict) -> str:
    inputs = cases.scalars(case)
    names = ", ".join(json.dumps(item["name"]) for item in inputs)
    parameters = ", ".join(f"{item['type']} {item['name']}" for item in inputs)
    arguments = ", ".join(item["name"] for item in inputs)
    # Static: setjmp returns twice, which ASan's tracking of a local's scope does not follow.
    declarations = "".join(f"        static {item['type']} {item['name']};\n" for item in inputs)
    draws = declarations + "".join(draw_statement(case, item, index) for index, item in enumerate(inputs))
    loop = LOOP.replace("NAMES", names).replace("COUNT", str(len(inputs)))
    body = (f"static void dawnr_body({parameters})\n{{\n" + parts.get("setup", "") + parts["harness"] + cases.END + "}\n")
    return (RUNTIME + parts["prelude"] + parts["definitions"] + loop
            + "#define __CPROVER_assume(c) do { if (!(c)) longjmp(dawnr_jump, 1); } while (0)\n"
            + "#define __CPROVER_assert(c, name) do { if (!(c)) dawnr_failure(name); } while (0)\n"
            + body + MAIN.replace("DRAWS", draws).replace("ARGUMENTS", arguments))


def sample(root: Path, variant: str, out: Path, count: int = 1_000_000, seed: int = 1, compiler: str = "gcc", timeout: float = 600) -> dict:
    case = cases.load(root)
    _, scope, parts = cases.build_unit(case, variant, root)
    out.mkdir(parents=True, exist_ok=False)
    unit = sample_unit(case, parts)
    (out / "sample.c").write_text(unit)
    # -O0, as in the replay: at -O1 the compiler removes a call whose result is unused, and the undefined behaviour with it.
    flags = ["-std=gnu11", "-O0", "-g", "-w", "-fsanitize=undefined", "-fsanitize=address", "-fno-sanitize-recover=all", "sample.c", "-o", "sample"]
    report = {"format": FORMAT, "case": case["id"], "variant": variant, "unit_sha256": scope["unit_sha256"], "source_sha256": native.digest(unit), "count": count, "seed": seed,
              "compiler": native.compiler_identity(compiler, out, timeout)}
    build = native.run_process([compiler, *flags], out, timeout)
    (out / "compile.stderr").write_text(build["stderr"])
    if build["state"] != "finished" or build["exit"] != 0:
        report.update(status="not_compiled", reason=build["stderr"][:600])
    else:
        run = native.run_process([str((out / "sample").resolve()), str(count), str(seed)], out, timeout)
        for stream in ("stdout", "stderr"):
            (out / f"sample.{stream}").write_text(run[stream])
        report.update(seconds=run["seconds"], exit=run["exit"])
        final = run["stdout"].splitlines()[-1] if run["stdout"].splitlines() else ""
        counts = json.loads(final) if final.startswith("{") else {}
        report.update(counts)
        report["failed_properties"] = sorted(set(re.findall(r"(?m)^native-sample: assertion failed: (.*)$", run["stdout"])))
        report["first_inputs"] = re.findall(r"(?m)^native-sample: (?:input|died on|stopped on) draw (.*)$", run["stdout"])[:5]
        sanitizer = re.search(r"(?m)^.*(runtime error: .*|ERROR: (?:AddressSanitizer|LeakSanitizer): .*)$", run["stderr"])
        if run["state"] != "finished":
            report.update(status=run["state"])
        elif sanitizer:
            report.update(status="sanitizer_report", report=sanitizer.group(1)[:300])
        elif not counts:
            report.update(status="stopped", reason="the program ended before its last line")
        elif counts["failed_assertions"]:
            report.update(status="failed_assertions")
        elif counts["reached_the_end"] == 0:
            report.update(status="nothing_reached_the_end")
        else:
            report.update(status="no_failure")
    (out / "sample.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("case", type=Path, help="directory holding case.json and its pinned source files")
    parser.add_argument("--variant", choices=("original", "fixed"), default="fixed")
    parser.add_argument("--count", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--compiler", default="gcc")
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--out", type=Path, required=True, help="new artifact directory; existing directories are refused")
    args = parser.parse_args(argv)
    try:
        report = sample(args.case, args.variant, args.out, args.count, args.seed, args.compiler, args.timeout)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "input_error", "reason": str(error)}))
        return 2
    print(json.dumps({key: report.get(key) for key in ("case", "variant", "status", "draws", "reached_the_end", "rejected", "failed_assertions", "failed_properties", "seconds", "report", "reason")}))
    return 0 if report["status"] == "no_failure" else 1


if __name__ == "__main__":
    sys.exit(main())
