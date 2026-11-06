#!/usr/bin/env python3
"""Native CBMC gate over a pinned function described by a case directory.

    python3 t/native_case.py CASE_DIR --variant original --cbmc /path/to/cbmc --out /tmp/run
    python3 t/native_case.py CASE_DIR --suite --cbmc /path/to/cbmc --out /tmp/suite
    python3 t/native_case.py CASE_DIR --find-bounds --cbmc /path/to/cbmc --out /tmp/bounds

This generalizes the wrap_bin pilot in native_check.py without changing its gate: the
same inventory, assumption-coverage and checking stages decide the verdict. A case
names full source files by SHA-256, the line ranges extracted from them unchanged, a
prelude, the nondeterministic inputs and a harness body. The adapter adds a machine
assertion and an end marker, so a harness that cannot run to its end is not complete.
A counterexample is replayed by compiling the same unit natively under sanitizers.

An input is a scalar, or an `array` or a `string` of a bounded length. An array or a string
is a heap object of exactly the drawn size, built from one scalar draw per element, so
that a read past its end leaves the object, under the model and under AddressSanitizer.

Sources: CBMC tutorial and modeling-assumptions manual (diffblue.github.io/cbmc);
arXiv:2302.02384; a task as a program plus a specification under a stated ILP32 or
LP64 architecture follows sv-comp.sosy-lab.org/2025/rules.php. Pinned files and an
expected verdict per control are local precedent: native_check.py. The syntax and the
counting rule of --unwindset: diffblue.github.io/cbmc/cprover-manual/md_cbmc-unwinding.html.
__asan_default_options: github.com/google/sanitizers/wiki/AddressSanitizerFlags.
"""
from __future__ import annotations

import argparse
import hashlib
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
                   "--float-div-by-zero-check", "--enum-range-check", "--unsigned-overflow-check",
                   "--malloc-may-fail", "--malloc-fail-null", "--memory-leak-check", "--pointer-primitive-check", "--memory-cleanup-check")
KINDS = ("function", "macro", "declaration")
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_ ]*\Z")
LOOP = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\.[0-9]+)?\Z")
END = "    __CPROVER_assume(1 == 1);\n"
MAX_ELEMENTS = 256
DEFAULT_MEMORY_MB = 4096
MAX_ATTEMPTS = 200
# CBMC ends these executions with no property: src/ansi-c/library/stdlib.c, pthread_lib.c and threads.c hold
# __CPROVER_assume(0), and goto-conversion/builtin_functions.cpp ignores __builtin_unreachable. Each is made a
# failing property here, so that a function that stops on some input cannot read as proved on it.
# ExitThread is Windows only and is left out.
STOP_FUNCTIONS = {"abort": "void", "exit": "int status", "_Exit": "int status", "_exit": "int status", "quick_exit": "int status",
                  "pthread_exit": "void *value", "thrd_exit": "int status"}
STOP_BUILTINS = ("__builtin_unreachable", "__builtin_trap", "__builtin_abort")
STOPS = (*STOP_FUNCTIONS, *STOP_BUILTINS)
STOP_FILE = "stops.c"
# The two solvers in the pinned release build. CBMC answers any other name with a message and uses its default,
# so a name is checked here. CaDiCaL: github.com/arminbiere/cadical; MiniSat is CBMC's default.
SOLVERS = ("minisat2", "cadical")
DEFAULT_SOLVER = "minisat2"


# Tested C library models a case can link: see native_models/ and t/PREDICT-2026-11-05-native-models.md.
MODELS = ("string", "stdlib", "ctype", "ctype_strict")
MODELS_DIRECTORY = Path(__file__).resolve().parent / "native_models"


def link_models(case: dict, out: Path) -> tuple[list[str], dict]:
    """Copy the models a case asks for beside the unit, and return their file names and identities."""
    names, identities = [], {}
    for name in case.get("models", []):
        data = (MODELS_DIRECTORY / f"{name}.c").read_bytes()
        target = f"model_{name}.c"
        (out / target).write_bytes(data)
        names.append(target)
        identities[name] = native.digest(data)
    return names, identities


def stops_unit(allowed: list[str], unit: str) -> tuple[str, list[str]]:
    """The second file of the inventory and checking stages, and the defines that reach the builtins.

    Each stop fails its property and then ends the execution, so nothing after it gives a false alarm. The
    checked unit is not touched and keeps its hash. A stop the unit defines itself is left out: a weak
    definition is no help, since CBMC given two source files keeps the weak one (goto-cc does not)."""
    text = "/* Written by native_case.py: an execution that stops here must not read as proved. */\n"
    for name, parameters in STOP_FUNCTIONS.items():
        if name not in allowed and not re.search(rf"\b{name}\s*\([^;{{}}]*\)\s*\{{", unit):
            text += f'void {name}({parameters})\n{{\n    __CPROVER_assert(0, "native.stop.{name}");\n    __CPROVER_assume(0);\n}}\n'
    defines = []
    for name in STOP_BUILTINS:
        if name not in allowed:
            text += f'void dawnr_stop{name}(void)\n{{\n    __CPROVER_assert(0, "native.stop.{name}");\n    __CPROVER_assume(0);\n}}\n'
            defines += ["-D", f"{name}()=dawnr_stop{name}()"]
    return text, defines


def own_properties(results: list[dict]) -> list[dict]:
    """The results that belong to the checked unit: what a published count of properties counts."""
    return [row for row in results if row.get("sourceLocation", {}).get("file") != STOP_FILE]


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


def shape_of(item: dict) -> dict | None:
    return item.get("array", item.get("string"))


def scalars(case: dict) -> list[dict]:
    """Every input as the scalars actually drawn: an array or string is a length and one draw per element."""
    drawn = []
    for item in case["inputs"]:
        shape = shape_of(item)
        if shape is None:
            drawn.append({"name": item["name"], "type": item["type"]})
        else:
            drawn.append({"name": item["name"] + "_len", "type": "unsigned int"})
            drawn += [{"name": f"{item['name']}_e{index}", "type": item["type"]} for index in range(shape["max"])]
    return drawn


def setup(case: dict) -> tuple[str, int]:
    """The heap objects of the array and string inputs, and how many assumptions that adds."""
    text, count = "", 0
    for item in case["inputs"]:
        shape = shape_of(item)
        if shape is None:
            continue
        name, kind, low, high = item["name"], item["type"], shape.get("min", 0), shape["max"]
        bound = f"{name}_len <= {high}" if low == 0 else f"{name}_len >= {low} && {name}_len <= {high}"
        text += f"    __CPROVER_assume({bound});\n"
        count += 1
        terminated = "string" in item
        if terminated and high:
            # strlen(s) == s_len: a string with a NUL inside it is the same as a shorter string.
            clauses = " && ".join(f"({name}_len <= {index} || {name}_e{index} != 0)" for index in range(high))
            text += f"    __CPROVER_assume({clauses});\n"
            count += 1
        size = f"({name}_len + 1)" if terminated else f"{name}_len"
        text += f"    {kind} *{name} = ({kind} *)malloc({size} * sizeof({kind}));\n    __CPROVER_assume({name} != 0);\n"
        count += 1
        for index in range(high):
            guard = "" if index < low else f"if ({name}_len > {index}) "
            text += f"    {guard}{name}[{index}] = {name}_e{index};\n"
        if terminated:
            text += f"    {name}[{name}_len] = 0;\n"
    return text, count


def check_input(item: dict) -> None:
    shapes = {"array", "string"} & set(item)
    if (set(item) - {"name", "type", "array", "string"} or not {"name", "type"} <= set(item) or len(shapes) > 1
            or not NAME.match(str(item["name"])) or not TYPE.match(str(item["type"]))):
        raise ValueError("inputs need distinct names and plain scalar type names, and at most one of array and string")
    for key in shapes:
        shape = item[key]
        low, high = shape.get("min", 0) if isinstance(shape, dict) else None, shape.get("max") if isinstance(shape, dict) else None
        if (not isinstance(shape, dict) or set(shape) - {"min", "max"} or not all(isinstance(value, int) and not isinstance(value, bool) for value in (low, high))
                or not 0 <= low <= high <= MAX_ELEMENTS):
            raise ValueError(f"{item['name']}: {key} needs max, and optionally min, with 0 <= min <= max <= {MAX_ELEMENTS}")


def assigned_to(name: str, harness: str) -> bool:
    """A witness is read from the value an input was drawn with, so the harness may not change it.
    A member of the same name is another object: `object.size = 1` does not assign to an input `size`."""
    plain = rf"(?<![\w.])(?<!->){re.escape(name)}"
    return bool(re.search(rf"{plain}\s*(?:[-+*/%&|^]|<<|>>)?=(?!=)|(?:\+\+|--)\s*{plain}\b|{plain}\s*(?:\+\+|--)", harness))


def load(root: Path) -> dict:
    case = json.loads((root / "case.json").read_text(encoding="utf-8"))
    required = {"format", "id", "repository", "path", "machine", "sources", "inputs", "harness", "assertions", "assumptions", "loops"}
    optional = {"prelude", "unwind", "unwindset", "under_unwind", "checks", "input_domain", "limitations", "allowed_stops", "models"}
    if not isinstance(case, dict) or case.get("format") != FORMAT or not required <= set(case) or set(case) - required - optional:
        raise ValueError(f"case.json is not a complete {FORMAT} description")
    if case["machine"] not in MACHINES or not set(case.get("checks", [])) <= set(OPTIONAL_CHECKS):
        raise ValueError("unsupported machine model or check option")
    if not case["inputs"]:
        raise ValueError("inputs need distinct names and plain scalar type names")
    for item in case["inputs"]:
        check_input(item)
    names = [item["name"] for item in scalars(case)] + [item["name"] for item in case["inputs"] if shape_of(item) is not None]
    if len(set(names)) != len(names):
        raise ValueError("inputs need distinct names and plain scalar type names")
    if "original" not in case["sources"] or set(case["sources"]) - {"original", "fixed"}:
        raise ValueError("sources must hold original and optionally fixed")
    counts = [case["assumptions"], case["loops"], case.get("unwind", 4), case.get("under_unwind", 1)]
    if any(not isinstance(value, int) or value < 0 for value in counts) or "native.machine" in case["assertions"]:
        raise ValueError("assumptions, loops and unwind bounds are non-negative integers; native.machine is reserved")
    if not isinstance(case.get("allowed_stops", []), list) or not set(case.get("allowed_stops", [])) <= set(STOPS):
        raise ValueError(f"allowed_stops may name only: {', '.join(STOPS)}")
    models = case.get("models", [])
    if not isinstance(models, list) or not set(models) <= set(MODELS) or len(set(models)) != len(models) or {"ctype", "ctype_strict"} <= set(models):
        raise ValueError(f"models may name each of {', '.join(MODELS)} once, and only one of ctype and ctype_strict")
    bounds = case.get("unwindset", {})
    if not isinstance(bounds, dict) or any(not LOOP.match(str(key)) or not isinstance(value, int) or value < 1 for key, value in bounds.items()):
        raise ValueError("unwindset maps a loop such as f.0, or a recursive function f, to a positive bound")
    if len(re.findall(r"__CPROVER_assume\s*\(", case["harness"])) != case["assumptions"]:
        raise ValueError("the declared assumption count does not match the harness")
    for name in names:
        if assigned_to(name, case["harness"]):
            raise ValueError(f"the harness assigns to input {name}")
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
    prelude, inputs = case.get("prelude", ""), scalars(case)
    declared = "".join(f"{item['type']} nondet_{item['name']}(void);\n" for item in inputs)
    drawn = "".join(f"    {item['type']} {item['name']} = nondet_{item['name']}();\n" for item in inputs)
    contradiction = "    __CPROVER_assume(0 != 0);\n" if variant == "vacuous" else ""
    generated, generated_assumptions = setup(case)
    allocator = "void *malloc(__SIZE_TYPE__);\n" if generated else ""
    parts = {"prelude": prelude, "definitions": "".join(texts), "harness": case["harness"], "setup": generated}
    unit = (prelude + parts["definitions"] + allocator + declared + "void harness(void) {\n"
            + f"    __CPROVER_assert({MACHINES[case['machine']][1]}, \"native.machine\");\n" + drawn + contradiction + generated + case["harness"] + END + "}\n")
    # A line directive could give an assumption a library file name and hide it from the coverage count.
    if re.search(r"(?m)^[ \t]*#[ \t]*(?:line\b|[0-9])", unit):
        raise ValueError("line directives are not supported in a checked unit")
    scope = {"case": case["id"], "variant": variant, "source": source, "unit_sha256": native.digest(unit),
             "prelude_sha256": native.digest(prelude), "harness_sha256": native.digest(case["harness"]),
             "entry": "harness", "machine_model": f"CBMC {case['machine']} little-endian; 8-bit byte",
             "inputs": case.get("input_domain", "every value of the declared inputs that satisfies the harness assumptions"),
             "allowed_stops": case.get("allowed_stops", []),
             "input_types": case["inputs"], "expected_assertions": ["native.machine", *case["assertions"]],
             "expected_loops": case["loops"], "expected_assumptions": case["assumptions"] + generated_assumptions + 1 + (variant == "vacuous"),
             "limitations": case.get("limitations", "extracted definitions and stated harness only; no callers, concurrency, hardware or timing")}
    return unit, scope, parts


def witnesses(result: dict, inputs: list[dict]) -> list[dict]:
    """Distinct input bit patterns of the failing traces, as the model assigned them last."""
    found, seen = [], set()
    for prop in result.get("properties", []):
        if prop.get("status") != "FAILURE" or native.bound_property(prop) or native.body_missing(prop):
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


def array_views(case: dict, witness: dict) -> dict:
    """The array and string inputs of a witness, as a reader wants them: only the elements in range."""
    views = {}
    for item in case["inputs"]:
        if shape_of(item) is not None:
            length = int(witness["inputs"][item["name"] + "_len"]["hex"], 16)
            views[item["name"]] = {"length": length, "elements": [witness["inputs"][f"{item['name']}_e{index}"]["hex"] for index in range(min(length, shape_of(item)["max"]))]}
    return views


# ASan gives malloc(0) one readable byte, so a read from an empty input would pass natively where the model fails it. Poisoning that
# byte makes an empty input empty. In the harness's own text only: the code under check keeps the real malloc.
# github.com/google/sanitizers/wiki/AddressSanitizerManualPoisoning
EXACT_MALLOC = '''extern void __asan_poison_memory_region(void const volatile *, size_t);
static void *dawnr_exact_malloc(size_t size) {
    void *block = (malloc)(size);
    if (block != 0 && size == 0) __asan_poison_memory_region(block, 1);
    return block;
}
#define malloc(size) dawnr_exact_malloc(size)
'''


def replay_unit(case: dict, parts: dict) -> str:
    """The same prelude, definitions and harness as a native program reading input bit patterns."""
    inputs, drawn = scalars(case), ""
    for index, item in enumerate(inputs, 1):
        drawn += (f"    {item['type']} {item['name']};\n    if (!dawnr_input(argv[{index}], argv[{index + len(inputs)}], "
                  f"&{item['name']}, sizeof {item['name']})) return 2;\n")
    # A leak is a finding only when the case asks the model to look for one.
    leaks = "" if "--memory-leak-check" in case.get("checks", []) else 'const char *__asan_default_options(void) { return "detect_leaks=0"; }\n'
    # The prelude first, as in the checked unit: a feature macro it defines has to come before any system header.
    return (leaks + parts["prelude"] + parts["definitions"] + '''#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
''' + (EXACT_MALLOC if parts.get("setup") else "") + '''static int dawnr_failed;
#define __CPROVER_assume(c) do { if (!(c)) { puts("native-replay: assumption rejected"); exit(3); } } while (0)
#define __CPROVER_assert(c, name) do { if (!(c)) { printf("native-replay: assertion failed: %s\\n", name); dawnr_failed = 1; } } while (0)
static int dawnr_input(const char *width, const char *hex, void *target, size_t size) {
    unsigned long long bits = strtoull(hex, 0, 16);
    if (strtoul(width, 0, 10) != size * CHAR_BIT || size > sizeof bits) return 0;
    memcpy(target, &bits, size); /* little-endian host, as in the model */
    return 1;
}
int main(int argc, char **argv) {
    if (argc != ''' + str(1 + 2 * len(inputs)) + ''') return 2;
    setvbuf(stdout, 0, _IONBF, 0); /* keep assertion lines when a sanitizer aborts afterwards */
''' + drawn + '''    puts("native-replay: started");
''' + parts.get("setup", "") + parts["harness"] + END + '''    puts(dawnr_failed ? "native-replay: failed" : "native-replay: passed");
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
    inputs = scalars(case)
    for index, witness in enumerate(found):
        args = [str(witness["inputs"][item["name"]]["width"]) for item in inputs]
        args += [witness["inputs"][item["name"]]["hex"] for item in inputs]
        run = native.run_process([str((out / "replay").resolve()), *args], out, timeout)
        for stream in ("stdout", "stderr"):
            (out / (f"replay-{index}." + stream)).write_text(run[stream])
        failed = re.findall(r"(?m)^native-replay: assertion failed: (.*)$", run["stdout"])
        sanitizer = re.search(r"(?m)^.*(runtime error: .*|ERROR: (?:AddressSanitizer|LeakSanitizer): \S+).*$", run["stderr"])
        status = "unconfirmed"
        detail = {"assertions": failed, "sanitizer": sanitizer.group(0).strip() if sanitizer else None, "access": native.memory_access(run["stderr"])}
        if run["state"] != "finished":
            status = run["state"]
        elif sanitizer:
            status = "undefined_behavior" if "runtime error" in sanitizer.group(1) else "memory_error"
        elif failed:
            status = "assertion_failed"
        elif "native-replay: assumption rejected" in run["stdout"]:
            status = "assumption_rejected"
        elif run["exit"] == 0 and run["stdout"].endswith("native-replay: passed\n"):
            status = "not_reproduced"
        elif "native-replay: started" in run["stdout"]:
            status = "stopped_early"  # it ran, and ended before its last line: exit, abort, a trap
            detail["exit"] = run["exit"]
        views = array_views(case, witness)
        report["witnesses"].append({**witness, **({"arrays": views} if views else {}), "status": status, "detail": detail, "process": native.process_record(run, args)})
    return report


def tool_identity(cbmc: str, out: Path, timeout: float) -> tuple[str | None, dict, str | None, str | None]:
    """The checker's path and identity, or the verdict and reason that stop the run."""
    executable = shutil.which(cbmc)
    if executable is None:
        return None, {}, "absent", "CBMC executable unavailable"
    executable = str(Path(executable).resolve())
    version = native.run_process([executable, "--version"], out, timeout)
    tool = {"name": "CBMC", "binary_sha256": native.digest(Path(executable).read_bytes()), "version": version["stdout"].strip()}
    if version["state"] != "finished":
        return executable, tool, version["state"], "tool version query did not finish"
    if version["exit"] != 0 or version["stdout"].strip() != "6.11.0 (cbmc-6.11.0)":
        return executable, tool, "unsupported", "this parser is pinned to CBMC 6.11.0"
    return executable, tool, None, None


def render_bounds(bounds: dict) -> str:
    return ",".join(f"{key}:{bounds[key]}" for key in sorted(bounds))


def file_digest(path: Path) -> str:
    """SHA-256 of a file that may be too large to hold in memory, such as a proof."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_proof(checker: str, formula: str, proof: str, cwd: Path, timeout: float, memory_limit_mb: int | None = None) -> dict:
    """Whether the proof checker accepts: its exact line and exit 0, and nothing else. On failure lrat-check prints
    `c NOT VERIFIED`, so a search for the word would accept a failure, and some of its error paths exit 0, so the
    exit status alone is not enough. A crash on a malformed proof is a refusal."""
    run = native.run_process([checker, formula, proof], cwd, timeout, memory_limit_mb)
    accepted = run["state"] == "finished" and run["exit"] == 0 and re.search(r"(?m)^c VERIFIED$", run["stdout"]) is not None
    return {"accepted": accepted, "state": run["state"], "exit": run["exit"], "seconds": run["seconds"], "stdout": run["stdout"], "stderr": run["stderr"]}


def certify(executable: str, args: list[str], out: Path, cadical: str, checker: str, timeout: float, memory_limit_mb: int, keep_proof: bool = False) -> dict:
    """Check a `complete` verdict without trusting a SAT solver: export the formula, have a solver write an LRAT proof
    that it has no solution, and have a separate program check that proof.

    The solver answers 20 for no solution and 10 for a solution. A solution means CBMC said every property holds and
    the same formula says one does not, which is `refuted`. `verified` is the checked proof, and `no_formula` means CBMC
    decided every property itself, so no solver is involved. This does not check CBMC's translation of C to the formula,
    and it does not touch the coverage stage. Tools: github.com/arminbiere/cadical, github.com/marijnheule/drat-trim.
    """
    report = {"status": "absent", "formula": "formula.cnf", "proof": "proof.lrat"}
    solver, proof_checker = shutil.which(cadical), shutil.which(checker)
    if solver is None or proof_checker is None:
        return {**report, "reason": "the proof-producing solver or the proof checker is unavailable"}
    solver, proof_checker = str(Path(solver).resolve()), str(Path(proof_checker).resolve())
    version = native.run_process([solver, "--version"], out, timeout)
    report["tools"] = {"solver": {"name": "CaDiCaL", "version": version["stdout"].strip(), "binary_sha256": native.digest(Path(solver).read_bytes())},
                       "checker": {"name": "lrat-check", "binary_sha256": native.digest(Path(proof_checker).read_bytes())}}
    formula, proof = out / "formula.cnf", out / "proof.lrat"
    export = native.run_process([executable, *args, "--dimacs", "--outfile", formula.name], out, timeout, memory_limit_mb)
    report["export"] = native.process_record(export, args)
    if export["state"] != "finished" or export["exit"] != 0 or not formula.exists():
        return {**report, "status": export["state"] if export["state"] != "finished" else "export_failed"}
    with formula.open() as stream:
        header = next((line for line in stream if line.startswith("p cnf ")), "").split()
    report.update(formula_sha256=file_digest(formula), formula_bytes=formula.stat().st_size,
                  variables=int(header[2]) if len(header) == 4 else None, clauses=int(header[3]) if len(header) == 4 else None)
    # When CBMC's own simplification decides every property it writes `p cnf 0 0`. That formula has a solution, and it
    # means nothing: no solver was asked anything, so there is no answer to trust and no proof to check.
    if (report["variables"], report["clauses"]) == (0, 0):
        report["seconds"] = export["seconds"]
        return {**report, "status": "no_formula"}
    arguments = ["--lrat", "--no-binary", "-q", formula.name, proof.name]
    solved = native.run_process([solver, *arguments], out, timeout, memory_limit_mb)
    report["solve"] = native.process_record(solved, arguments)
    if solved["state"] != "finished":
        return {**report, "status": solved["state"]}
    if solved["exit"] == 10:
        return {**report, "status": "refuted"}
    if solved["exit"] != 20 or not proof.exists():
        return {**report, "status": "solver_failed"}
    report.update(proof_sha256=file_digest(proof), proof_bytes=proof.stat().st_size)
    result = check_proof(proof_checker, formula.name, proof.name, out, timeout, memory_limit_mb)
    report["check"] = {key: result[key] for key in ("state", "exit", "seconds")} | {"stdout_sha256": native.digest(result["stdout"])}
    report["seconds"] = round(export["seconds"] + solved["seconds"] + result["seconds"], 2)
    report["status"] = "verified" if result["accepted"] else "timeout" if result["state"] == "timeout" else "not_verified"
    # A proof can run to gigabytes. Its hash stays in the receipt, and a failure keeps the files to read.
    if report["status"] == "verified" and not keep_proof:
        formula.unlink()
        proof.unlink()
    return report


def check(root: Path, variant: str, out: Path, cbmc: str = "cbmc", unwind: int | None = None, timeout: float = 120,
          compiler: str = "gcc", memory_limit_mb: int = DEFAULT_MEMORY_MB, solver: str = DEFAULT_SOLVER,
          certify_with: tuple[str, str] | None = None, keep_proof: bool = False) -> dict:
    """One variant through the gate. With certify_with (a solver and a proof checker), `complete` also needs a checked proof."""
    case = load(root)
    # An explicit bound is a control, so it applies to every loop and the case's per-loop bounds stay out of it.
    bounds = case.get("unwindset", {}) if unwind is None else {}
    unwind = case.get("unwind", 4) if unwind is None else unwind
    if unwind < 1 or not 0 < timeout <= 3600 or memory_limit_mb < 1:
        raise ValueError("positive unwind and memory limit, and timeout <= 3600, required")
    if solver not in SOLVERS:
        raise ValueError(f"solver must be one of {', '.join(SOLVERS)}")
    unit, scope, parts = build_unit(case, variant, root)
    out.mkdir(parents=True, exist_ok=False)
    (out / "unit.c").write_text(unit)
    receipt = {"format": FORMAT, "scope": scope, "unwind": unwind, "stages": {}, "memory_limit_mb": memory_limit_mb, "solver": solver,
               "memory_limit_enforced": native.MEMORY_LIMIT_ENFORCED, **({"unwindset": bounds} if bounds else {}),
               "adapter_sha256": native.digest(Path(__file__).read_bytes()),
               "gate_sha256": native.digest(Path(native.__file__).read_bytes()),
               "case_sha256": native.digest((root / "case.json").read_bytes()),
               "preprocessor": native.compiler_identity("gcc", out, timeout)}
    executable, tool, verdict, reason = tool_identity(cbmc, out, timeout)
    if tool:
        receipt["tool"] = tool
    if verdict is not None:
        receipt.update(verdict=verdict, reason=reason)
    else:
        checks = [*CHECKS, *case.get("checks", [])]
        stops, defines = stops_unit(case.get("allowed_stops", []), unit)
        (out / STOP_FILE).write_text(stops)
        receipt["stops_sha256"] = native.digest(stops)
        linked, identities = link_models(case, out)
        if identities:
            receipt["models"] = identities
        model = ["--function", "harness", MACHINES[case["machine"]][0], "--little-endian", *native.KEEP_SELF_LOOPS, "--unwind", str(unwind),
                 *(["--unwindset", render_bounds(bounds)] if bounds else [])]
        common = [*model[:5], "--sat-solver", solver, *model[5:], "--json-ui"]
        # Coverage reads the unit without the stops: its goals have to be the harness's own and the end marker reachable.
        with_stops = ["unit.c", *linked, STOP_FILE, *defines, *common]
        configurations = {"inventory": [*with_stops, *checks, "--unwinding-assertions", "--show-properties"],
                          "coverage": ["unit.c", *linked, *common, "--cover", "assume"],
                          "checking": [*with_stops, *checks, "--unwinding-assertions", "--trace"]}
        runs = {}
        for name, args in configurations.items():
            runs[name] = native.run_process([executable, *args], out, timeout, memory_limit_mb)
            for stream in ("stdout", "stderr"):
                (out / (name + "." + stream)).write_text(runs[name][stream])
            receipt["stages"][name] = native.process_record(runs[name], args)
        receipt.update(native.interpret(runs["inventory"], runs["coverage"], runs["checking"], scope))
        if receipt["verdict"] == "counterexample":
            receipt["native_replay"] = replay(case, parts, witnesses(receipt, scalars(case)), out, compiler, timeout)
        if certify_with and receipt["verdict"] == "complete":
            formula_args = ["unit.c", *linked, STOP_FILE, *defines, *model, *checks, "--unwinding-assertions"]
            receipt["certificate"] = certify(executable, formula_args, out, *certify_with, timeout, memory_limit_mb, keep_proof)
            if receipt["certificate"]["status"] not in ("verified", "no_formula"):
                # The checking stage's own word stays in the properties; the verdict says it could not be checked.
                receipt.update(verdict="uncertified", reason=f"the proof of the checking stage's result: {receipt['certificate']['status']}")
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def confirmed(receipt: dict) -> int:
    return sum(witness["status"] in ("assertion_failed", "undefined_behavior", "memory_error", "stopped_early")
               for witness in receipt.get("native_replay", {}).get("witnesses", []))


def peak_rss_mb() -> int | None:
    """The largest child of this process so far, in MB; there is no such figure off POSIX."""
    try:
        import resource
    except ImportError:
        return None
    return resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss // 1024


def suite(root: Path, out: Path, cbmc: str = "cbmc", timeout: float = 120, compiler: str = "gcc", memory_limit_mb: int = DEFAULT_MEMORY_MB,
          solver: str = DEFAULT_SOLVER, certify_with: tuple[str, str] | None = None) -> dict:
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
        receipt = check(root, variant, out / (variant if unwind is None else f"{variant}-unwind-{unwind}"), cbmc, unwind, timeout, compiler, memory_limit_mb, solver, certify_with)
        row = {"variant": variant, "unwind": receipt["unwind"], "expected": expected, "verdict": receipt["verdict"],
               "reason": receipt["reason"], "unit_sha256": receipt["scope"]["unit_sha256"],
               "properties": len(own_properties(receipt.get("properties", []))), "confirmed_witnesses": confirmed(receipt),
               "seconds": round(sum(stage["seconds"] for stage in receipt["stages"].values()), 2)}
        if "certificate" in receipt:
            certificate = receipt["certificate"]
            row["certificate"] = {key: certificate.get(key) for key in ("status", "seconds", "formula_bytes", "proof_bytes", "variables", "clauses", "formula_sha256", "proof_sha256")}
            row["certificate"]["solve_seconds"] = certificate.get("solve", {}).get("seconds")
            row["certificate"]["check_seconds"] = certificate.get("check", {}).get("seconds")
            row["certificate"]["checking_stage_seconds"] = receipt["stages"].get("checking", {}).get("seconds")
        row["ok"] = row["verdict"] in expected.split(" or ") and (variant != "original" or row["confirmed_witnesses"] > 0)
        rows.append(row)
    summary = {"format": FORMAT + "-suite", "case": case["id"], "rows": rows, "ok": all(row["ok"] for row in rows),
               "memory_limit_mb": memory_limit_mb, "solver": solver, "peak_rss_mb": peak_rss_mb()}
    (out / "suite.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def loop_key(prop: str) -> str:
    """The --unwindset name of an unwinding property: f.unwind.2 is f.2 and f.recursion is f."""
    return prop[:-len(".recursion")] if prop.endswith(".recursion") else prop.replace(".unwind.", ".")


def find_bounds(root: Path, out: Path, cbmc: str = "cbmc", timeout: float = 120, memory_limit_mb: int = DEFAULT_MEMORY_MB,
                ceiling: int = 64, variant: str | None = None, solver: str = DEFAULT_SOLVER) -> dict:
    """The smallest per-loop bounds under which no unwinding property fails.

    One global --unwind multiplies the model by the longest loop. This starts every loop at 2,
    raises only the loops whose own property fails, then narrows each raised bound. It never
    weakens a result: the bounds are only a proposal, and the gate still has to pass with them.

    INVENTED: the search itself. The CBMC manual, the CBMC training FAQ and the Kani notes set
    these bounds by hand. The solver runs each time from nothing, so this costs one model
    check per attempt; a found bound depends on the other loops' bounds in the same way a
    hand-chosen one does.
    """
    case = load(root)
    variant = variant or ("fixed" if "fixed" in case["sources"] else "original")
    unit, scope, _ = build_unit(case, variant, root)
    if ceiling < 2 or memory_limit_mb < 1 or not 0 < timeout <= 3600 or solver not in SOLVERS:
        raise ValueError("a ceiling of at least 2, a positive memory limit, timeout <= 3600 and a known solver are required")
    out.mkdir(parents=True, exist_ok=False)
    (out / "unit.c").write_text(unit)
    stops, defines = stops_unit(case.get("allowed_stops", []), unit)
    (out / STOP_FILE).write_text(stops)
    linked, _ = link_models(case, out)
    summary = {"format": FORMAT + "-bounds", "case": case["id"], "variant": variant, "unit_sha256": scope["unit_sha256"], "ceiling": ceiling,
               "memory_limit_mb": memory_limit_mb, "solver": solver, "found": False, "attempts": []}
    executable, tool, verdict, reason = tool_identity(cbmc, out, timeout)
    if tool:
        summary["tool"] = tool
    if verdict is not None:
        summary.update(reason=f"{verdict}: {reason}")
        return summary
    base = ["unit.c", *linked, STOP_FILE, *defines, "--function", "harness", MACHINES[case["machine"]][0], "--little-endian", *native.KEEP_SELF_LOOPS, "--sat-solver", solver, "--unwind", "2",
            "--json-ui", "--verbosity", "8", *CHECKS, *case.get("checks", []), "--unwinding-assertions"]

    def attempt(bounds: dict) -> dict:
        args = [*base, *(["--unwindset", render_bounds(bounds)] if bounds else [])]
        run = native.run_process([executable, *args], out, timeout, memory_limit_mb)
        record = {"unwindset": dict(bounds), "state": run["state"], "exit": run["exit"], "seconds": run["seconds"]}
        summary["attempts"].append(record)
        if len(summary["attempts"]) > MAX_ATTEMPTS:
            record["stop"] = "too many attempts"
        elif run["state"] != "finished":
            record["stop"] = run["state"]
        elif native.out_of_memory(run):
            record["stop"] = "out_of_memory"
        elif run["exit"] not in (0, 10):
            record["stop"] = f"exit {run['exit']}"
        if "stop" in record:
            return record
        try:
            results = native.rows(native.document(run), "result")
        except ValueError as error:
            record["stop"] = str(error)[:300]
            return record
        sizes = re.findall(r"(\d+) variables, (\d+) clauses", run["stdout"])
        record.update(variables=max((int(pair[0]) for pair in sizes), default=None), clauses=max((int(pair[1]) for pair in sizes), default=None),
                      properties=len(results), bound_properties=sum(native.bound_property(row) for row in results),
                      short=sorted(row["property"] for row in results if native.bound_property(row) and row["status"] == "FAILURE"),
                      open=sorted(row["property"] for row in results if native.bound_property(row) and row["status"] not in ("SUCCESS", "FAILURE")),
                      missing_body=sorted(row["property"] for row in results if native.body_missing(row) and row["status"] == "FAILURE"),
                      failed=sorted(row["property"] for row in results if row["status"] == "FAILURE" and not native.bound_property(row) and not native.body_missing(row))[:20])
        return record

    bounds, too_short = {}, {}
    while True:
        record = attempt(bounds)
        if "stop" in record:
            summary.update(reason=f"stopped: {record['stop']}", unwindset=bounds)
            return summary
        if record["missing_body"]:
            summary.update(reason="a callee has no body: " + ", ".join(record["missing_body"])[:300], unwindset=bounds)
            return summary
        if not record["short"]:
            break
        for prop in record["short"]:
            key = loop_key(prop)
            current = bounds.get(key, 2)
            too_short[key] = current
            raised = current + max(1, current // 2)
            if raised > ceiling:
                summary.update(reason=f"{key} needs more than the ceiling of {ceiling}", unwindset=bounds)
                return summary
            bounds[key] = raised
    for key in sorted(bounds):
        low, high = too_short[key], bounds[key]
        while high - low > 1:
            middle = (low + high) // 2
            record = attempt({**bounds, key: middle})
            if "stop" in record:
                break
            if key in {loop_key(prop) for prop in record["short"]} or record["open"]:
                low = middle
            else:
                high = middle
        bounds[key] = high
    final = attempt(bounds)
    if "stop" in final or final.get("short") or final.get("open"):
        reason = final.get("stop") or "the narrowed bounds leave an unwinding property undecided: " + ", ".join(final.get("short", []) + final.get("open", []))[:300]
        summary.update(reason=reason, unwindset=bounds)
        return summary
    summary.update(found=True, reason="no unwinding property fails under these bounds", unwind=2, unwindset=bounds, loops=final["bound_properties"],
                   properties=final["properties"], variables=final["variables"], clauses=final["clauses"], other_failures=final["failed"])
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("case", type=Path, help="directory holding case.json and its pinned source files")
    parser.add_argument("--variant", choices=VARIANTS, default=None)
    parser.add_argument("--suite", action="store_true", help="run every control and compare with the expected verdicts")
    parser.add_argument("--find-bounds", action="store_true", help="propose per-loop unwinding bounds for this case")
    parser.add_argument("--max-bound", type=int, default=64, help="largest bound --find-bounds will try for one loop")
    parser.add_argument("--out", type=Path, required=True, help="new artifact directory; existing directories are refused")
    parser.add_argument("--cbmc", default="cbmc")
    parser.add_argument("--compiler", default="gcc")
    parser.add_argument("--unwind", type=int)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--memory-limit-mb", type=int, default=DEFAULT_MEMORY_MB, help="address space ceiling for the model checker")
    parser.add_argument("--solver", choices=SOLVERS, default=DEFAULT_SOLVER, help="SAT solver in the pinned CBMC build")
    parser.add_argument("--cadical", help="with --lrat-check: certify a complete verdict with a checked proof (t/build_certify_tools.sh)")
    parser.add_argument("--lrat-check", dest="lrat_check", help="the proof checker for --cadical")
    parser.add_argument("--keep-proof", action="store_true", help="keep the formula and the proof of a verified certificate")
    args = parser.parse_args(argv)
    if bool(args.cadical) != bool(args.lrat_check):
        parser.error("--cadical and --lrat-check go together")
    certify_with = (args.cadical, args.lrat_check) if args.cadical else None
    try:
        if args.find_bounds:
            summary = find_bounds(args.case, args.out, args.cbmc, args.timeout, args.memory_limit_mb, args.max_bound, args.variant, args.solver)
            (args.out / "bounds.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
            print(json.dumps({key: value for key, value in summary.items() if key != "attempts"} | {"attempts": len(summary["attempts"])}))
            return 0 if summary["found"] else 1
        if args.suite:
            summary = suite(args.case, args.out, args.cbmc, args.timeout, args.compiler, args.memory_limit_mb, args.solver, certify_with)
            print(json.dumps(summary))
            return 0 if summary["ok"] else 1
        receipt = check(args.case, args.variant or "original", args.out, args.cbmc, args.unwind, args.timeout, args.compiler, args.memory_limit_mb, args.solver,
                        certify_with, args.keep_proof)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"verdict": "input_error", "reason": str(error)}))
        return 2
    print(json.dumps({"verdict": receipt["verdict"], "reason": receipt["reason"], "unit_sha256": receipt["scope"]["unit_sha256"],
                      "confirmed_witnesses": confirmed(receipt), **({"certificate": receipt["certificate"]["status"]} if "certificate" in receipt else {})}))
    return 0 if receipt["verdict"] == "complete" else 1 if receipt["verdict"] == "counterexample" else 2


if __name__ == "__main__":
    raise SystemExit(main())
