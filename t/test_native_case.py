"""Controls for the case-driven native CBMC adapter; optional real-tool runs."""
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_case as cases
import native_check as native

PILOT = Path(__file__).resolve().parent / "native_fixtures" / "px4-wrap-bin"
SOURCE = """/* a brace in a comment: { */
static const char *text = "}{";

int clamp_add(int a, int b)
{
	const char open = '{'; (void)open; // a '}' in a comment
	if (a > 0 && b > 2147483647 - a) { return 2147483647; }
	return a + b;
}

#define TWICE(x) \\
	((x) + \\
	 (x))

struct pair {
	int left;
	int right;
};

int count_to(int n)
{
	int i = 0;
	while (i < n) { ++i; }
	return i;
}
"""
FIXED = SOURCE.replace("\treturn a + b;\n", "\tif (a < 0 && b < -2147483647 - 1 - a) { return -2147483647 - 1; }\n\treturn a + b;\n")
HARNESS = """    long long sum = (long long)a + b;
    long long want = sum > 2147483647LL ? 2147483647LL : sum < -2147483648LL ? -2147483648LL : sum;
    int result = clamp_add(a, b);
    __CPROVER_assert(result == want, "clamp.saturates");
"""


def write_case(root: Path, **changes) -> Path:
    root.mkdir()
    (root / "original.c").write_text(SOURCE)
    (root / "fixed.c").write_text(FIXED)
    case = {"format": cases.FORMAT, "id": "synthetic-clamp-add", "repository": "example/synthetic", "path": "clamp.c", "machine": "LP64",
            "sources": {"original": {"file": "original.c", "sha256": native.digest(SOURCE), "revision": "synthetic",
                                     "definitions": [{"name": "clamp_add", "line": 4, "end_line": 9, "starts_with": "int clamp_add("}]},
                        "fixed": {"file": "fixed.c", "sha256": native.digest(FIXED), "revision": "synthetic",
                                  "definitions": [{"name": "clamp_add", "line": 4, "end_line": 10}]}},
            "inputs": [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
            "harness": HARNESS, "assertions": ["clamp.saturates"], "assumptions": 0, "loops": 0}
    case.update(changes)
    (root / "case.json").write_text(json.dumps(case))
    return root


def test_braces_in_comments_and_literals_do_not_count():
    assert cases.balance(SOURCE.split("\n\n")[0] + "\n")[0] == 0
    depth, low, closed = cases.balance("int f(void) { return '}' + \"{{\"[0]; /* } */ }\n")
    assert (depth, low, len(closed)) == (0, 0, 1)
    with pytest.raises(ValueError, match="unterminated"):
        cases.balance("/* never closed {")


def test_one_whole_item_is_extracted_unchanged():
    lines = SOURCE.split("\n")
    assert cases.extract(SOURCE, {"name": "clamp_add", "line": 4, "end_line": 9}) == "\n".join(lines[3:9]) + "\n"
    assert cases.extract(SOURCE, {"name": "TWICE", "kind": "macro", "line": 11, "end_line": 13}).count("\n") == 3
    assert cases.extract(SOURCE, {"name": "pair", "kind": "declaration", "line": 15, "end_line": 18}).endswith("};\n")
    assert cases.extract(SOURCE, {"name": "clamp_add", "line": 4, "end_line": 10}).endswith("}\n\n")  # a trailing blank line


@pytest.mark.parametrize("entry", [
    {"name": "clamp_add", "line": 4, "end_line": 8},                               # cut before the closing brace
    {"name": "clamp_add", "line": 4, "end_line": 25},                              # runs into the following items
    {"name": "clamp_add", "line": 5, "end_line": 9, "starts_with": "int clamp_add("},  # does not start as declared
    {"name": "count_to", "line": 4, "end_line": 9},                                # names another function
    {"name": "TWICE", "kind": "macro", "line": 11, "end_line": 12},                # continuation cut short
    {"name": "TWICE", "kind": "macro", "line": 12, "end_line": 13},                # not a directive
    {"name": "pair", "kind": "declaration", "line": 15, "end_line": 17},           # cut before the semicolon
    {"name": "clamp_add", "kind": "class", "line": 4, "end_line": 9},              # unknown kind
    {"name": "clamp_add", "line": 0, "end_line": 9},                               # outside the file
    {"name": "clamp_add", "line": 4, "end_line": 9, "body": "int f(void) {}"},     # no replacement text
])
def test_a_range_that_is_not_one_declared_item_is_refused(entry):
    with pytest.raises(ValueError):
        cases.extract(SOURCE, entry)


def test_no_source_byte_can_change_under_the_pinned_identity(tmp_path):
    root = write_case(tmp_path / "case")
    cases.build_unit(cases.load(root), "original", root)
    (root / "original.c").write_text(SOURCE.replace("2147483647 - a", "2147483646 - a"))
    with pytest.raises(ValueError, match="source mismatch"):
        cases.build_unit(cases.load(root), "original", root)


@pytest.mark.parametrize("changes", [
    {"format": "dawnr-native-cbmc-v1"}, {"machine": "ILP64"}, {"checks": ["--no-standard-checks"]}, {"note": "unknown key"},
    {"inputs": []}, {"inputs": [{"name": "a", "type": "int"}, {"name": "a", "type": "int"}]},
    {"inputs": [{"name": "a", "type": "int *"}, {"name": "b", "type": "int"}]},
    {"assumptions": 1}, {"assertions": ["native.machine"]}, {"loops": -1},
    {"harness": HARNESS + "    a = 0;\n"}, {"harness": HARNESS + "    b++;\n"}, {"harness": HARNESS + "    a <<= 1;\n"},
    {"sources": {"fixed": {}}},
])
def test_an_incomplete_or_unsupported_description_is_refused(tmp_path, changes):
    with pytest.raises(ValueError):
        cases.load(write_case(tmp_path / "case", **changes))


def test_comparisons_with_an_input_are_not_assignments(tmp_path):
    harness = "    __CPROVER_assume(a <= b && a >= -5 && a != 3 && b == 7);\n" + HARNESS
    assert cases.load(write_case(tmp_path / "case", harness=harness, assumptions=1))["assumptions"] == 1


def test_the_unit_carries_machine_inputs_harness_and_end_marker(tmp_path):
    root = write_case(tmp_path / "case")
    case = cases.load(root)
    unit, scope, parts = cases.build_unit(case, "original", root)
    assert unit.startswith("int clamp_add(int a, int b)\n{\n") and "static const char *text" not in unit
    assert "int nondet_a(void);\nint nondet_b(void);\nvoid harness(void) {\n" in unit
    assert 'sizeof(long) == 8 && sizeof(void *) == 8, "native.machine");\n    int a = nondet_a();\n    int b = nondet_b();\n' in unit
    assert unit.endswith(HARNESS + cases.END + "}\n")
    assert scope["expected_assertions"] == ["native.machine", "clamp.saturates"] and scope["expected_assumptions"] == 1
    assert scope["source"]["definitions"] == [{"name": "clamp_add", "kind": "function", "lines": [4, 9], "sha256": native.digest(parts["definitions"])}]
    fixed, fixed_scope, _ = cases.build_unit(case, "fixed", root)
    vacuous, vacuous_scope, _ = cases.build_unit(case, "vacuous", root)
    assert "__CPROVER_assume(0 != 0);" in vacuous and "__CPROVER_assume(0 != 0);" not in fixed
    assert vacuous_scope["expected_assumptions"] == 2 and fixed_scope["source"]["sha256"] == native.digest(FIXED)
    assert len({scope["unit_sha256"], fixed_scope["unit_sha256"], vacuous_scope["unit_sha256"]}) == 3


def step(name, bits, function="harness", kind="variable"):
    return {"stepType": "assignment", "assignmentType": kind, "lhs": name, "sourceLocation": {"function": function},
            "value": {"binary": bits, "name": "integer", "width": len(bits)}}


def test_a_witness_is_the_value_the_harness_drew_not_a_callee_copy():
    inputs = [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}]
    trace = [step("a", "0" * 32), step("a", "1" + "0" * 31), step("b", "0" * 32), step("b", "1" * 32),
             step("a", "0" * 31 + "1", function="clamp_add"), step("b", "0" * 32, kind="actual-parameter")]
    result = {"properties": [{"property": "clamp_add.overflow.1", "status": "FAILURE", "trace": trace},
                             {"property": "harness.assertion.2", "status": "FAILURE", "trace": trace},
                             {"property": "harness.assertion.3", "status": "FAILURE", "trace": trace[:2]},
                             {"property": "count_to.unwind.0", "status": "FAILURE", "trace": trace},
                             {"property": "harness.assertion.1", "status": "SUCCESS"}]}
    assert cases.witnesses(result, inputs) == [{"property": "clamp_add.overflow.1",
                                                "inputs": {"a": {"width": 32, "hex": "80000000"}, "b": {"width": 32, "hex": "ffffffff"}}}]


@pytest.mark.skipif(shutil.which("gcc") is None, reason="needs a native compiler with sanitizers")
def test_native_replay_distinguishes_undefined_behavior_from_a_passing_run(tmp_path):
    root = write_case(tmp_path / "case")
    case = cases.load(root)
    _, _, parts = cases.build_unit(case, "original", root)
    word = lambda value: {"width": 32, "hex": format(value & 0xFFFFFFFF, "x")}
    found = [{"property": "p", "inputs": {"a": word(-2**31), "b": word(-1)}}, {"property": "q", "inputs": {"a": word(1), "b": word(1)}},
             {"property": "r", "inputs": {"a": {"width": 64, "hex": "1"}, "b": word(1)}}]
    out = tmp_path / "out"
    out.mkdir()
    report = cases.replay(case, parts, found, out, "gcc", 60)
    assert report["compile"]["exit"] == 0
    assert [witness["status"] for witness in report["witnesses"]] == ["undefined_behavior", "not_reproduced", "unconfirmed"]
    assert "signed integer overflow" in report["witnesses"][0]["detail"]["sanitizer"]
    _, _, fixed = cases.build_unit(case, "fixed", root)
    (tmp_path / "again").mkdir()
    assert cases.replay(case, fixed, found[:1], tmp_path / "again", "gcc", 60)["witnesses"][0]["status"] == "not_reproduced"


def test_missing_tool_writes_an_explicit_nonresult_and_keeps_the_unit(tmp_path):
    receipt = cases.check(write_case(tmp_path / "case"), "original", tmp_path / "out", cbmc="definitely-absent-cbmc")
    assert receipt["verdict"] == "absent" and (tmp_path / "out" / "unit.c").exists() and cases.confirmed(receipt) == 0
    with pytest.raises(OSError):
        cases.check(tmp_path / "case", "original", tmp_path / "out", cbmc="definitely-absent-cbmc")


CBMC = os.environ.get("CBMC", "")
real = pytest.mark.skipif(not CBMC, reason="set CBMC to run the native cases")


@real
def test_the_pilot_verdicts_and_witnesses_through_the_case_adapter(tmp_path):
    summary = cases.suite(PILOT, tmp_path / "suite", cbmc=CBMC)
    assert summary["ok"] and [(row["variant"], row["verdict"]) for row in summary["rows"]] == [
        ("original", "counterexample"), ("fixed", "complete"), ("vacuous", "vacuous")]
    receipt = json.loads((tmp_path / "suite" / "original" / "receipt.json").read_text())
    replayed = receipt["native_replay"]["witnesses"]
    assert replayed and all(witness["inputs"]["bin_count"]["hex"] == "48" for witness in replayed)
    assert {witness["status"] for witness in replayed} == {"undefined_behavior"}
    # A negative remainder is an out-of-range bin, and a sum past INT_MAX is a signed overflow.
    assert any("native.range" in witness["detail"]["assertions"] for witness in replayed)
    assert any("signed integer overflow" in witness["detail"]["sanitizer"] for witness in replayed)
    assert "workingDirectory" not in (tmp_path / "suite" / "original" / "receipt.json").read_text()


@real
def test_a_case_without_assumptions_is_gated_by_the_end_marker(tmp_path):
    summary = cases.suite(write_case(tmp_path / "case"), tmp_path / "suite", cbmc=CBMC)
    assert summary["ok"] and [row["verdict"] for row in summary["rows"]] == ["counterexample", "complete", "vacuous"]
    assert summary["rows"][0]["confirmed_witnesses"] >= 1


@real
def test_a_harness_that_cannot_reach_its_end_is_not_complete(tmp_path):
    harness = "    if (a == a) { return; }\n    __CPROVER_assert(clamp_add(a, b) == 0, \"clamp.saturates\");\n"
    receipt = cases.check(write_case(tmp_path / "case", harness=harness), "fixed", tmp_path / "out", cbmc=CBMC)
    assert receipt["verdict"] == "vacuous"


@real
def test_a_call_without_a_body_is_not_complete(tmp_path):
    harness = "    int helper(int);\n    __CPROVER_assert(clamp_add(a, b) <= 2147483647 && helper(a) == helper(a), \"clamp.saturates\");\n"
    receipt = cases.check(write_case(tmp_path / "case", harness=harness), "fixed", tmp_path / "out", cbmc=CBMC)
    assert receipt["verdict"] != "complete" and cases.confirmed(receipt) == 0


@real
def test_an_insufficient_unwinding_bound_is_incomplete(tmp_path):
    entry = {"name": "count_to", "line": 20, "end_line": 25}
    sources = {label: {"file": label + ".c", "sha256": native.digest(SOURCE if label == "original" else FIXED), "revision": "synthetic",
                       "definitions": [{**entry, "line": entry["line"] + (label == "fixed"), "end_line": entry["end_line"] + (label == "fixed")}]}
               for label in ("original", "fixed")}
    harness = "    __CPROVER_assume(a >= 0 && a <= 3);\n    (void)b;\n    __CPROVER_assert(count_to(a) == a, \"count.result\");\n"
    root = write_case(tmp_path / "case", sources=sources, harness=harness, assertions=["count.result"], assumptions=1, loops=1)
    assert cases.check(root, "fixed", tmp_path / "short", cbmc=CBMC, unwind=1)["verdict"] == "incomplete"
    assert cases.check(root, "fixed", tmp_path / "enough", cbmc=CBMC, unwind=4)["verdict"] == "complete"
