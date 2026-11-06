"""Controls for the case-driven native CBMC adapter; optional real-tool runs."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_case as cases
import native_check as native

PILOT = Path(__file__).resolve().parent / "native_fixtures" / "px4-wrap-bin"


def have_sanitizers() -> bool:
    """A compiler can be present without them: MinGW has neither library."""
    if shutil.which("gcc") is None:
        return False
    with tempfile.TemporaryDirectory() as directory:
        (Path(directory) / "probe.c").write_text("int main(void) { return 0; }\n")
        flags = ["-fsanitize=undefined", "-fsanitize=address", "probe.c", "-o", "probe"]
        return native.run_process(["gcc", *flags], Path(directory), 60)["exit"] == 0


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
    (root / "original.c").write_bytes(SOURCE.encode())
    (root / "fixed.c").write_bytes(FIXED.encode())
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
    (root / "original.c").write_bytes(SOURCE.replace("2147483647 - a", "2147483646 - a").encode())
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


@pytest.mark.skipif(not have_sanitizers(), reason="needs a native compiler with sanitizers")
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
    # When every execution needs more than the bound, the end of the harness is out of reach instead.
    always = write_case(tmp_path / "always", sources=sources, harness=harness.replace("a >= 0", "a >= 1"),
                        assertions=["count.result"], assumptions=1, loops=1)
    assert cases.check(always, "fixed", tmp_path / "none", cbmc=CBMC, unwind=1)["verdict"] == "vacuous"
    summary = cases.suite(always, tmp_path / "suite", cbmc=CBMC)
    assert [(row["unwind"], row["verdict"], row["ok"]) for row in summary["rows"]][-1] == (1, "vacuous", True)


def ranges(source, *names):
    """Line ranges of whole functions: first line with the name, up to the next line that is only a brace."""
    lines, found = source.split("\n"), []
    for name in names:
        first = next(i for i, line in enumerate(lines, 1) if re.match(rf"\w[\w \*]*\b{name}\(", line))
        found.append({"name": name, "line": first, "end_line": next(i for i, line in enumerate(lines, 1) if i > first and line == "}")})
    return found


def custom_case(root, original, fixed, names, **fields):
    root.mkdir()
    (root / "original.c").write_bytes(original.encode())
    (root / "fixed.c").write_bytes(fixed.encode())
    case = {"format": cases.FORMAT, "id": root.name, "repository": "example/synthetic", "path": "x.c", "machine": "LP64",
            "sources": {"original": {"file": "original.c", "sha256": native.digest(original), "revision": "synthetic", "definitions": ranges(original, *names)},
                        "fixed": {"file": "fixed.c", "sha256": native.digest(fixed), "revision": "synthetic", "definitions": ranges(fixed, *names)}},
            "inputs": [{"name": "a", "type": "int"}], "harness": "    (void)a;\n", "assertions": [], "assumptions": 0, "loops": 0}
    case.update(fields)
    (root / "case.json").write_text(json.dumps(case))
    return root


ARRAY = {"name": "s", "type": "unsigned char", "array": {"min": 1, "max": 3}}
TEXT = {"name": "t", "type": "char", "string": {"max": 2}}


def test_an_array_input_is_a_heap_object_built_from_scalar_draws(tmp_path):
    root = write_case(tmp_path / "case", inputs=[ARRAY, TEXT, {"name": "a", "type": "int"}], harness="    (void)s; (void)t; (void)a;\n")
    case = cases.load(root)
    assert [item["name"] for item in cases.scalars(case)] == ["s_len", "s_e0", "s_e1", "s_e2", "t_len", "t_e0", "t_e1", "a"]
    unit, scope, parts = cases.build_unit(case, "fixed", root)
    assert "void *malloc(__SIZE_TYPE__);" in unit and "unsigned int nondet_s_len(void);" in unit
    assert "__CPROVER_assume(s_len >= 1 && s_len <= 3);" in unit and "__CPROVER_assume(t_len <= 2);" in unit
    assert "s = (unsigned char *)malloc(s_len * sizeof(unsigned char));" in unit and "t = (char *)malloc((t_len + 1) * sizeof(char));" in unit
    # The first element is below the minimum length and so is always written; the others only when in range.
    assert "\n    s[0] = s_e0;\n    if (s_len > 1) s[1] = s_e1;\n" in unit and "\n    t[t_len] = 0;\n" in unit
    assert "__CPROVER_assume((t_len <= 0 || t_e0 != 0) && (t_len <= 1 || t_e1 != 0));" in unit
    # The end marker, plus: array range and non-null; string range, exact length and non-null.
    assert scope["expected_assumptions"] == 1 + 2 + 3
    native_text = cases.replay_unit(case, parts)
    assert parts["setup"] in native_text and "argc != " + str(1 + 2 * 8) in native_text and "malloc(__SIZE_TYPE__)" not in native_text


def test_a_case_without_array_inputs_keeps_its_unit_free_of_the_allocator(tmp_path):
    root = write_case(tmp_path / "case")
    unit, _, parts = cases.build_unit(cases.load(root), "original", root)
    assert "malloc" not in unit and parts["setup"] == ""


@pytest.mark.parametrize("item", [
    {"name": "s", "type": "char", "array": {"min": 1}}, {"name": "s", "type": "char", "array": {"min": 4, "max": 3}},
    {"name": "s", "type": "char", "array": {"max": 257}}, {"name": "s", "type": "char", "array": {"max": True}},
    {"name": "s", "type": "char", "array": 3}, {"name": "s", "type": "char", "array": {"max": 3, "step": 1}},
    {"name": "s", "type": "char", "array": {"max": 3}, "string": {"max": 3}}, {"name": "s", "type": "char *", "array": {"max": 3}},
])
def test_a_bad_array_shape_is_refused(tmp_path, item):
    with pytest.raises(ValueError):
        cases.load(write_case(tmp_path / "case", inputs=[item], harness="    (void)s;\n"))


@pytest.mark.parametrize("inputs", [[ARRAY, {"name": "s_len", "type": "int"}], [ARRAY, {"name": "s_e1", "type": "int"}], [ARRAY, {"name": "s", "type": "int"}]])
def test_a_generated_name_that_collides_is_refused(tmp_path, inputs):
    with pytest.raises(ValueError):
        cases.load(write_case(tmp_path / "case", inputs=inputs, harness="    (void)s;\n"))


@pytest.mark.parametrize("line", ["    s_len = 0;\n", "    s_e0++;\n", "    s = 0;\n"])
def test_the_harness_may_not_assign_to_a_generated_draw(tmp_path, line):
    with pytest.raises(ValueError, match="assigns to input"):
        cases.load(write_case(tmp_path / "case", inputs=[ARRAY], harness=line))


@pytest.mark.parametrize("line", ["    object.a = 1;\n", "    object->a = 1;\n", "    p->a += 2;\n", "    o.a++;\n", "    ++o.a;\n"])
def test_a_member_named_like_an_input_is_not_the_input(tmp_path, line):
    assert cases.load(write_case(tmp_path / "case", harness=line + HARNESS))


@pytest.mark.parametrize("line", ["    a = 1;\n", "    a += 1;\n", "    a++;\n", "    --a;\n", "    a <<= 2;\n"])
def test_the_input_itself_is_still_refused(tmp_path, line):
    with pytest.raises(ValueError, match="assigns to input"):
        cases.load(write_case(tmp_path / "case", harness=line + HARNESS))


@pytest.mark.parametrize("field, text", [("prelude", '#line 1 "<builtin-library-malloc>"\n__CPROVER_assume(0);\n'), ("prelude", '# 1 "<builtin-library-malloc>"\n'),
                                         ("harness", '  #  line 9 "x.c"\n')])
def test_a_line_directive_cannot_move_an_assumption_out_of_the_count(tmp_path, field, text):
    root = write_case(tmp_path / "case", **{field: text + (HARNESS if field == "harness" else "")})
    with pytest.raises(ValueError, match="line directives"):
        cases.build_unit(cases.load(root), "fixed", root)


def test_unwindset_names_are_checked(tmp_path):
    assert cases.load(write_case(tmp_path / "good", unwindset={"f.0": 3, "depth": 5}))["unwindset"]["depth"] == 5
    for bad in ({"f.0;rm": 3}, {"f.0": 0}, {"f.0": "3"}, ["f.0"]):
        shutil.rmtree(tmp_path / "bad", ignore_errors=True)
        with pytest.raises(ValueError):
            cases.load(write_case(tmp_path / "bad", unwindset=bad))


def test_an_array_witness_reads_as_the_elements_in_range(tmp_path):
    case = cases.load(write_case(tmp_path / "case", inputs=[ARRAY], harness="    (void)s;\n"))
    word = lambda value: {"width": 8, "hex": format(value, "x")}
    witness = {"inputs": {"s_len": {"width": 32, "hex": "2"}, "s_e0": word(0xe2), "s_e1": word(0x80), "s_e2": word(0x41)}}
    assert cases.array_views(case, witness) == {"s": {"length": 2, "elements": ["e2", "80"]}}


RECURSIVE = "int depth(int n)\n{\n\treturn n <= 0 ? 0 : 1 + depth(n - 1);\n}\n"
DEPTH = dict(inputs=[{"name": "n", "type": "int"}], assertions=["depth.value"], assumptions=1, loops=1,
             harness='    __CPROVER_assume(n >= 0 && n <= 3);\n    __CPROVER_assert(depth(n) == n, "depth.value");\n')


@real
def test_a_recursion_bound_on_correct_code_is_incomplete_and_not_a_defect(tmp_path):
    root = custom_case(tmp_path / "case", RECURSIVE, RECURSIVE, ["depth"], **DEPTH)
    short = cases.check(root, "fixed", tmp_path / "short", cbmc=CBMC, unwind=1)
    assert short["verdict"] == "incomplete" and "native_replay" not in short and cases.confirmed(short) == 0
    assert cases.check(root, "fixed", tmp_path / "enough", cbmc=CBMC, unwind=5)["verdict"] == "complete"


@real
def test_a_callee_without_a_body_is_incomplete_through_the_gate(tmp_path):
    source = "int outer(int a)\n{\n\tint helper(int);\n\treturn helper(a);\n}\n"
    root = custom_case(tmp_path / "case", source, source, ["outer"], assertions=["outer.ran"],
                       harness='    int r = outer(a);\n    (void)r;\n    __CPROVER_assert(1 == 1, "outer.ran");\n')
    receipt = cases.check(root, "fixed", tmp_path / "out", cbmc=CBMC)
    assert receipt["verdict"] == "incomplete" and "helper" in receipt["reason"] and "native_replay" not in receipt


DUP = "char *dup_bytes(const char *p, unsigned n)\n{\n\tchar *out = malloc(n);\n\tif (!out) { return 0; }\n\tmemcpy(out, p, n);\n\tout[n] = 0;\n\treturn out;\n}\n"
DUP_CASE = dict(prelude="#include <stdlib.h>\n#include <string.h>\n", inputs=[{"name": "s", "type": "char", "array": {"min": 1, "max": 3}}], assertions=["dup.terminated"],
                harness='    char *copy = dup_bytes(s, s_len);\n    if (copy) {\n        __CPROVER_assert(copy[s_len] == 0, "dup.terminated");\n        free(copy);\n    }\n    free(s);\n')


@real
def test_a_function_that_allocates_gets_a_real_verdict_both_ways(tmp_path):
    root = custom_case(tmp_path / "case", DUP, DUP.replace("malloc(n)", "malloc(n + 1)"), ["dup_bytes"], **DUP_CASE)
    summary = cases.suite(root, tmp_path / "suite", cbmc=CBMC)
    assert summary["ok"] and [row["verdict"] for row in summary["rows"]] == ["counterexample", "complete", "vacuous"]
    receipt = json.loads((tmp_path / "suite" / "original" / "receipt.json").read_text())
    replayed = receipt["native_replay"]["witnesses"]
    assert replayed and {witness["status"] for witness in replayed} == {"memory_error"}
    assert "heap-buffer-overflow" in replayed[0]["detail"]["sanitizer"] and replayed[0]["arrays"]["s"]["length"] >= 1
    assert receipt["library_assumption_goals"] and all(goal["sourceLocation"]["file"].startswith("<builtin-library-") for goal in receipt["library_assumption_goals"])


LEN = "unsigned my_len(const char *s)\n{\n\tunsigned n = 0;\n\twhile (s[n] != 0) { n += 2; }\n\treturn n;\n}\n"
LEN_CASE = dict(inputs=[{"name": "t", "type": "char", "string": {"max": 3}}], assertions=["len.exact"], loops=1, unwind=5,
                harness='    __CPROVER_assert(my_len(t) == t_len, "len.exact");\n')


@real
def test_a_read_past_the_terminator_leaves_the_string_object(tmp_path):
    root = custom_case(tmp_path / "case", LEN, LEN.replace("n += 2", "++n"), ["my_len"], **LEN_CASE)
    summary = cases.suite(root, tmp_path / "suite", cbmc=CBMC)
    assert summary["ok"] and [row["verdict"] for row in summary["rows"]] == ["counterexample", "complete", "vacuous", "incomplete"]
    replayed = json.loads((tmp_path / "suite" / "original" / "receipt.json").read_text())["native_replay"]["witnesses"]
    assert "memory_error" in {witness["status"] for witness in replayed}


LEAK = "int *keep(int a)\n{\n\tint *p = malloc(sizeof *p);\n\tif (p) { *p = a; }\n\treturn p;\n}\n"
LEAK_CASE = dict(prelude="#include <stdlib.h>\n", assertions=["keep.ran"], harness='    int *p = keep(a);\n    (void)p;\n    __CPROVER_assert(1 == 1, "keep.ran");\n')


@real
def test_a_leak_is_a_finding_only_when_the_case_asks_for_it(tmp_path):
    silent = custom_case(tmp_path / "silent", LEAK, LEAK, ["keep"], **LEAK_CASE)
    assert cases.check(silent, "fixed", tmp_path / "silent-out", cbmc=CBMC)["verdict"] == "complete"
    asked = custom_case(tmp_path / "asked", LEAK, LEAK, ["keep"], checks=["--memory-leak-check"], **LEAK_CASE)
    receipt = cases.check(asked, "fixed", tmp_path / "asked-out", cbmc=CBMC)
    assert receipt["verdict"] == "counterexample"
    assert {witness["status"] for witness in receipt["native_replay"]["witnesses"]} == {"memory_error"}
    assert "LeakSanitizer" in receipt["native_replay"]["witnesses"][0]["detail"]["sanitizer"]


BIG = "unsigned long churn(unsigned n, unsigned char b)\n{\n\tunsigned long h = 0;\n\tfor (unsigned i = 0; i < n; ++i) { h = h * 31 + b * b; }\n\treturn h;\n}\n"


@real
def test_a_model_past_the_memory_ceiling_is_a_named_nonresult(tmp_path):
    root = custom_case(tmp_path / "case", BIG, BIG, ["churn"], inputs=[{"name": "n", "type": "unsigned int"}, {"name": "b", "type": "unsigned char"}],
                       assumptions=1, loops=1, assertions=["churn.ran"],
                       harness='    __CPROVER_assume(n <= 400);\n    __CPROVER_assert(churn(n, b) != 0x123456789UL, "churn.ran");\n')
    receipt = cases.check(root, "fixed", tmp_path / "out", cbmc=CBMC, unwind=401, memory_limit_mb=200)
    assert receipt["verdict"] == "out_of_memory" and cases.confirmed(receipt) == 0 and receipt["memory_limit_mb"] == 200


TWO = ("int sum(const unsigned char *p, unsigned n)\n{\n\tint t = 0;\n\tfor (unsigned i = 0; i < n; ++i) { t += p[i]; }\n\treturn t;\n}\n"
       "int count(unsigned n)\n{\n\tunsigned c = 0;\n\twhile (c < n) { ++c; }\n\treturn (int)c;\n}\n")
TWO_CASE = dict(inputs=[{"name": "n", "type": "unsigned int"}, {"name": "m", "type": "unsigned int"}, {"name": "b", "type": "unsigned char"}],
                assertions=["two.sum", "two.count"], assumptions=1, loops=2,
                harness=('    __CPROVER_assume(n <= 3 && m <= 20);\n    unsigned char buf[3] = {b, b, b};\n'
                         '    __CPROVER_assert(sum(buf, n) >= 0, "two.sum");\n    __CPROVER_assert(count(m) == (int)m, "two.count");\n'))


@real
def test_find_bounds_raises_only_the_loop_that_needs_it(tmp_path):
    root = custom_case(tmp_path / "case", TWO, TWO, ["sum", "count"], **TWO_CASE)
    found = cases.find_bounds(root, tmp_path / "bounds", cbmc=CBMC)
    # K counts the checks of the loop condition, one more than the iterations (CBMC manual).
    assert found["found"] and found["unwindset"] == {"count.0": 21, "sum.0": 4} and found["loops"] == 2 and found["other_failures"] == []
    # The proposal has to pass the gate, and a bound one lower must not.
    tuned = custom_case(tmp_path / "tuned", TWO, TWO, ["sum", "count"], **TWO_CASE, unwind=found["unwind"], unwindset=found["unwindset"])
    assert cases.check(tuned, "fixed", tmp_path / "tuned-out", cbmc=CBMC)["verdict"] == "complete"
    lower = custom_case(tmp_path / "lower", TWO, TWO, ["sum", "count"], **TWO_CASE, unwind=2, unwindset={"count.0": 20, "sum.0": 4})
    assert cases.check(lower, "fixed", tmp_path / "lower-out", cbmc=CBMC)["verdict"] == "incomplete"
    # The short-unwind control ignores the per-loop bounds, so the suite still exercises it.
    assert cases.suite(tuned, tmp_path / "suite", cbmc=CBMC)["rows"][-1]["unwind"] == 1


@real
def test_find_bounds_handles_recursion_by_function_name(tmp_path):
    root = custom_case(tmp_path / "case", RECURSIVE, RECURSIVE, ["depth"], **DEPTH)
    found = cases.find_bounds(root, tmp_path / "bounds", cbmc=CBMC)
    assert found["found"] and set(found["unwindset"]) == {"depth"}
    tuned = custom_case(tmp_path / "tuned", RECURSIVE, RECURSIVE, ["depth"], **DEPTH, unwind=found["unwind"], unwindset=found["unwindset"])
    assert cases.check(tuned, "fixed", tmp_path / "tuned-out", cbmc=CBMC)["verdict"] == "complete"


@real
def test_find_bounds_says_so_when_it_cannot_finish(tmp_path):
    root = custom_case(tmp_path / "case", TWO, TWO, ["sum", "count"], **TWO_CASE)
    capped = cases.find_bounds(root, tmp_path / "capped", cbmc=CBMC, ceiling=8)
    assert not capped["found"] and "count.0" in capped["reason"] and "ceiling" in capped["reason"]
    source = "int outer(int a)\n{\n\tint helper(int);\n\treturn helper(a);\n}\n"
    missing = custom_case(tmp_path / "missing", source, source, ["outer"], assertions=["outer.ran"],
                          harness='    (void)outer(a);\n    __CPROVER_assert(1 == 1, "outer.ran");\n')
    result = cases.find_bounds(missing, tmp_path / "missing-out", cbmc=CBMC)
    assert not result["found"] and "helper" in result["reason"]
    absent = cases.find_bounds(missing, tmp_path / "absent-out", cbmc="definitely-absent-cbmc")
    assert not absent["found"] and absent["attempts"] == [] and "absent" in absent["reason"]


STOPPING = {
    "abort": ("#include <stdlib.h>\n", "abort();", {"stopped_early"}),
    "exit": ("#include <stdlib.h>\n", "exit(1);", {"stopped_early"}),
    "exit_zero": ("#include <stdlib.h>\n", "exit(0);", {"stopped_early"}),
    "exit_three": ("#include <stdlib.h>\n", "exit(3);", {"stopped_early"}),
    "_Exit": ("#include <stdlib.h>\n", "_Exit(1);", {"stopped_early"}),
    "_exit": ("#include <unistd.h>\n", "_exit(1);", {"stopped_early"}),
    "quick_exit": ("#include <stdlib.h>\n", "quick_exit(1);", {"stopped_early"}),
    "pthread_exit": ("#include <pthread.h>\n", "pthread_exit(0);", {"stopped_early"}),
    "thrd_exit": ("#include <threads.h>\n", "thrd_exit(1);", {"stopped_early"}),
    "__builtin_unreachable": ("", "__builtin_unreachable();", {"undefined_behavior"}),
    "__builtin_trap": ("", "__builtin_trap();", {"stopped_early"}),
    "__builtin_abort": ("", "__builtin_abort();", {"stopped_early"}),
}
CHECKED = "int checked(int a)\n{\n\tif (a == 0) { %s }\n\treturn 1;\n}\n"
RETURNS = dict(assertions=["checked.returns"], harness='    __CPROVER_assert(checked(a) == 1, "checked.returns");\n', unwind=3)


@real
@pytest.mark.parametrize("name", sorted(STOPPING))
def test_a_function_that_stops_on_some_input_is_not_proved_on_it(tmp_path, name):
    prelude, stop, statuses = STOPPING[name]
    source = CHECKED % stop
    root = custom_case(tmp_path / "case", source, source, ["checked"], prelude=prelude, **RETURNS)
    receipt = cases.check(root, "fixed", tmp_path / "out", cbmc=CBMC)
    assert receipt["verdict"] == "counterexample"
    failing = {row["description"] for row in receipt["properties"] if row["status"] == "FAILURE"}
    assert any(text.startswith("native.stop.") for text in failing)
    replayed = receipt["native_replay"]["witnesses"]
    assert replayed and {witness["status"] for witness in replayed} == statuses
    assert all(witness["inputs"]["a"]["hex"] == "0" for witness in replayed) and cases.confirmed(receipt) == len(replayed)


@real
@pytest.mark.parametrize("stop", ["while (1) ;", "while (a == 0) ;", "here: goto here;", "for (;;) ;", "do ; while (a == 0);"])
def test_a_hang_on_some_input_is_not_proved_on_it(tmp_path, stop):
    source = CHECKED % stop
    root = custom_case(tmp_path / "case", source, source, ["checked"], **RETURNS)
    receipt = cases.check(root, "fixed", tmp_path / "out", cbmc=CBMC)
    assert receipt["verdict"] == "incomplete" and any(".unwind." in row["property"] and row["status"] == "FAILURE" for row in receipt["properties"])
    found = cases.find_bounds(root, tmp_path / "bounds", cbmc=CBMC, ceiling=6)
    assert not found["found"] and "ceiling" in found["reason"]


@real
def test_the_control_that_returns_is_still_complete(tmp_path):
    source = CHECKED % "return 1;"
    root = custom_case(tmp_path / "case", source, source, ["checked"], **RETURNS)
    receipt = cases.check(root, "fixed", tmp_path / "out", cbmc=CBMC)
    assert receipt["verdict"] == "complete" and cases.own_properties(receipt["properties"]) != receipt["properties"]
    assert all(row["status"] == "SUCCESS" for row in receipt["properties"])


@real
def test_a_stop_a_case_allows_acts_as_before_and_the_receipt_says_so(tmp_path):
    source = CHECKED % "exit(1);"
    root = custom_case(tmp_path / "case", source, source, ["checked"], prelude="#include <stdlib.h>\n", allowed_stops=["exit"], **RETURNS)
    receipt = cases.check(root, "fixed", tmp_path / "out", cbmc=CBMC)
    assert receipt["verdict"] == "complete" and receipt["scope"]["allowed_stops"] == ["exit"]
    assert "void exit(" not in (tmp_path / "out" / "stops.c").read_text() and "void abort(" in (tmp_path / "out" / "stops.c").read_text()


def test_only_a_known_stop_can_be_allowed(tmp_path):
    with pytest.raises(ValueError, match="allowed_stops"):
        cases.load(write_case(tmp_path / "case", allowed_stops=["free"]))
    shutil.rmtree(tmp_path / "case")
    with pytest.raises(ValueError, match="allowed_stops"):
        cases.load(write_case(tmp_path / "case", allowed_stops="exit"))


@real
def test_a_project_s_own_definition_wins_over_the_stop(tmp_path):
    source = CHECKED % "abort();"
    root = custom_case(tmp_path / "case", source, source, ["checked"], prelude="void abort(void) { }\n", **RETURNS)
    assert cases.check(root, "fixed", tmp_path / "out", cbmc=CBMC)["verdict"] == "complete"


@real
def test_a_stop_on_every_input_is_vacuous_not_proved(tmp_path):
    source = "int checked(int a)\n{\n\t(void)a;\n\tabort();\n}\n"
    root = custom_case(tmp_path / "case", source, source, ["checked"], prelude="#include <stdlib.h>\n", **RETURNS)
    assert cases.check(root, "fixed", tmp_path / "out", cbmc=CBMC)["verdict"] == "vacuous"


@real
def test_longjmp_is_a_limit_of_the_model(tmp_path):
    source = CHECKED % "longjmp(env, 1);"
    root = custom_case(tmp_path / "case", source, source, ["checked"], prelude="#include <setjmp.h>\nstatic jmp_buf env;\n", **RETURNS)
    receipt = cases.check(root, "fixed", tmp_path / "out", cbmc=CBMC)
    assert receipt["verdict"] == "incomplete" and "native_replay" not in receipt


@real
def test_a_stop_is_not_counted_with_the_properties_of_the_unit(tmp_path):
    root = write_case(tmp_path / "case")
    summary = cases.suite(root, tmp_path / "suite", cbmc=CBMC)
    receipt = json.loads((tmp_path / "suite" / "fixed" / "receipt.json").read_text())
    assert summary["rows"][1]["properties"] == len(cases.own_properties(receipt["properties"])) < len(receipt["properties"])
    unit = (tmp_path / "suite" / "fixed" / "unit.c").read_text()
    assert native.digest(unit) == summary["rows"][1]["unit_sha256"] and "native.stop" not in unit


@pytest.mark.skipif(not have_sanitizers(), reason="needs a native compiler with sanitizers")
def test_a_function_that_exits_with_the_assumption_code_is_not_an_assumption(tmp_path):
    source = CHECKED % "exit(3);"
    root = custom_case(tmp_path / "case", source, source, ["checked"], prelude="#include <stdlib.h>\n", **RETURNS)
    case = cases.load(root)
    _, _, parts = cases.build_unit(case, "fixed", root)
    (tmp_path / "out").mkdir()
    word = {"width": 32, "hex": "0"}
    report = cases.replay(case, parts, [{"property": "p", "inputs": {"a": word}}], tmp_path / "out", "gcc", 60)
    assert report["witnesses"][0]["status"] == "stopped_early" and report["witnesses"][0]["detail"]["exit"] == 3


def test_an_unknown_solver_is_refused_since_cbmc_would_quietly_use_its_default(tmp_path):
    root = write_case(tmp_path / "case")
    with pytest.raises(ValueError, match="solver"):
        cases.check(root, "fixed", tmp_path / "out", cbmc="definitely-absent-cbmc", solver="glucose")
    with pytest.raises(ValueError, match="solver"):
        cases.find_bounds(root, tmp_path / "bounds", cbmc="definitely-absent-cbmc", solver="glucose")
    with pytest.raises(SystemExit):
        cases.main([str(root), "--out", str(tmp_path / "cli"), "--solver", "glucose"])


@real
@pytest.mark.parametrize("solver", cases.SOLVERS)
def test_each_solver_in_the_pinned_build_gives_the_same_verdicts_and_says_which_it_was(tmp_path, solver):
    summary = cases.suite(write_case(tmp_path / "case"), tmp_path / "suite", cbmc=CBMC, solver=solver)
    assert summary["ok"] and summary["solver"] == solver and [row["verdict"] for row in summary["rows"]] == ["counterexample", "complete", "vacuous"]
    receipt = json.loads((tmp_path / "suite" / "fixed" / "receipt.json").read_text())
    assert receipt["solver"] == solver and solver in receipt["stages"]["checking"]["arguments"]
    # CBMC names a solver it does not have, and goes on with its default: this is what the refusal above guards against.
    assert "not available" not in (tmp_path / "suite" / "fixed" / "checking.stdout").read_text()


CADICAL, LRAT_CHECK = os.environ.get("CADICAL", ""), os.environ.get("LRAT_CHECK", "")
certifying = pytest.mark.skipif(not (CBMC and CADICAL and LRAT_CHECK), reason="set CBMC, CADICAL and LRAT_CHECK; see t/build_certify_tools.sh")
posix = pytest.mark.skipif(os.name != "posix", reason="the stand-in tools are shell scripts")


def tool(path, body):
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return str(path)


def fake_tools(tmp_path, solver_exit=20, checker='echo "c VERIFIED"\nexit 0\n', export_exit=0):
    """A checker, solver and model checker that say exactly what a test needs."""
    tmp_path.mkdir(exist_ok=True)
    cbmc = tool(tmp_path / "fake-cbmc", f'while [ "$1" != "--outfile" ]; do shift; done\nprintf "p cnf 2 3\\n1 0\\n" > "$2"\nexit {export_exit}\n')
    solver = tool(tmp_path / "fake-solver", f'[ "$1" = "--version" ] && {{ echo 9.9.9; exit 0; }}\nprintf "3 0 1 2 0\\n" > "$5"\nexit {solver_exit}\n')
    return cbmc, solver, tool(tmp_path / "fake-checker", checker)


@posix
def test_a_certificate_needs_the_exact_line_and_exit_zero(tmp_path):
    verdicts = {'echo "c VERIFIED"\nexit 0\n': "verified",
                'echo "c NOT VERIFIED"\nexit 0\n': "not_verified",         # the word is in the failure message
                'echo "c VERIFIED"\nexit 1\n': "not_verified",
                'exit 0\n': "not_verified",                                # lrat-check has error paths that exit 0
                'echo "c ERROR: comment longer than 1024"\nexit 0\n': "not_verified",
                'echo "note: c VERIFIED"\nexit 0\n': "not_verified",
                'kill -SEGV $$\n': "not_verified"}                         # it crashes on some malformed proofs
    for index, (checker, status) in enumerate(verdicts.items()):
        out = tmp_path / f"out{index}"
        out.mkdir()
        cbmc, solver, proof_checker = fake_tools(tmp_path / f"tools{index}", checker=checker)
        report = cases.certify(cbmc, ["unit.c"], out, solver, proof_checker, 30, 1024)
        assert report["status"] == status, checker


@posix
def test_a_formula_with_a_solution_refutes_the_checking_stage(tmp_path):
    cbmc, solver, checker = fake_tools(tmp_path / "tools", solver_exit=10)
    report = cases.certify(cbmc, ["unit.c"], tmp_path, solver, checker, 30, 1024)
    assert report["status"] == "refuted" and "check" not in report


@posix
@pytest.mark.parametrize("solver_exit", [0, 1, 134])
def test_a_solver_that_does_not_answer_is_no_certificate(tmp_path, solver_exit):
    cbmc, solver, checker = fake_tools(tmp_path / "tools", solver_exit=solver_exit)
    assert cases.certify(cbmc, ["unit.c"], tmp_path, solver, checker, 30, 1024)["status"] == "solver_failed"


@posix
def test_a_formula_that_cannot_be_exported_is_no_certificate(tmp_path):
    cbmc, solver, checker = fake_tools(tmp_path / "tools", export_exit=6)
    assert cases.certify(cbmc, ["unit.c"], tmp_path, solver, checker, 30, 1024)["status"] == "export_failed"


def test_a_missing_tool_is_no_certificate(tmp_path):
    assert cases.certify("cbmc", ["unit.c"], tmp_path, "definitely-absent-solver", "definitely-absent-checker", 30, 1024)["status"] == "absent"


@posix
def test_a_verified_certificate_keeps_its_hashes_and_drops_its_files_unless_asked(tmp_path):
    cbmc, solver, checker = fake_tools(tmp_path / "tools")
    (tmp_path / "gone").mkdir()
    report = cases.certify(cbmc, ["unit.c"], tmp_path / "gone", solver, checker, 30, 1024)
    assert report["status"] == "verified" and len(report["proof_sha256"]) == 64 and (report["variables"], report["clauses"]) == (2, 3)
    assert not (tmp_path / "gone" / "proof.lrat").exists() and not (tmp_path / "gone" / "formula.cnf").exists()
    (tmp_path / "kept").mkdir()
    assert cases.certify(cbmc, ["unit.c"], tmp_path / "kept", solver, checker, 30, 1024, keep_proof=True)["status"] == "verified"
    assert (tmp_path / "kept" / "proof.lrat").exists() and (tmp_path / "kept" / "formula.cnf").exists()
    (tmp_path / "failed").mkdir()
    _, _, refusing = fake_tools(tmp_path / "tools2", checker="exit 1\n")
    assert cases.certify(cbmc, ["unit.c"], tmp_path / "failed", solver, refusing, 30, 1024)["status"] == "not_verified"
    assert (tmp_path / "failed" / "proof.lrat").exists()  # kept to read


def test_the_cli_refuses_half_of_the_certificate_tools(tmp_path):
    with pytest.raises(SystemExit):
        cases.main([str(tmp_path), "--out", str(tmp_path / "out"), "--cadical", "cadical"])


@certifying
def test_a_complete_verdict_gets_a_checked_proof(tmp_path):
    root = write_case(tmp_path / "case")
    summary = cases.suite(root, tmp_path / "suite", cbmc=CBMC, certify_with=(CADICAL, LRAT_CHECK))
    assert summary["ok"] and [row["verdict"] for row in summary["rows"]] == ["counterexample", "complete", "vacuous"]
    assert summary["rows"][1]["certificate"]["status"] == "verified" and "certificate" not in summary["rows"][0]
    receipt = json.loads((tmp_path / "suite" / "fixed" / "receipt.json").read_text())
    assert receipt["certificate"]["tools"]["solver"]["version"] and len(receipt["certificate"]["tools"]["checker"]["binary_sha256"]) == 64


def export_and_solve(tmp_path, root, variant, unwind=None):
    """The formula of a variant, and what the solver says about it, written to a kept directory."""
    out = tmp_path / f"{root.name}-{variant}-{unwind}"
    case = cases.load(root)
    unit, _, _ = cases.build_unit(case, variant, root)
    out.mkdir()
    (out / "unit.c").write_text(unit)
    stops, defines = cases.stops_unit(case.get("allowed_stops", []), unit)
    (out / cases.STOP_FILE).write_text(stops)
    args = ["unit.c", cases.STOP_FILE, *defines, "--function", "harness", cases.MACHINES[case["machine"]][0], "--little-endian", *native.KEEP_SELF_LOOPS,
            "--unwind", str(unwind or case.get("unwind", 4)), *cases.CHECKS, "--unwinding-assertions"]
    return cases.certify(CBMC, args, out, CADICAL, LRAT_CHECK, 120, 4096, keep_proof=True), out


@certifying
def test_the_exported_formula_carries_the_failing_property_and_the_bound(tmp_path):
    assert export_and_solve(tmp_path, write_case(tmp_path / "case"), "original")[0]["status"] == "refuted"
    assert export_and_solve(tmp_path, write_case(tmp_path / "case2"), "fixed")[0]["status"] == "verified"
    root = custom_case(tmp_path / "loop", TWO, TWO, ["sum", "count"], **TWO_CASE)
    assert export_and_solve(tmp_path, root, "fixed", 2)[0]["status"] == "refuted"     # the unwinding assertions are in it
    assert export_and_solve(tmp_path, root, "fixed", 21)[0]["status"] == "verified"
    source = CHECKED % "abort();"
    stopping = custom_case(tmp_path / "stop", source, source, ["checked"], prelude="#include <stdlib.h>\n", **RETURNS)
    assert export_and_solve(tmp_path, stopping, "fixed")[0]["status"] == "refuted"     # so are the stops


@certifying
def test_a_contradiction_has_a_proof_so_a_certificate_cannot_replace_the_coverage_stage(tmp_path):
    """A symbolic contradiction leaves a formula with no solution, and its proof checks. A certificate says nothing
    about whether anything could be reached, so the gate only certifies what has already passed coverage."""
    source = "int same(int a)\n{\n\treturn a;\n}\n"
    fields = dict(assumptions=1, assertions=["same.big"], harness='    __CPROVER_assume(a > 5 && a < 3);\n    __CPROVER_assert(same(a) == 100, "same.big");\n')
    root = custom_case(tmp_path / "case", source, source, ["same"], **fields)
    assert export_and_solve(tmp_path, root, "fixed")[0]["status"] == "verified"
    receipt = cases.check(root, "fixed", tmp_path / "out", cbmc=CBMC, certify_with=(CADICAL, LRAT_CHECK))
    assert receipt["verdict"] == "vacuous" and "certificate" not in receipt


@certifying
def test_when_cbmc_decides_everything_there_is_no_formula_and_no_false_alarm(tmp_path):
    """Every property folds away, so CBMC writes `p cnf 0 0`. That has a solution and must not read as refuted."""
    source = "int same(int a)\n{\n\treturn a;\n}\n"
    root = custom_case(tmp_path / "case", source, source, ["same"], assertions=["same.folded"], harness='    (void)same(a);\n    __CPROVER_assert(1 == 1, "same.folded");\n')
    receipt = cases.check(root, "fixed", tmp_path / "out", cbmc=CBMC, certify_with=(CADICAL, LRAT_CHECK))
    assert receipt["verdict"] == "complete" and receipt["certificate"]["status"] == "no_formula"
    assert (receipt["certificate"]["variables"], receipt["certificate"]["clauses"]) == (0, 0) and "proof_sha256" not in receipt["certificate"]


@certifying
@pytest.mark.parametrize("damage", ["flipped", "hint", "truncated", "empty", "other"])
def test_a_damaged_proof_is_refused_by_the_real_checker(tmp_path, damage):
    report, out = export_and_solve(tmp_path, write_case(tmp_path / "case"), "fixed")
    assert report["status"] == "verified"
    assert cases.check_proof(LRAT_CHECK, "formula.cnf", "proof.lrat", out, 60)["accepted"]
    lines = (out / "proof.lrat").read_text().splitlines()
    additions = [index for index, line in enumerate(lines) if " d " not in line and len(line.split()) > 4]
    middle = additions[len(additions) // 2]
    fields = lines[middle].split()
    if damage == "flipped":
        fields[1] = str(-int(fields[1]))
        lines[middle] = " ".join(fields)
    elif damage == "hint":
        fields[fields.index("0") + 1] = "999999999"
        lines[middle] = " ".join(fields)
    elif damage == "truncated":
        lines = lines[:len(lines) // 2]
    elif damage == "empty":
        lines = []
    elif damage == "other":
        other, other_out = export_and_solve(tmp_path, custom_case(tmp_path / "loop", TWO, TWO, ["sum", "count"], **TWO_CASE), "fixed", 21)
        assert other["status"] == "verified"
        lines = (other_out / "proof.lrat").read_text().splitlines()
    (out / "bad.lrat").write_text("\n".join(lines) + "\n")
    assert not cases.check_proof(LRAT_CHECK, "formula.cnf", "bad.lrat", out, 60)["accepted"]


def test_the_case_gate_describes_itself_in_the_receipt_when_tools_are_absent(tmp_path):
    receipt = cases.check(write_case(tmp_path / "case"), "fixed", tmp_path / "out", cbmc="definitely-absent-cbmc", certify_with=("a", "b"))
    assert receipt["verdict"] == "absent" and "certificate" not in receipt


@pytest.mark.parametrize("models", [["nothing"], ["string", "string"], ["ctype", "ctype_strict"], "string"])
def test_a_bad_list_of_models_is_refused(tmp_path, models):
    with pytest.raises(ValueError, match="models"):
        cases.load(write_case(tmp_path / "case", models=models))


def test_each_model_file_is_present_and_written_without_assumptions_or_intrinsics():
    for name in cases.MODELS:
        text = (cases.MODELS_DIRECTORY / f"{name}.c").read_text()
        assert "__CPROVER" not in text.split("*/", 1)[1], name   # they have to compile natively, to be compared with the C library


def test_the_ctype_tables_are_what_the_generator_writes(tmp_path):
    """Generated files must not drift from their generator. The generator writes beside itself, so run a copy."""
    shutil.copy(cases.MODELS_DIRECTORY / "make_ctype.py", tmp_path / "make_ctype.py")
    done = subprocess.run([sys.executable, str(tmp_path / "make_ctype.py")], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    for name in ("ctype.c", "ctype_strict.c"):
        assert (tmp_path / name).read_bytes() == (cases.MODELS_DIRECTORY / name).read_bytes()


@pytest.mark.skipif(not sys.platform.startswith("linux") or shutil.which("gcc") is None, reason="the comparison is with glibc")
def test_the_models_agree_with_the_c_library_on_a_small_domain(tmp_path):
    """The full domain is in t/PREDICT-2026-11-05-native-models.md. This is the same program with short strings."""
    done = subprocess.run([sys.executable, str(cases.MODELS_DIRECTORY / "cross_check.py"), "--out", str(tmp_path / "out"), "--string-length", "3", "--set-length", "2",
                           "--number-length", "2", "--sanitized-number-length", "1"], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-500:]
    report = json.loads((tmp_path / "out" / "cross-check.json").read_text())
    assert report["runs"]["plain"]["counts"]["different"] == 0 and report["runs"]["plain"]["counts"]["compared"] > 10000
    assert report["runs"]["sanitized"]["counts"]["different"] == 0


PARSE = "long parse(const char *s)\n{\n\tchar *end;\n\tlong v = strtol(s, &end, 2);\n\treturn end == s ? -1 : v;\n}\n"
PARSE_FIELDS = dict(prelude="#include <stdlib.h>\n", inputs=[{"name": "c", "type": "char"}], assertions=["parse.binary"],
                    harness='    (void)c;\n    __CPROVER_assert(parse("12") == 1 && parse("+") == -1, "parse.binary");\n', unwind=6)


@real
def test_the_stdlib_model_gives_the_right_answer_where_the_cbmc_model_does_not(tmp_path):
    """In base 2, "12" is 1 and the number ends at the 2. CBMC 6.11.0's model takes the 2 as a digit and gives 4."""
    alone = custom_case(tmp_path / "alone", PARSE, PARSE, ["parse"], **PARSE_FIELDS)
    wrong = cases.check(alone, "fixed", tmp_path / "alone-out", cbmc=CBMC)
    assert wrong["verdict"] == "counterexample"
    assert {witness["status"] for witness in wrong["native_replay"]["witnesses"]} == {"not_reproduced"}  # the real strtol disagrees with the model
    linked = custom_case(tmp_path / "linked", PARSE, PARSE, ["parse"], models=["stdlib"], **PARSE_FIELDS)
    right = cases.check(linked, "fixed", tmp_path / "linked-out", cbmc=CBMC)
    assert right["verdict"] == "complete" and set(right["models"]) == {"stdlib"}
    assert (tmp_path / "linked-out" / "model_stdlib.c").exists() and "model_stdlib.c" in right["stages"]["coverage"]["arguments"]


DIGIT = "int digit(int c)\n{\n\treturn isdigit(c) != 0;\n}\n"
DIGIT_FIELDS = dict(prelude="#include <ctype.h>\n", inputs=[{"name": "c", "type": "unsigned char"}], assertions=["digit.exact"], unwind=2,
                    harness='    __CPROVER_assert(digit(c) == (c >= 48 && c <= 57), "digit.exact");\n')


@real
def test_the_ctype_macros_of_glibc_run_with_the_model_and_stop_without_it(tmp_path):
    alone = custom_case(tmp_path / "alone", DIGIT, DIGIT, ["digit"], **DIGIT_FIELDS)
    receipt = cases.check(alone, "fixed", tmp_path / "alone-out", cbmc=CBMC)
    assert receipt["verdict"] == "incomplete" and "__ctype_b_loc" in receipt["reason"]
    linked = custom_case(tmp_path / "linked", DIGIT, DIGIT, ["digit"], models=["ctype"], **DIGIT_FIELDS)
    assert cases.check(linked, "fixed", tmp_path / "linked-out", cbmc=CBMC)["verdict"] == "complete"


@real
def test_a_negative_char_is_undefined_by_c_and_only_the_strict_table_says_so(tmp_path):
    """isdigit of a negative char other than EOF is undefined by C11 7.4, and glibc tolerates it."""
    harness = '    __CPROVER_assert(digit((char)c) == (c >= 48 && c <= 57), "digit.exact");\n'
    fields = {**DIGIT_FIELDS, "harness": harness}
    tolerant = custom_case(tmp_path / "tolerant", DIGIT, DIGIT, ["digit"], models=["ctype"], **fields)
    assert cases.check(tolerant, "fixed", tmp_path / "tolerant-out", cbmc=CBMC)["verdict"] == "complete"
    strict = custom_case(tmp_path / "strict", DIGIT, DIGIT, ["digit"], models=["ctype_strict"], **fields)
    receipt = cases.check(strict, "fixed", tmp_path / "strict-out", cbmc=CBMC)
    assert receipt["verdict"] == "counterexample"
    assert {witness["status"] for witness in receipt["native_replay"]["witnesses"]} == {"not_reproduced"}  # by design: glibc tolerates it
    casted = dict(fields, harness='    __CPROVER_assert(digit((unsigned char)(char)c) == (c >= 48 && c <= 57), "digit.exact");\n')
    fixed = custom_case(tmp_path / "fixed", DIGIT, DIGIT, ["digit"], models=["ctype_strict"], **casted)
    assert cases.check(fixed, "fixed", tmp_path / "fixed-out", cbmc=CBMC)["verdict"] == "complete"


COUNT = "unsigned leading(const char *s)\n{\n\treturn (unsigned)strspn(s, \"ab\");\n}\n"


@real
def test_a_string_model_reads_one_byte_at_a_time_so_it_finds_a_missing_terminator(tmp_path):
    fields = dict(prelude="#include <string.h>\n", models=["string"], assertions=["count.bound"], unwind=6)
    sound = custom_case(tmp_path / "sound", COUNT, COUNT, ["leading"], inputs=[{"name": "t", "type": "char", "string": {"max": 3}}],
                        harness='    __CPROVER_assert(leading(t) <= t_len, "count.bound");\n', **fields)
    assert cases.check(sound, "fixed", tmp_path / "sound-out", cbmc=CBMC)["verdict"] == "complete"
    # The same bytes in an array with no terminator: strspn runs off the end of the object.
    broken = custom_case(tmp_path / "broken", COUNT, COUNT, ["leading"], inputs=[{"name": "t", "type": "char", "array": {"min": 1, "max": 3}}],
                         harness='    __CPROVER_assert(leading(t) <= t_len, "count.bound");\n', **fields)
    receipt = cases.check(broken, "fixed", tmp_path / "broken-out", cbmc=CBMC)
    assert receipt["verdict"] == "counterexample"
    assert "memory_error" in {witness["status"] for witness in receipt["native_replay"]["witnesses"]}


@certifying
def test_a_verdict_that_rests_on_a_model_can_still_be_certified(tmp_path):
    linked = custom_case(tmp_path / "linked", PARSE, PARSE, ["parse"], models=["stdlib"], **PARSE_FIELDS)
    receipt = cases.check(linked, "fixed", tmp_path / "out", cbmc=CBMC, certify_with=(CADICAL, LRAT_CHECK))
    assert receipt["verdict"] == "complete" and receipt["certificate"]["status"] in ("verified", "no_formula")


@real
def test_find_bounds_sees_the_loops_inside_a_model(tmp_path):
    fields = dict(prelude="#include <string.h>\n", models=["string"], assertions=["count.bound"], inputs=[{"name": "t", "type": "char", "string": {"max": 3}}],
                  harness='    __CPROVER_assert(leading(t) <= t_len, "count.bound");\n')
    found = cases.find_bounds(custom_case(tmp_path / "case", COUNT, COUNT, ["leading"], **fields), tmp_path / "bounds", cbmc=CBMC)
    assert found["found"] and any(key.startswith(("strspn", "dawnr_in_set")) for key in found["unwindset"])
