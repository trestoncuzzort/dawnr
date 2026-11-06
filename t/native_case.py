#!/usr/bin/env python3
"""Native CBMC gate over a pinned function described by a case directory.

    python3 t/native_case.py CASE_DIR --variant original --cbmc /path/to/cbmc --out /tmp/run
    python3 t/native_case.py CASE_DIR --suite --cbmc /path/to/cbmc --out /tmp/suite

This generalizes the wrap_bin pilot in native_check.py without changing its gate: the
same inventory, assumption-coverage and checking stages decide the verdict. A case
names full source files by SHA-256, the line ranges extracted from them unchanged, a
prelude, the nondeterministic inputs and a harness body. The adapter adds a machine
assertion and an end marker, so a harness that cannot run to its end is not complete.
A counterexample is replayed by compiling the same unit natively under sanitizers.

Sources: CBMC tutorial and modeling-assumptions manual (diffblue.github.io/cbmc);
arXiv:2302.02384; a task as a program plus a specification under a stated ILP32 or
LP64 architecture follows sv-comp.sosy-lab.org/2025/rules.php. Pinned files and an
expected verdict per control are local precedent: native_check.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_check as native

FORMAT = "dawnr-native-case-v1"
VARIANTS = ("original", "fixed", "vacuous")
MACHINES = {"ILP32": ("--32", "sizeof(int) == 4 && sizeof(long) == 4 && sizeof(void *) == 4"),
            "LP64": ("--64", "sizeof(int) == 4 && sizeof(long) == 8 && sizeof(void *) == 8")}
# Defined conversions are not undefined behavior, so --conversion-check is opt-in here.
CHECKS = [flag for flag in native.CHECKS if flag != "--conversion-check"]
OPTIONAL_CHECKS = ("--conversion-check", "--pointer-overflow-check", "--float-overflow-check", "--nan-check",
                   "--float-div-by-zero-check", "--enum-range-check", "--unsigned-overflow-check")
KINDS = ("function", "macro", "declaration")
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_ ]*\Z")
END = "    __CPROVER_assume(1 == 1);\n"


def balance(text: str) -> tuple[int, int, list[int]]:
    """Final brace depth, its minimum, and where it returned to zero, outside comments and literals."""
    depth = low = index = 0
    closed = []
    while index < len(text):
        two = text[index:index + 2]
        if two == "//":
            index = text.find("\n", index)
            index = len(text) if index < 0 else index
        elif two == "/*":
            close = text.find("*/", index + 2)
            if close < 0:
                raise ValueError("unterminated comment in extracted lines")
            index = close + 2
        elif text[index] in "\"'":
            quote, index = text[index], index + 1
            while index < len(text) and text[index] != quote:
                index += 2 if text[index] == "\\" else 1
            if index >= len(text):
                raise ValueError("unterminated literal in extracted lines")
            index += 1
        else:
            depth += {"{": 1, "}": -1}.get(text[index], 0)
            low = min(low, depth)
            if text[index] == "}" and depth == 0:
                closed.append(index)
            index += 1
    return depth, low, closed


def extract(source: str, entry: dict) -> str:
    """Return lines line..end_line unchanged, refusing a range that is not one whole item."""
    if set(entry) - {"name", "kind", "line", "end_line", "starts_with"} or not NAME.match(str(entry.get("name", ""))):
        raise ValueError("definition needs name, line, end_line and optionally kind and starts_with")
    kind, first, last = entry.get("kind", "function"), entry.get("line"), entry.get("end_line")
    lines = source.split("\n")
    if kind not in KINDS or not all(isinstance(value, int) for value in (first, last)) or not 1 <= first <= last <= len(lines):
        raise ValueError(f"unsupported kind or line range for {entry['name']}")
    chosen = lines[first - 1:last]
    text = "\n".join(chosen) + "\n"
    if "\r" in text or 'R"' in text:
        raise ValueError(f"{entry['name']}: carriage returns and raw string literals are not supported")
    if not chosen[0].startswith(entry.get("starts_with", "")) or entry["name"] not in text:
        raise ValueError(f"{entry['name']}: extracted lines do not start as declared or do not name it")
    if kind == "macro":
        if not chosen[0].lstrip().startswith("#") or any(not line.endswith("\\") for line in chosen[:-1]) or chosen[-1].endswith("\\"):
            raise ValueError(f"{entry['name']}: not exactly one preprocessor definition")
        return text
    depth, low, closed = balance(text)
    # Conditional compilation can hold unmatched braces in its branches; the line range then stands alone.
    conditional = any(re.match(r"\s*#\s*(if|ifdef|ifndef|elif|else)\b", line) for line in chosen)
    if not conditional and (depth != 0 or low < 0):
        raise ValueError(f"{entry['name']}: braces do not balance over the extracted lines")
    tail = text.rstrip()
    if kind == "function" and (not tail.endswith("}") or (not conditional and closed != [len(tail) - 1])):
        raise ValueError(f"{entry['name']}: not exactly one function definition")
    if kind == "declaration" and (not tail.endswith(";") or (not conditional and len(closed) > 1)):
        raise ValueError(f"{entry['name']}: not exactly one declaration")
    return text


def load(root: Path) -> dict:
    case = json.loads((root / "case.json").read_text())
    required = {"format", "id", "repository", "path", "machine", "sources", "inputs", "harness", "assertions", "assumptions", "loops"}
    optional = {"prelude", "unwind", "under_unwind", "checks", "input_domain", "limitations"}
    if not isinstance(case, dict) or case.get("format") != FORMAT or not required <= set(case) or set(case) - required - optional:
        raise ValueError(f"case.json is not a complete {FORMAT} description")
    if case["machine"] not in MACHINES or not set(case.get("checks", [])) <= set(OPTIONAL_CHECKS):
        raise ValueError("unsupported machine model or check option")
    if not case["inputs"] or any(set(item) != {"name", "type"} or not NAME.match(item["name"]) or not TYPE.match(item["type"])
                                 for item in case["inputs"]) or len({item["name"] for item in case["inputs"]}) != len(case["inputs"]):
        raise ValueError("inputs need distinct names and plain scalar type names")
    if "original" not in case["sources"] or set(case["sources"]) - {"original", "fixed"}:
        raise ValueError("sources must hold original and optionally fixed")
    counts = [case["assumptions"], case["loops"], case.get("unwind", 4), case.get("under_unwind", 1)]
    if any(not isinstance(value, int) or value < 0 for value in counts) or "native.machine" in case["assertions"]:
        raise ValueError("assumptions, loops and unwind bounds are non-negative integers; native.machine is reserved")
    if len(re.findall(r"__CPROVER_assume\s*\(", case["harness"])) != case["assumptions"]:
        raise ValueError("the declared assumption count does not match the harness")
    for item in case["inputs"]:
        name = re.escape(item["name"])
        # A witness is read from the value an input was drawn with, so the harness may not change it.
        if re.search(rf"\b{name}\s*(?:[-+*/%&|^]|<<|>>)?=(?!=)|(?:\+\+|--)\s*{name}\b|\b{name}\s*(?:\+\+|--)", case["harness"]):
            raise ValueError(f"the harness assigns to input {item['name']}")
    return case


def definitions(case: dict, label: str, root: Path) -> tuple[list[str], dict]:
    entry = case["sources"][label]
    if set(entry) - {"file", "sha256", "revision", "note", "definitions"} or not {"file", "sha256", "revision", "definitions"} <= set(entry):
        raise ValueError(f"source {label} needs file, sha256, revision and definitions")
    if Path(entry["file"]).name != entry["file"]:
        raise ValueError("source files live beside case.json")
    data = (root / entry["file"]).read_bytes()
    if native.digest(data) != entry["sha256"]:
        raise ValueError(f"source mismatch: {entry['file']} is not the pinned file")
    texts = [extract(data.decode(), item) for item in entry["definitions"]]
    if not texts:
        raise ValueError("no definitions to check")
    listed = [{"name": item["name"], "kind": item.get("kind", "function"), "lines": [item["line"], item["end_line"]],
               "sha256": native.digest(text)} for item, text in zip(entry["definitions"], texts)]
    return texts, {"repository": case["repository"], "path": case["path"], "revision": entry["revision"], "sha256": entry["sha256"],
                   "note": entry.get("note", ""), "definitions": listed,
                   "transformations": ["extract the listed line ranges unchanged", "omit the rest of the file",
                                       "prepend the case prelude", "parse as C"]}


def build_unit(case: dict, variant: str, root: Path) -> tuple[str, dict, dict]:
    if variant not in VARIANTS:
        raise ValueError("unsupported variant")
    label = "original" if variant == "original" or "fixed" not in case["sources"] else "fixed"
    texts, source = definitions(case, label, root)
    prelude, inputs = case.get("prelude", ""), case["inputs"]
    declared = "".join(f"{item['type']} nondet_{item['name']}(void);\n" for item in inputs)
    drawn = "".join(f"    {item['type']} {item['name']} = nondet_{item['name']}();\n" for item in inputs)
    contradiction = "    __CPROVER_assume(0 != 0);\n" if variant == "vacuous" else ""
    parts = {"prelude": prelude, "definitions": "".join(texts), "harness": case["harness"]}
    unit = (prelude + parts["definitions"] + declared + "void harness(void) {\n"
            + f"    __CPROVER_assert({MACHINES[case['machine']][1]}, \"native.machine\");\n" + drawn + contradiction + case["harness"] + END + "}\n")
    scope = {"case": case["id"], "variant": variant, "source": source, "unit_sha256": native.digest(unit),
             "prelude_sha256": native.digest(prelude), "harness_sha256": native.digest(case["harness"]),
             "entry": "harness", "machine_model": f"CBMC {case['machine']} little-endian; 8-bit byte",
             "inputs": case.get("input_domain", "every value of the declared inputs that satisfies the harness assumptions"),
             "input_types": inputs, "expected_assertions": ["native.machine", *case["assertions"]],
             "expected_loops": case["loops"], "expected_assumptions": case["assumptions"] + 1 + (variant == "vacuous"),
             "limitations": case.get("limitations", "extracted definitions and stated harness only; no callers, concurrency, hardware or timing")}
    return unit, scope, parts


def witnesses(result: dict, inputs: list[dict]) -> list[dict]:
    """Distinct input bit patterns of the failing traces, as the model assigned them last."""
    found, seen = [], set()
    for prop in result.get("properties", []):
        if prop.get("status") != "FAILURE" or ".unwind." in prop["property"]:
            continue
        bits = {}
        for step in prop.get("trace", []):
            value = step.get("value", {})
            if (step.get("stepType") == "assignment" and step.get("assignmentType") == "variable"
                    and step.get("sourceLocation", {}).get("function") == "harness"
                    and re.fullmatch(r"[01]{1,64}", str(value.get("binary", "")))):
                bits[step.get("lhs")] = value["binary"]
        if all(item["name"] in bits for item in inputs):
            values = {item["name"]: {"width": len(bits[item["name"]]), "hex": format(int(bits[item["name"]], 2), "x")} for item in inputs}
            key = json.dumps(values, sort_keys=True)
            if key not in seen:
                seen.add(key)
                found.append({"property": prop["property"], "inputs": values})
    return found


def replay_unit(case: dict, parts: dict) -> str:
    """The same prelude, definitions and harness as a native program reading input bit patterns."""
    drawn = ""
    for index, item in enumerate(case["inputs"], 1):
        drawn += (f"    {item['type']} {item['name']};\n    if (!dawnr_input(argv[{index}], argv[{index + len(case['inputs'])}], "
                  f"&{item['name']}, sizeof {item['name']})) return 2;\n")
    return ('''#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
''' + parts["prelude"] + parts["definitions"] + '''static int dawnr_failed;
#define __CPROVER_assume(c) do { if (!(c)) { puts("native-replay: assumption rejected"); exit(3); } } while (0)
#define __CPROVER_assert(c, name) do { if (!(c)) { printf("native-replay: assertion failed: %s\\n", name); dawnr_failed = 1; } } while (0)
static int dawnr_input(const char *width, const char *hex, void *target, size_t size) {
    unsigned long long bits = strtoull(hex, 0, 16);
    if (strtoul(width, 0, 10) != size * CHAR_BIT || size > sizeof bits) return 0;
    memcpy(target, &bits, size); /* little-endian host, as in the model */
    return 1;
}
int main(int argc, char **argv) {
    if (argc != ''' + str(1 + 2 * len(case["inputs"])) + ''') return 2;
    setvbuf(stdout, 0, _IONBF, 0); /* keep assertion lines when a sanitizer aborts afterwards */
''' + drawn + parts["harness"] + END + '''    puts(dawnr_failed ? "native-replay: failed" : "native-replay: passed");
    return dawnr_failed;
}
''')


def replay(case: dict, parts: dict, found: list[dict], out: Path, compiler: str, timeout: float) -> dict:
    unit = replay_unit(case, parts)
    (out / "replay.c").write_text(unit)
    flags = ["-std=gnu11", "-O0", "-fsanitize=undefined", "-fsanitize=address", "-fno-sanitize-recover=all", "replay.c", "-o", "replay"]
    build = native.run_process([compiler, *flags], out, timeout)
    for stream in ("stdout", "stderr"):
        (out / ("replay-compile." + stream)).write_text(build[stream])
    report = {"source_sha256": native.digest(unit), "compiler": native.compiler_identity(compiler, out, timeout),
              "compile": native.process_record(build, flags), "witnesses": []}
    if build["state"] != "finished" or build["exit"] != 0:
        return report
    for index, witness in enumerate(found):
        args = [str(witness["inputs"][item["name"]]["width"]) for item in case["inputs"]]
        args += [witness["inputs"][item["name"]]["hex"] for item in case["inputs"]]
        run = native.run_process([str((out / "replay").resolve()), *args], out, timeout)
        for stream in ("stdout", "stderr"):
            (out / (f"replay-{index}." + stream)).write_text(run[stream])
        failed = re.findall(r"(?m)^native-replay: assertion failed: (.*)$", run["stdout"])
        sanitizer = re.search(r"(?m)^.*(runtime error: .*|ERROR: AddressSanitizer: \S+).*$", run["stderr"])
        status = "unconfirmed"
        detail = {"assertions": failed, "sanitizer": sanitizer.group(0).strip() if sanitizer else None}
        if run["state"] != "finished":
            status = run["state"]
        elif sanitizer:
            status = "undefined_behavior" if "runtime error" in sanitizer.group(1) else "memory_error"
        elif failed:
            status = "assertion_failed"
        elif run["exit"] == 3:
            status = "assumption_rejected"
        elif run["exit"] == 0 and run["stdout"].endswith("native-replay: passed\n"):
            status = "not_reproduced"
        report["witnesses"].append({**witness, "status": status, "detail": detail, "process": native.process_record(run, args)})
    return report


def check(root: Path, variant: str, out: Path, cbmc: str = "cbmc", unwind: int | None = None, timeout: float = 120,
          compiler: str = "gcc") -> dict:
    case = load(root)
    unwind = case.get("unwind", 4) if unwind is None else unwind
    if unwind < 1 or not 0 < timeout <= 3600:
        raise ValueError("positive unwind and timeout <= 3600 required")
    unit, scope, parts = build_unit(case, variant, root)
    out.mkdir(parents=True, exist_ok=False)
    (out / "unit.c").write_text(unit)
    receipt = {"format": FORMAT, "scope": scope, "unwind": unwind, "stages": {},
               "adapter_sha256": native.digest(Path(__file__).read_bytes()),
               "gate_sha256": native.digest(Path(native.__file__).read_bytes()),
               "case_sha256": native.digest((root / "case.json").read_bytes()),
               "preprocessor": native.compiler_identity("gcc", out, timeout)}
    executable = shutil.which(cbmc)
    if executable is None:
        receipt.update(verdict="absent", reason="CBMC executable unavailable")
    else:
        executable = str(Path(executable).resolve())
        version = native.run_process([executable, "--version"], out, timeout)
        receipt["tool"] = {"name": "CBMC", "binary_sha256": native.digest(Path(executable).read_bytes()), "version": version["stdout"].strip()}
        if version["state"] != "finished":
            receipt.update(verdict=version["state"], reason="tool version query did not finish")
        elif version["exit"] != 0 or version["stdout"].strip() != "6.11.0 (cbmc-6.11.0)":
            receipt.update(verdict="unsupported", reason="this parser is pinned to CBMC 6.11.0")
        else:
            checks = [*CHECKS, *case.get("checks", [])]
            common = ["unit.c", "--function", "harness", MACHINES[case["machine"]][0], "--little-endian", "--unwind", str(unwind), "--json-ui"]
            configurations = {"inventory": [*common, *checks, "--unwinding-assertions", "--show-properties"],
                              "coverage": [*common, "--cover", "assume"],
                              "checking": [*common, *checks, "--unwinding-assertions", "--trace"]}
            runs = {}
            for name, args in configurations.items():
                runs[name] = native.run_process([executable, *args], out, timeout)
                for stream in ("stdout", "stderr"):
                    (out / (name + "." + stream)).write_text(runs[name][stream])
                receipt["stages"][name] = native.process_record(runs[name], args)
            receipt.update(native.interpret(runs["inventory"], runs["coverage"], runs["checking"], scope))
            if receipt["verdict"] == "counterexample":
                receipt["native_replay"] = replay(case, parts, witnesses(receipt, case["inputs"]), out, compiler, timeout)
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def confirmed(receipt: dict) -> int:
    return sum(witness["status"] in ("assertion_failed", "undefined_behavior", "memory_error")
               for witness in receipt.get("native_replay", {}).get("witnesses", []))


def suite(root: Path, out: Path, cbmc: str = "cbmc", timeout: float = 120, compiler: str = "gcc") -> dict:
    """The controls every case must pass: the original fails with a replayed witness, the
    fix completes, contradictory assumptions are vacuous, and a short unwind is not complete.
    A short unwind is incomplete when some execution stays within the bound and vacuous
    when none does, because the end of the harness is then out of reach."""
    case = load(root)
    if "fixed" not in case["sources"]:
        raise ValueError("the suite needs a fixed source")
    planned = [("original", None, "counterexample"), ("fixed", None, "complete"), ("vacuous", None, "vacuous")]
    if case["loops"]:
        planned.append(("fixed", case.get("under_unwind", 1), "incomplete or vacuous"))
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for variant, unwind, expected in planned:
        receipt = check(root, variant, out / (variant if unwind is None else f"{variant}-unwind-{unwind}"), cbmc, unwind, timeout, compiler)
        row = {"variant": variant, "unwind": receipt["unwind"], "expected": expected, "verdict": receipt["verdict"],
               "reason": receipt["reason"], "unit_sha256": receipt["scope"]["unit_sha256"],
               "properties": len(receipt.get("properties", [])), "confirmed_witnesses": confirmed(receipt)}
        row["ok"] = row["verdict"] in expected.split(" or ") and (variant != "original" or row["confirmed_witnesses"] > 0)
        rows.append(row)
    summary = {"format": FORMAT + "-suite", "case": case["id"], "rows": rows, "ok": all(row["ok"] for row in rows)}
    (out / "suite.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("case", type=Path, help="directory holding case.json and its pinned source files")
    parser.add_argument("--variant", choices=VARIANTS, default="original")
    parser.add_argument("--suite", action="store_true", help="run every control and compare with the expected verdicts")
    parser.add_argument("--out", type=Path, required=True, help="new artifact directory; existing directories are refused")
    parser.add_argument("--cbmc", default="cbmc")
    parser.add_argument("--compiler", default="gcc")
    parser.add_argument("--unwind", type=int)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)
    try:
        if args.suite:
            summary = suite(args.case, args.out, args.cbmc, args.timeout, args.compiler)
            print(json.dumps(summary))
            return 0 if summary["ok"] else 1
        receipt = check(args.case, args.variant, args.out, args.cbmc, args.unwind, args.timeout, args.compiler)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"verdict": "input_error", "reason": str(error)}))
        return 2
    print(json.dumps({"verdict": receipt["verdict"], "reason": receipt["reason"], "unit_sha256": receipt["scope"]["unit_sha256"],
                      "confirmed_witnesses": confirmed(receipt)}))
    return 0 if receipt["verdict"] == "complete" else 1 if receipt["verdict"] == "counterexample" else 2


if __name__ == "__main__":
    raise SystemExit(main())
