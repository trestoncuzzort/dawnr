#!/usr/bin/env python3
"""Experimental CBMC pilot over the exact pinned PX4 wrap_bin definitions.

    python3 t/native_check.py --case fixed --cbmc /path/to/cbmc --out /tmp/native-fixed

This is separate from the seven t backends. `complete` covers only the identified
machine model, extracted function and harness assumptions. It requires a complete
property inventory, successful unwinding and non-vacuous assumption coverage.
Sources: CBMC tutorial and modeling-assumptions manual; arXiv:2302.02384.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

FIXTURES = Path(__file__).resolve().parent / "native_fixtures" / "px4-wrap-bin"
SOURCE_PATH = "src/lib/collision_prevention/ObstacleMath.cpp"
SOURCES = {
    "original": ("dd804e4b9c490aed051bb36f8d3fca1ee137be2a", "90146c4c5d67ec86a97da974f92e892a0d75ad81c3e33c1d4f849830514e7ba6"),
    "fixed": ("07d30f9341dc02720eac2ed6fb9ee7524f8bd713", "d01b82d5cb76ae8449a3d0411c9a4dadf6c905ef44cce419f7d63cd9090fb8c2"),
}
CASES = ("original", "fixed", "mutant", "vacuous", "loop")
# Without the flag CBMC turns `while (c) ;` into an assumption during symbolic execution: a hang on some
# input vanishes from the model, and no coverage goal can show it (src/goto-symex/symex_goto.cpp at cbmc-6.11.0).
KEEP_SELF_LOOPS = ["--no-self-loops-to-assumptions"]
MODEL = ["--function", "harness", "--32", "--little-endian", *KEEP_SELF_LOOPS]
CHECKS =["--bounds-check", "--pointer-check", "--signed-overflow-check", "--div-by-zero-check",
          "--undefined-shift-check", "--conversion-check", "--retain-trivial-checks"]


def digest(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def extract(label: str, root: Path = FIXTURES) -> tuple[str, dict]:
    revision, expected = SOURCES[label]
    data = (root / (label + ".cpp")).read_bytes()
    if digest(data) != expected:
        raise ValueError(f"source mismatch: {label}.cpp is not the pinned upstream file")
    # These reviewed definitions have no nested braces. Refuse a changed shape;
    # do not try to translate arbitrary C++ or silently omit difficult syntax.
    matches = re.findall(r"(?m)^int wrap_bin\(int bin, int bin_count\)\n\{\n[^{}]*\n\}", data.decode())
    if len(matches) != 1:
        raise ValueError("unsupported wrap_bin definition shape")
    definition = matches[0] + "\n"
    return definition, {"repository": "PX4/PX4-Autopilot", "revision": revision,
                        "path": SOURCE_PATH, "sha256": expected,
                        "definition_sha256": digest(definition), "function": "ObstacleMath::wrap_bin(int,int)",
                        "transformations": ["extract definition unchanged", "omit surrounding namespace and includes", "parse extracted definition as C"]}


def build_case(case: str, root: Path = FIXTURES) -> tuple[str, dict, str]:
    if case not in CASES:
        raise ValueError("unsupported pilot case")
    if case == "loop":
        definition = "int count_to(int n) { int i = 0; while (i < n) { ++i; } return i; }\n"
        body = '''    int n = nondet_int();
    __CPROVER_assume(n >= 0 && n <= 3);
    int result = count_to(n);
    __CPROVER_assert(result == n, "native.loop_result");
'''
        source = {"fixture": "synthetic loop completeness control", "definition_sha256": digest(definition), "function": "count_to(int)"}
        assertions, loops, assumes = ["native.machine", "native.loop_result"], 1, 1
    else:
        label = "original" if case == "original" else "fixed"
        definition, source = extract(label, root)
        if case == "mutant":
            definition, mutation_source = extract("original", root)
            source["mutation"] = {"description": "replace fixed definition with the original expression", "replacement": mutation_source}
        body = '''    int bin = nondet_int();
    int bin_count = nondet_int();
    __CPROVER_assume(bin_count == 72);
'''
        if case == "vacuous":
            body += "    __CPROVER_assume(bin_count != 72);\n"
        body += '''    int result = wrap_bin(bin, bin_count);
    __CPROVER_assert(result >= 0 && result < 72, "native.range");
    unsigned char bins[72] = {0};
    bins[result] = 1;
    __CPROVER_assert(bins[result] == 1, "native.store");
'''
        assertions, loops, assumes = ["native.machine", "native.range", "native.store"], 0, 2 if case == "vacuous" else 1
    unit = definition + '''int nondet_int(void);
void harness(void) {
    __CPROVER_assert(sizeof(int) == 4 && sizeof(unsigned int) == 4, "native.machine");
''' + body + "}\n"
    scope = {"case": case, "source": source, "unit_sha256": digest(unit), "executed_definition_sha256": digest(definition),
             "entry": "harness", "machine_model": "CBMC ILP32 little-endian; 32-bit signed int; 8-bit byte",
             "inputs": "0 <= n <= 3" if case == "loop" else "all int32 bin; bin_count == 72",
             "expected_assertions": assertions, "expected_loops": loops, "expected_assumptions": assumes,
             "limitations": "extracted function and stated harness only; no PX4 callers, concurrency, hardware, timing or flight certification"}
    return unit, scope, definition


MEMORY_LIMIT_ENFORCED = sys.platform == "linux"  # macOS does not enforce RLIMIT_AS, and Windows has no such limit


def address_space_cap(limit_mb: int):
    """A hook run in the child: an allocation past the ceiling fails, and CBMC reports it and exits."""
    def apply() -> None:
        import resource  # Linux only, and this hook only runs there
        _, hard = resource.getrlimit(resource.RLIMIT_AS)
        wanted = limit_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (wanted if hard == resource.RLIM_INFINITY else min(wanted, hard), hard))
    return apply


def run_process(argv: list[str], cwd: Path, timeout: float, memory_limit_mb: int | None = None) -> dict:
    """Keep each invocation bounded; timeout kills its whole process group. A memory limit is for
    the model checker only: AddressSanitizer reserves far more address space than it uses."""
    start = time.monotonic()
    capped = address_space_cap(memory_limit_mb) if memory_limit_mb and MEMORY_LIMIT_ENFORCED else None
    try:
        process = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, preexec_fn=capped)
    except OSError as error:
        return {"state": "absent" if isinstance(error, FileNotFoundError) else "tool_error", "error": type(error).__name__,
                "exit": None, "stdout": "", "stderr": "", "seconds": 0.0}
    state = "finished"
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        state = "timeout"
        try:
            if hasattr(os, "killpg"):
                os.killpg(process.pid, signal.SIGKILL)
            else:  # Windows has no process groups in this sense; the checker has no children there
                process.kill()
        except ProcessLookupError:
            pass
        stdout, stderr = process.communicate()
    return {"state": state, "exit": process.returncode, "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"), "seconds": round(time.monotonic() - start, 4)}


def document(run: dict) -> list[dict]:
    if run["state"] != "finished":
        raise ValueError(run["state"])
    data = json.loads(run["stdout"])
    if not isinstance(data, list) or not data or any(not isinstance(row, dict) for row in data):
        raise ValueError("invalid JSON event list")
    errors = [str(row.get("messageText", "")) for row in data if row.get("messageType") == "ERROR"]
    if errors:
        raise ValueError("CBMC reported a parser or tool error: " + "; ".join(errors)[:400])
    return data


def rows(data: list[dict], key: str) -> list[dict]:
    containers = [row[key] for row in data if key in row]
    if len(containers) != 1 or not isinstance(containers[0], list) or not containers[0]:
        raise ValueError(f"missing or duplicate {key} collection")
    if any(not isinstance(row, dict) for row in containers[0]):
        raise ValueError(f"malformed {key} row")
    return containers[0]


def clean(value):
    """Keep public receipts free of the CBMC working directory/user account."""
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items() if key != "workingDirectory"}
    return value


def bound_property(result: dict) -> bool:
    """A limit of the bound, not a defect. `f.unwind.N` is a loop and `f.recursion` a recursive call:
    src/goto-symex/symex_goto.cpp and symex_function_call.cpp at cbmc-6.11.0."""
    name = str(result.get("property", ""))
    return result.get("sourceLocation", {}).get("propertyClass") == "unwind" or ".unwind." in name or name.endswith(".recursion")


def body_missing(result: dict) -> bool:
    """Not modelled, so nothing past the call means anything: `f.no-body.g`, where f calls g and g has no
    definition, and the longjmp family, whose models refuse with an assertion (src/ansi-c/library/setjmp.c)."""
    return ".no-body." in str(result.get("property", "")) or str(result.get("description", "")).endswith("requires instrumentation")


def out_of_memory(run: dict) -> bool:
    """CBMC catches the failed allocation, reports it and exits 6."""
    return run.get("exit") == 6 and '"Out of memory"' in run.get("stdout", "")


def library_goal(goal: dict) -> bool:
    """An assumption inside one of CBMC's own library models, such as malloc. It is a modelling
    choice of the tool, and it can sit on a branch this harness never takes, so it says nothing
    about the harness; the end marker still has to be reachable through it."""
    return str(goal.get("sourceLocation", {}).get("file", "")).startswith("<builtin-library-")


def interpret(inventory: dict, coverage: dict, checking: dict, scope: dict) -> dict:
    for run in (inventory, coverage, checking):
        if run["state"] != "finished":
            return {"verdict": run["state"], "reason": "a required CBMC stage did not finish"}
        if out_of_memory(run):
            return {"verdict": "out_of_memory", "reason": "a required CBMC stage ran out of its memory limit"}
    try:
        listed, covered, checked = document(inventory), document(coverage), document(checking)
        props, every_goal, results = rows(listed, "properties"), rows(covered, "goals"), rows(checked, "result")
        goals = [goal for goal in every_goal if not library_goal(goal)]
        library = [goal for goal in every_goal if library_goal(goal)]
        expected = [prop["name"] for prop in props]
        actual = [result["property"] for result in results]
        if len(set(expected)) != len(expected) or len(set(actual)) != len(actual) or not set(expected) <= set(actual):
            raise ValueError("property results do not cover the complete inventory")
        if not set(scope["expected_assertions"]) <= {prop.get("description") for prop in props}:
            raise ValueError("required harness assertions are absent")
        if inventory["exit"] != 0 or coverage["exit"] != 0:
            raise ValueError("inventory or coverage process failed")
        total = next(row for row in covered if "goals" in row)
        if len(goals) != 2 * scope["expected_assumptions"] or total.get("totalGoals") != len(every_goal):
            raise ValueError("assumption coverage is incomplete")
        if len({goal.get("goal") for goal in every_goal}) != len(every_goal):
            raise ValueError("duplicate assumption coverage goals")
        paired = {}
        for goal in goals:
            location = goal.get("sourceLocation", {})
            key = (location.get("function"), location.get("line"))
            description = goal.get("description", "")
            side = "before" if description.startswith("assert(false) before assume(") else "after" if description.startswith("assert(false) after assume(") else "unknown"
            paired.setdefault(key, []).append(side)
        if len(paired) != scope["expected_assumptions"] or any(sorted(pair) != ["after", "before"] for pair in paired.values()):
            raise ValueError("assumption coverage lacks complete before/after pairs")
        if any(goal.get("status") not in ("satisfied", "failed") for goal in every_goal):
            raise ValueError("unknown assumption coverage status")
        if total.get("goalsCovered") != sum(goal["status"] == "satisfied" for goal in every_goal):
            raise ValueError("inconsistent assumption coverage totals")
        terminal = [row["cProverStatus"] for row in checked if "cProverStatus" in row]
        statuses = {result.get("status") for result in results}
        if not statuses <= {"SUCCESS", "FAILURE", "UNKNOWN", "NOT_CHECKED"}:
            raise ValueError("unknown property status")
        failed = [result for result in results if result["status"] == "FAILURE"]
        if terminal != (["failure"] if failed else ["success"]) or checking["exit"] != (10 if failed else 0):
            raise ValueError("property outcomes contradict terminal status or process exit")
        detail = {"properties": clean(results), "assumption_goals": clean(goals)}
        if library:
            detail["library_assumption_goals"] = clean(library)
        if any(goal["status"] != "satisfied" for goal in goals):
            return {**detail, "verdict": "vacuous", "reason": "assumption coverage has an unreachable before/after goal"}
        missing = [result for result in failed if body_missing(result)]
        if missing:
            return {**detail, "verdict": "incomplete", "reason": "no body for a callee, so nothing past the call is modelled: "
                    + ", ".join(sorted(result["property"].split(".no-body.")[-1] for result in missing))[:300]}
        unwind = [result for result in results if bound_property(result)]
        ordinary = [result for result in failed if result not in unwind]
        if ordinary:
            if any(not any(step.get("stepType") == "failure" and step.get("property") == result["property"]
                           for step in result.get("trace", [])) for result in ordinary):
                raise ValueError("failed property is missing its counterexample trace")
            return {**detail, "verdict": "counterexample", "reason": "a checked property has a concrete failing trace"}
        if any(result["status"] != "SUCCESS" for result in results):
            return {**detail, "verdict": "incomplete", "reason": "unwinding or another property is unresolved"}
        if len(unwind) < scope["expected_loops"]:
            raise ValueError("a loop is missing its unwinding assertion")
        return {**detail, "verdict": "complete", "reason": "all inventoried properties and required unwinding checks succeeded; assumption goals reachable"}
    except (ValueError, KeyError, TypeError, AttributeError, StopIteration) as error:
        return {"verdict": "tool_error", "reason": str(error)}


def witnesses(result: dict) -> list[dict]:
    found = []
    for prop in result.get("properties", []):
        if prop.get("status") != "FAILURE" or bound_property(prop) or body_missing(prop):
            continue
        values = {}
        for step in prop.get("trace", []):
            if step.get("stepType") == "assignment" and step.get("lhs") in ("bin", "bin_count", "result"):
                raw = step.get("value", {}).get("data", "")
                if re.fullmatch(r"-?\d+", raw):
                    values[step["lhs"]] = int(raw)
        if {"bin", "bin_count"} <= values.keys():
            found.append({"property": prop["property"], **values})
    return found


def process_record(run: dict, args: list[str]) -> dict:
    return {key: run[key] for key in ("state", "exit", "seconds")} | {
        "arguments": args, "stdout_sha256": digest(run["stdout"]), "stderr_sha256": digest(run["stderr"])}


def compiler_identity(compiler: str, out: Path, timeout: float) -> dict:
    executable = shutil.which(compiler)
    identity = {"name": Path(compiler).name}
    if executable is not None:
        identity["binary_sha256"] = digest(Path(executable).read_bytes())
        for flag, key in (("--version", "version"), ("-dumpmachine", "target")):
            response = run_process([executable, flag], out, timeout)
            identity[key] = response["stdout"].strip()
    return identity


def replay(definition: str, found: list[dict], out: Path, compiler: str, timeout: float) -> dict:
    unit = '''#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
_Static_assert(sizeof(int) == 4 && CHAR_BIT == 8, "int32 required");
''' + definition + '''int main(int argc, char **argv) {
    if (argc != 3) return 2;
    long a = strtol(argv[1], 0, 10), b = strtol(argv[2], 0, 10);
    if (a < INT_MIN || a > INT_MAX || b != 72) return 2;
    int result = wrap_bin((int)a, (int)b);
    printf("%d\\n", result);
    return 0;
}
'''
    (out / "replay.c").write_text(unit)
    flags = ["-std=c11", "-O0", "-fsanitize=undefined", "-fno-sanitize-recover=undefined", "replay.c", "-o", "replay"]
    identity = compiler_identity(compiler, out, timeout)
    build = run_process([compiler, *flags], out, timeout)
    for stream in ("stdout", "stderr"):
        (out / ("replay-compile." + stream)).write_text(build[stream])
    report = {"source_sha256": digest(unit), "compiler": identity, "compile": process_record(build, flags), "witnesses": []}
    if build["state"] != "finished" or build["exit"] != 0:
        return report
    for index, witness in enumerate(found):
        args = [str(witness["bin"]), str(witness["bin_count"])]
        run = run_process([str((out / "replay").resolve()), *args], out, timeout)
        for stream in ("stdout", "stderr"):
            (out / (f"replay-{index}." + stream)).write_text(run[stream])
        status = "unconfirmed"
        value = None
        if run["state"] == "finished" and run["exit"] == 0 and re.fullmatch(r"-?\d+\n", run["stdout"]):
            value = int(run["stdout"])
            status = "range_counterexample" if not 0 <= value < 72 else "in_range"
        elif run["state"] == "finished" and run["exit"] != 0 and "runtime error: signed integer overflow" in run["stderr"]:
            status = "undefined_behavior"
        report["witnesses"].append({**witness, "native_result": value, "status": status, "process": process_record(run, args)})
    return report


def check(case: str, out: Path, cbmc: str = "cbmc", unwind: int = 4, timeout: float = 30, compiler: str = "gcc", root: Path = FIXTURES) -> dict:
    if unwind < 1 or not 0 < timeout <= 3600:
        raise ValueError("positive unwind and timeout <= 3600 required")
    unit, scope, definition = build_case(case, root)
    out.mkdir(parents=True, exist_ok=False)
    (out / "unit.c").write_text(unit)
    receipt = {"format": "dawnr-native-cbmc-v1", "scope": scope, "unwind": unwind, "stages": {},
               "adapter_sha256": digest(Path(__file__).read_bytes()),
               "preprocessor": compiler_identity("gcc", out, timeout)}
    executable = shutil.which(cbmc)
    if executable is None:
        receipt.update(verdict="absent", reason="CBMC executable unavailable")
    else:
        executable = str(Path(executable).resolve())
        version = run_process([executable, "--version"], out, timeout)
        receipt["tool"] = {"name": "CBMC", "binary_sha256": digest(Path(executable).read_bytes()), "version": version["stdout"].strip()}
        if version["state"] != "finished":
            receipt.update(verdict=version["state"], reason="tool version query did not finish")
        elif version["exit"] != 0 or version["stdout"].strip() != "6.11.0 (cbmc-6.11.0)":
            receipt.update(verdict="unsupported", reason="this pilot parser is pinned to CBMC 6.11.0")
        else:
            common = ["unit.c", *MODEL, "--unwind", str(unwind), "--json-ui"]
            configurations = {"inventory": [*common, *CHECKS, "--unwinding-assertions", "--show-properties"],
                              "coverage": [*common, "--cover", "assume"],
                              "checking": [*common, *CHECKS, "--unwinding-assertions", "--trace"]}
            runs = {}
            for name, args in configurations.items():
                runs[name] = run_process([executable, *args], out, timeout)
                for stream in ("stdout", "stderr"):
                    (out / (name + "." + stream)).write_text(runs[name][stream])
                receipt["stages"][name] = process_record(runs[name], args)
            receipt.update(interpret(runs["inventory"], runs["coverage"], runs["checking"], scope))
            if receipt["verdict"] == "counterexample" and case != "loop":
                receipt["native_replay"] = replay(definition, witnesses(receipt), out, compiler, timeout)
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, default="fixed")
    parser.add_argument("--out", type=Path, required=True, help="new artifact directory; existing directories are refused")
    parser.add_argument("--cbmc", default="cbmc")
    parser.add_argument("--compiler", default="gcc")
    parser.add_argument("--unwind", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args(argv)
    try:
        receipt = check(args.case, args.out, args.cbmc, args.unwind, args.timeout, args.compiler)
    except (OSError, ValueError) as error:
        print(json.dumps({"verdict": "input_error", "reason": str(error)}))
        return 2
    print(json.dumps({"verdict": receipt["verdict"], "reason": receipt["reason"], "unit_sha256": receipt["scope"]["unit_sha256"]}))
    return 0 if receipt["verdict"] == "complete" else 1 if receipt["verdict"] == "counterexample" else 2


if __name__ == "__main__":
    raise SystemExit(main())
