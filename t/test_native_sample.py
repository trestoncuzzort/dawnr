"""Controls for the native sampler: it has to find what is there, and say so when it finds nothing to run."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_case as cases
import native_check as native
import native_sample as sampler


def have_sanitizers() -> bool:
    if shutil.which("gcc") is None or os.name != "posix":
        return False
    with tempfile.TemporaryDirectory() as directory:
        (Path(directory) / "probe.c").write_text("int main(void) { return 0; }\n")
        return native.run_process(["gcc", "-fsanitize=undefined", "-fsanitize=address", "probe.c", "-o", "probe"], Path(directory), 60)["exit"] == 0


needs_compiler = pytest.mark.skipif(not have_sanitizers(), reason="needs a native compiler with sanitizers")
CBMC = os.environ.get("CBMC", "")


def make_case(root, source, **fields):
    root.mkdir()
    (root / "original.c").write_bytes(source.encode())
    (root / "fixed.c").write_bytes(source.encode())
    end = source.count("\n")
    entry = {"sha256": native.digest(source), "revision": "synthetic", "definitions": [{"name": fields.pop("function"), "line": 1, "end_line": end}]}
    case = {"format": cases.FORMAT, "id": root.name, "repository": "example/synthetic", "path": "x.c", "machine": "LP64",
            "sources": {"original": {**entry, "file": "original.c"}, "fixed": {**entry, "file": "fixed.c"}},
            "inputs": [{"name": "a", "type": "int"}], "harness": "    (void)a;\n", "assertions": [], "assumptions": 0, "loops": 0}
    case.update(fields)
    (root / "case.json").write_text(json.dumps(case))
    return root


SUM = "int add(int a, int b)\n{\n\treturn a + b;\n}\n"
BOTH = [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}]


@needs_compiler
def test_a_true_property_finds_nothing_and_counts_what_it_ran(tmp_path):
    source = "int same(int a)\n{\n\treturn a;\n}\n"
    root = make_case(tmp_path / "case", source, function="same", assertions=["same.value"], harness='    __CPROVER_assert(same(a) == a, "same.value");\n')
    report = sampler.sample(root, "fixed", tmp_path / "out", count=2000)
    assert report["status"] == "no_failure" and report["draws"] == 2000 and report["reached_the_end"] == 2000 and report["failed_assertions"] == 0


@needs_compiler
def test_a_failed_assertion_is_counted_and_its_input_kept(tmp_path):
    source = "int off(int a)\n{\n\treturn a == 100 ? 0 : a;\n}\n"
    root = make_case(tmp_path / "case", source, function="off", assertions=["off.value"], harness='    __CPROVER_assert(off(a) == a, "off.value");\n')
    report = sampler.sample(root, "fixed", tmp_path / "out", count=20000)
    assert report["status"] == "failed_assertions" and report["failed_assertions"] > 0 and report["failed_properties"] == ["off.value"]
    assert report["first_inputs"] and "a=64" in report["first_inputs"][0]   # 100 is 0x64, one of the edges


@needs_compiler
def test_undefined_behavior_is_a_sanitizer_report_naming_the_input(tmp_path):
    root = make_case(tmp_path / "case", SUM, function="add", inputs=BOTH, assertions=["add.ran"], harness='    (void)add(a, b);\n    __CPROVER_assert(1 == 1, "add.ran");\n')
    report = sampler.sample(root, "fixed", tmp_path / "out", count=20000)
    assert report["status"] == "sanitizer_report" and "signed integer overflow" in report["report"] and "draws" not in report
    assert report["first_inputs"] and "a=" in report["first_inputs"][0]


@needs_compiler
def test_a_read_past_the_end_of_a_heap_input_is_a_sanitizer_report(tmp_path):
    source = "int last(const char *s, unsigned n)\n{\n\treturn s[n];\n}\n"
    root = make_case(tmp_path / "case", source, function="last", inputs=[{"name": "s", "type": "char", "array": {"min": 1, "max": 4}}], assertions=["last.ran"],
                     harness='    (void)last(s, s_len);\n    __CPROVER_assert(1 == 1, "last.ran");\n')
    report = sampler.sample(root, "fixed", tmp_path / "out", count=100)
    assert report["status"] == "sanitizer_report" and "heap-buffer-overflow" in report["report"]


@needs_compiler
def test_a_string_input_is_always_terminated_at_its_length(tmp_path):
    source = "unsigned length(const char *s)\n{\n\tunsigned n = 0;\n\twhile (s[n] != 0) { ++n; }\n\treturn n;\n}\n"
    root = make_case(tmp_path / "case", source, function="length", inputs=[{"name": "t", "type": "char", "string": {"max": 6}}], assertions=["length.exact"],
                     harness='    __CPROVER_assert(length(t) == t_len, "length.exact");\n', unwind=8)
    report = sampler.sample(root, "fixed", tmp_path / "out", count=20000)
    assert report["status"] == "no_failure" and report["reached_the_end"] == 20000   # a string input needs no rejection


@needs_compiler
@pytest.mark.parametrize("prelude, stop", [("#include <stdlib.h>\n", "abort();"), ("#include <stdlib.h>\n", "exit(3);"), ("", "__builtin_trap();")])
def test_a_stop_ends_the_run_and_names_the_input_where_it_can(tmp_path, prelude, stop):
    source = f"int checked(int a)\n{{\n\tif (a == 0) {{ {stop} }}\n\treturn 1;\n}}\n"
    root = make_case(tmp_path / "case", source, function="checked", prelude=prelude, assertions=["checked.ran"], harness='    (void)checked(a);\n    __CPROVER_assert(1 == 1, "checked.ran");\n')
    report = sampler.sample(root, "fixed", tmp_path / "out", count=20000)
    assert report["status"] in ("stopped", "sanitizer_report") and "draws" not in report
    if stop.startswith(("exit", "abort")):
        assert report["first_inputs"] and "a=0" in report["first_inputs"][0]


@needs_compiler
def test_an_assumption_rejects_and_a_harness_that_rejects_everything_says_so(tmp_path):
    source = "int same(int a)\n{\n\treturn a;\n}\n"
    some = make_case(tmp_path / "some", source, function="same", assumptions=1, assertions=["same.small"],
                     harness='    __CPROVER_assume(a >= 0 && a < 8);\n    __CPROVER_assert(same(a) < 8, "same.small");\n')
    report = sampler.sample(some, "fixed", tmp_path / "some-out", count=5000)
    assert report["status"] == "no_failure" and 0 < report["reached_the_end"] < 5000 and report["reached_the_end"] + report["rejected"] == 5000
    none = make_case(tmp_path / "none", source, function="same", assumptions=1, assertions=["same.small"],
                     harness='    __CPROVER_assume(a > 5 && a < 3);\n    __CPROVER_assert(same(a) == 100, "same.small");\n')
    report = sampler.sample(none, "fixed", tmp_path / "none-out", count=500)
    assert report["status"] == "nothing_reached_the_end" and report["rejected"] == 500


@needs_compiler
def test_a_seed_repeats_a_run_and_another_seed_does_not(tmp_path):
    source = "int same(int a)\n{\n\treturn a;\n}\n"
    root = make_case(tmp_path / "case", source, function="same", assumptions=1, assertions=["same.small"],
                     harness='    __CPROVER_assume(a >= 0 && a < 1000);\n    __CPROVER_assert(same(a) < 1000, "same.small");\n')
    runs = [sampler.sample(root, "fixed", tmp_path / f"out{index}", count=5000, seed=seed)["reached_the_end"] for index, seed in enumerate((7, 7, 8))]
    assert runs[0] == runs[1] and runs[0] != runs[2]


def test_a_case_that_does_not_compile_natively_says_so(tmp_path):
    if shutil.which("gcc") is None:
        pytest.skip("needs a compiler")
    root = make_case(tmp_path / "case", "int same(int a)\n{\n\treturn a;\n}\n", function="same", assertions=["same.value"],
                     harness='    __CPROVER_assert(no_such_function(a), "same.value");\n')
    assert sampler.sample(root, "fixed", tmp_path / "out", count=10)["status"] == "not_compiled"


PARSE = "long parse(const char *s)\n{\n\tchar *end;\n\treturn strtol(s, &end, 2);\n}\n"


@needs_compiler
@pytest.mark.skipif(not CBMC, reason="set CBMC to run this with the real tool")
def test_the_sampler_catches_what_a_wrong_library_model_lets_through(tmp_path):
    """This is why it exists. CBMC's strtol reads "12" in base 2 as 4, where it is 1. A harness that states the model's wrong
    answer is `complete` under the gate, since model and harness agree, and the real C library says otherwise."""
    root = make_case(tmp_path / "case", PARSE, function="parse", prelude="#include <stdlib.h>\n", assertions=["parse.wrong"], unwind=6,
                     harness='    (void)a;\n    __CPROVER_assert(parse("12") == 4, "parse.wrong");\n')
    assert cases.check(root, "fixed", tmp_path / "gate", cbmc=CBMC)["verdict"] == "complete"
    report = sampler.sample(root, "fixed", tmp_path / "sample", count=10)
    assert report["status"] == "failed_assertions" and report["failed_properties"] == ["parse.wrong"]
