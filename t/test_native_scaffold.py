"""Controls for drafting a case from a signature, and for scanning a file."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_case as cases
import native_scaffold as scaffold

CBMC = os.environ.get("CBMC", "")
real = pytest.mark.skipif(not CBMC, reason="set CBMC to run the drafts with the real tool")
needs_gcc = pytest.mark.skipif(shutil.which("gcc") is None or os.name != "posix", reason="needs a native compiler")

UNIT = """typedef unsigned long size_t;
typedef unsigned char u8;
typedef struct { int left; int right; } pair_t;
struct node { struct node *next; int value; };
enum color { RED, GREEN };
int prototype_only(int a);
static const int table[3] = {1, 2, 3};
static int unused_global = 5;
static int counter;
static int helper(int a)
{
    return a + table[0];
}
static int unused_helper(int a)
{
    return a * unused_global;
}
int top(int a)
{
    counter++;
    return helper(a);
}
struct node make(int a)
{
    struct node n = {0, a};
    return n;
}
"""


def test_top_level_items_end_where_c_says_they_do():
    items = scaffold.split_items(UNIT)
    assert items[0] == "typedef unsigned long size_t;"
    assert "typedef struct { int left; int right; } pair_t;" in items and "struct node { struct node *next; int value; };" in items
    assert "static const int table[3] = {1, 2, 3};" in items
    assert sum(item.endswith("}") for item in items) == 4
    tricky = 'static const char *s = "};{";\nint f(void)\n{\n\tchar c = \'}\'; /* }; */\n\treturn c;\n}\nint g(void);\n'
    assert scaffold.split_items(tricky) == ['static const char *s = "};{";', "int f(void)\n{\n\tchar c = '}'; /* }; */\n\treturn c;\n}", "int g(void);"]


def test_only_function_definitions_read_as_functions():
    unit = scaffold.analyse(UNIT)
    assert set(unit["functions"]) == {"helper", "unused_helper", "top", "make"}
    assert set(unit["globals"]) == {"table", "unused_global", "counter"}
    assert scaffold.function_parts("static int *f(int a, char *b) __attribute__((nonnull)) {\n return 0;\n}")[:3] == ("static int *", "f", "int a, char *b")
    assert not scaffold.is_function_head("struct node") and not scaffold.is_function_head("int x[] = (int[])") and not scaffold.is_function_head("typedef int (f)(void)")


def test_a_draft_holds_what_the_target_reaches_and_nothing_else(tmp_path):
    unit = scaffold.analyse(UNIT)
    result = scaffold.draft(unit, "top", tmp_path / "case", "x.c")
    assert "refused" not in result
    case = cases.load(tmp_path / "case")
    assert "helper(int a)" in case["prelude"] and "unused_helper" not in case["prelude"]
    assert "table[3]" in case["prelude"] and "counter;" in case["prelude"] and "unused_global" not in case["prelude"]
    assert "pair_t" in case["prelude"] and "prototype_only" in case["prelude"]   # types and declarations stay
    unit_text, _, _ = cases.build_unit(case, "original", tmp_path / "case")
    assert "int top(int a)" in unit_text and "(void)top(a);" in unit_text


TYPES = scaffold.Types(scaffold.split_items(UNIT))


@pytest.mark.parametrize("parameters, expected, arguments", [
    ("int a, unsigned long b", [{"name": "a", "type": "int"}, {"name": "b", "type": "unsigned long"}], ["a", "b"]),
    ("const char *s", [{"name": "s", "type": "char", "string": {"max": 4}}], ["(char *)s"]),
    ("const u8 *buf, size_t len", [{"name": "buf", "type": "u8", "array": {"max": 4}}], ["(u8 *)buf", "(size_t)buf_len"]),
    ("const void *p, size_t n", [{"name": "p", "type": "unsigned char", "array": {"max": 4}}], ["(void *)p", "(size_t)p_len"]),
    ("int *out", [{"name": "out", "type": "int", "array": {"min": 1, "max": 1}}], ["(int *)out"]),
    ("char buf[], size_t size", [{"name": "buf", "type": "char", "array": {"max": 4}}], ["(char *)buf", "(size_t)buf_len"]),
    ("enum color c", [{"name": "c", "type": "enum color"}], ["c"]),
    ("_Bool flag", [{"name": "flag", "type": "unsigned char"}], ["(flag != 0)"]),
    ("void", [{"name": "dawnr_unused", "type": "int"}], []),
])
def test_a_parameter_becomes_an_input_by_its_type(parameters, expected, arguments):
    plan = scaffold.plan_inputs(parameters, TYPES, 4)
    assert plan["inputs"] == expected and plan["arguments"] == arguments


def test_two_pointers_share_the_length_that_follows_them():
    plan = scaffold.plan_inputs("const void *a, const void *b, size_t n", TYPES, 4)
    assert [item["name"] for item in plan["inputs"]] == ["a", "b"]
    assert plan["assumptions"] == ["    __CPROVER_assume(b_len == a_len);\n"]
    assert plan["arguments"] == ["(void *)a", "(void *)b", "(size_t)a_len"]


def test_a_guess_is_recorded_so_the_reader_can_doubt_it():
    assert "out points to one element" in scaffold.plan_inputs("int *out", TYPES, 4)["guesses"]
    assert "len is the length of buf" in scaffold.plan_inputs("u8 *buf, size_t len", TYPES, 4)["guesses"]


def test_a_pointer_named_as_the_end_of_the_one_before_it_makes_one_array():
    plan = scaffold.plan_inputs("const char *s, const char *se, char *d, char *de", TYPES, 4)
    assert plan["inputs"] == [{"name": "s", "type": "char", "array": {"max": 4}}, {"name": "d", "type": "char", "array": {"max": 4}}]
    assert plan["arguments"] == ["(char *)s", "(char *)(s + s_len)", "(char *)d", "(char *)(d + d_len)"]
    assert "se is the end of s" in plan["guesses"] and plan["assumptions"] == []


@pytest.mark.parametrize("first, second, expected", [
    ("s", "se", True), ("buf", "buf_end", True), ("begin", "end", True), ("src", "srclimit", True), ("p", "pe", True),
    ("dst", "src", False), ("s", "s2", False), ("first", "last", False), ("a", "b", False), ("data", "dataset", False),
])
def test_only_a_name_that_says_so_ends_a_pointer(first, second, expected):
    assert scaffold.is_end_of(first, second) is expected


def test_pointers_of_two_types_are_not_a_pair_however_they_are_named():
    plan = scaffold.plan_inputs("const char *s, const u8 *se", TYPES, 4)
    assert [item["name"] for item in plan["inputs"]] == ["s", "se"] and len(plan["arguments"]) == 2 and "(char *)(s + s_len)" not in plan["arguments"]


def test_a_length_named_after_one_pointer_is_that_pointers_alone():
    plan = scaffold.plan_inputs("char *dst, const char *src, size_t dst_size", TYPES, 4)
    assert plan["inputs"] == [{"name": "dst", "type": "char", "array": {"max": 4}}, {"name": "src", "type": "char", "string": {"max": 4}}]
    assert plan["arguments"] == ["(char *)dst", "(char *)src", "(size_t)dst_len"] and plan["assumptions"] == []


def test_beside_a_writable_pointer_a_const_char_pointer_is_a_string():
    plan = scaffold.plan_inputs("const char *source, u8 *out, size_t n", TYPES, 4)
    assert plan["inputs"] == [{"name": "source", "type": "char", "string": {"max": 4}}, {"name": "out", "type": "u8", "array": {"max": 4}}]
    assert plan["arguments"] == ["(char *)source", "(u8 *)out", "(size_t)out_len"]


def test_two_constant_strings_still_share_a_length():
    plan = scaffold.plan_inputs("const char *a, const char *b, size_t n", TYPES, 4)
    assert plan["assumptions"] == ["    __CPROVER_assume(b_len == a_len);\n"]


def test_a_length_is_found_past_another_scalar_and_not_past_another_pointer():
    plan = scaffold.plan_inputs("void *dst, u8 value, size_t len", TYPES, 4)
    assert plan["inputs"] == [{"name": "dst", "type": "unsigned char", "array": {"max": 4}}, {"name": "value", "type": "u8"}]
    assert plan["arguments"] == ["(void *)dst", "value", "(size_t)dst_len"]
    far = scaffold.plan_inputs("const char *a, int mode, u8 *b, size_t n", TYPES, 4)
    assert far["inputs"][0] == {"name": "a", "type": "char", "string": {"max": 4}} and far["inputs"][2] == {"name": "b", "type": "u8", "array": {"max": 4}}


def test_an_array_parameter_has_the_size_it_declares():
    plan = scaffold.plan_inputs("u8 digest[16], size_t n", TYPES, 4)
    assert plan["inputs"][0] == {"name": "digest", "type": "u8", "array": {"min": 16, "max": 16}} and plan["arguments"] == ["(u8 *)digest", "n"]
    assert "digest has the 16 elements it declares" in plan["guesses"]
    assert "declares an array" in scaffold.plan_inputs("u8 huge[4096]", TYPES, 4)["refused"]


def test_the_file_s_own_functions_come_from_the_line_markers_wherever_the_name_starts():
    expanded = ('# 0 "a.c"\n# 0 "<built-in>"\n#define X 1\n# 1 "a.c"\n# 1 "a.h" 1\nstatic int from_header(int a) { return a; }\n# 2 "a.c" 2\n'
                'int\nat_line_start(int a)\n{\n  return a;\n}\nstatic inline int beside(void) { return 1; }\nint declared_only(int a);\n')
    assert scaffold.own_functions(expanded) == {"at_line_start", "beside"}


def test_a_function_that_reaches_the_operating_system_is_not_drafted_to_be_run(tmp_path):
    source = "int kill(int, int);\nstatic int helper(int a)\n{\n\treturn kill(a, 9);\n}\nint f(int a)\n{\n\treturn helper(a);\n}\nint g(int a)\n{\n\treturn a;\n}\n"
    unit = scaffold.analyse(source)
    assert "operating system (kill)" in scaffold.draft(unit, "f", tmp_path / "f", "t.c")["refused"]
    assert "refused" not in scaffold.draft(unit, "g", tmp_path / "g", "t.c")
    assert "refused" not in scaffold.draft(unit, "f", tmp_path / "f-allowed", "t.c", allow_system=True)


@pytest.mark.parametrize("text, expected", [
    ("return s->close(s);", False), ("return s.read(s);", False), ("int read = 1; return read;", False), ("static int close_all(void);", False),
    ("return close(fd);", True), ("return close (fd);", True), ("x = (write)(1, p, n);", False),
])
def test_only_a_call_by_that_name_counts_as_reaching_the_system(text, expected):
    assert bool(scaffold.SYSTEM_CALL.search(text)) is expected


def test_a_function_that_defines_its_own_read_is_not_refused_for_it(tmp_path):
    unit = scaffold.analyse("static int read(int a)\n{\n\treturn a;\n}\nint f(int a)\n{\n\treturn read(a);\n}\n")
    assert "refused" not in scaffold.draft(unit, "f", tmp_path / "f", "t.c")


def test_a_scan_will_not_run_what_it_was_told_may_reach_the_system(tmp_path):
    with pytest.raises(SystemExit):
        scaffold.main([str(tmp_path / "a.c"), "--scan", "--allow-system", "--out", str(tmp_path / "out")])


def witness_of(status, access=None):
    return {"status": status, "detail": {"access": access}}


def test_a_memory_error_past_a_buffer_of_unknown_size_says_so():
    row = {"unsized_strings": ["dst"], "single_elements": []}
    assert "no size" in scaffold.doubt(row, [witness_of("memory_error", "WRITE")])
    assert scaffold.doubt(row, [witness_of("memory_error", "READ")]) is None, "a string says where it ends, so a read past the end is the function's own"
    assert "one element" in scaffold.doubt({"unsized_strings": [], "single_elements": ["out"]}, [witness_of("memory_error", "READ")])


def test_a_failure_with_no_guess_behind_it_carries_no_doubt():
    assert scaffold.doubt({"unsized_strings": [], "single_elements": []}, [witness_of("memory_error", "WRITE")]) is None
    assert scaffold.doubt({"unsized_strings": ["dst"], "single_elements": ["out"]}, [witness_of("undefined_behavior")]) is None
    sampled = {"unsized_strings": ["dst"], "single_elements": [], "sample": {"status": "sanitizer_report", "report": "ERROR: AddressSanitizer: heap-buffer-overflow", "access": "WRITE"}}
    assert "no size" in scaffold.doubt(sampled, [])


@pytest.mark.parametrize("report", ["t.c:1:1: runtime error: store to null pointer of type 'float'", "ERROR: AddressSanitizer: SEGV on unknown address 0x000000000000 (pc 0x1 bp 0x1 sp 0x1 T0)"])
def test_a_null_the_draft_did_not_pass_comes_from_state_it_did_not_set_up(report):
    row = {"unsized_strings": [], "single_elements": [], "sample": {"status": "sanitizer_report", "report": report}}
    assert "state it did not set up" in scaffold.doubt(row, [])


def test_the_project_s_own_assert_is_not_a_candidate():
    aborted = {"sample": {"status": "sanitizer_report", "report": "ERROR: AddressSanitizer: ABRT on unknown address 0xfffe (pc 0x1)"}}
    assert not scaffold.sampler_failed(aborted) and scaffold.doubt(aborted, []) is None
    assert scaffold.sampler_failed({"sample": {"status": "sanitizer_report", "report": "ERROR: AddressSanitizer: heap-buffer-overflow"}})
    assert not scaffold.sampler_failed({"sample": {"status": "no_failure"}}) and not scaffold.sampler_failed({})


@real
@needs_gcc
def test_a_failing_assert_is_counted_and_not_listed(tmp_path):
    source = tmp_path / "guarded.c"
    source.write_text("#include <assert.h>\nint guarded(int a)\n{\n    assert(a != 7);\n    return a;\n}\n")
    args = argparse.Namespace(include=[], define=[], compiler="gcc", machine="LP64", out=tmp_path / "scan", max_length=4, unwind=6, repository="test", revision="test", cbmc=CBMC, timeout=60,
                              memory_limit_mb=2048, solver="minisat2", jobs=2, sample=2000)
    report = scaffold.scan(source, args)
    assert report["candidates"] == [] and report["project_asserts"] == ["guarded"], json.dumps(report)[:600]


def test_asan_says_whether_it_read_or_wrote():
    report = "==1==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x1\nWRITE of size 1 at 0x1 thread T0\n"
    assert cases.native.memory_access(report) == "WRITE" and cases.native.memory_access(report.replace("WRITE", "READ")) == "READ"
    assert cases.native.memory_access("t.c:1:1: runtime error: signed integer overflow\n") is None


@needs_gcc
def test_a_file_with_each_name_on_its_own_line_is_still_scanned(tmp_path):
    (tmp_path / "helper.h").write_text("static inline int from_header(int a) { return a; }\n")
    source = tmp_path / "gnu.c"
    source.write_text('#include "helper.h"\nint\nlisted(int a)\n{\n  return from_header(a);\n}\n')
    unit = scaffold.load_unit(source, [str(tmp_path)], [])
    assert unit["own"] == {"listed"} and {"listed", "from_header"} <= set(unit["functions"])


@pytest.mark.parametrize("parameters, reason", [
    ("int (*cb)(int)", "function pointer"), ("char **argv", "pointer to a pointer"), ("pair_t p", "aggregate by value"), ("struct node *n", "pointer to an aggregate"),
    ("const char *fmt, ...", "variable arguments"), ("void *opaque", "void pointer with no length"), ("_Bool *flag", "pointer to a bool"), ("pair_t *p, size_t n", "pointer to an aggregate"),
])
def test_what_a_draft_cannot_fill_in_is_refused_by_name(parameters, reason):
    assert reason in scaffold.plan_inputs(parameters, TYPES, 4)["refused"]


def test_a_model_is_linked_when_the_code_calls_it_and_not_when_the_file_defines_it(tmp_path):
    source = "unsigned long strspn(const char *, const char *);\nint f(const char *s)\n{\n\treturn (int)strspn(s, \"a\");\n}\n"
    result = scaffold.draft(scaffold.analyse(source), "f", tmp_path / "uses", "x.c")
    assert result["models"] == ["string"]
    own = "unsigned long strspn(const char *a, const char *b)\n{\n\treturn 0;\n}\nint f(const char *s)\n{\n\treturn (int)strspn(s, \"a\");\n}\n"
    assert scaffold.draft(scaffold.analyse(own), "f", tmp_path / "own", "x.c")["models"] == []


def scan_args(out, **changes):
    values = dict(include=[], define=[], compiler="gcc", machine="LP64", out=out, max_length=4, unwind=6, repository="example/synthetic", revision="synthetic", cbmc=CBMC,
                  timeout=60, memory_limit_mb=2048, solver="cadical", jobs=2, sample=2000)
    values.update(changes)
    return argparse.Namespace(**values)


PLANTED = """#include <stddef.h>
/* Reads one past the end when n is the length of the buffer. */
int broken_sum(const unsigned char *p, size_t n)
{
    int total = 0;
    for (size_t i = 0; i <= n; ++i) { total += p[i]; }
    return total;
}
int sound_sum(const unsigned char *p, size_t n)
{
    int total = 0;
    for (size_t i = 0; i < n; ++i) { total += p[i]; }
    return total;
}
int broken_shift(int a)
{
    return 1 << a;
}
int takes_a_callback(int (*cb)(int))
{
    return cb(1);
}
int calls_outside(int a)
{
    extern int elsewhere(int);
    return elsewhere(a);
}
"""


@real
@needs_gcc
def test_a_scan_lists_the_planted_defects_and_not_the_sound_twin(tmp_path):
    source = tmp_path / "planted.c"
    source.write_text(PLANTED)
    report = scaffold.scan(source, scan_args(tmp_path / "scan"))
    assert report["functions"] == 5 and report["drafted"] == 4
    assert [row["function"] for row in report["refused"]] == ["takes_a_callback"]
    rows = {row["function"]: row for row in report["rows"]}
    assert rows["broken_sum"]["candidate"] and "memory_error" in rows["broken_sum"]["witness_statuses"]
    assert rows["broken_shift"]["candidate"] and "undefined_behavior" in rows["broken_shift"]["witness_statuses"]
    assert rows["sound_sum"]["verdict"] == "complete" and not rows["sound_sum"]["candidate"]
    assert rows["calls_outside"]["verdict"] == "incomplete" and not rows["calls_outside"]["candidate"]
    assert {row["function"] for row in report["candidates"]} == {"broken_sum", "broken_shift"}
    assert report["reminder"] == "a candidate is not a bug until someone has read it"


@real
@needs_gcc
def test_a_drafted_case_goes_through_the_gate_as_any_other(tmp_path):
    source = tmp_path / "planted.c"
    source.write_text(PLANTED)
    assert scaffold.main([str(source), "--function", "sound_sum", "--out", str(tmp_path / "case")]) == 0
    assert cases.check(tmp_path / "case", "original", tmp_path / "gate", cbmc=CBMC, solver="cadical")["verdict"] == "complete"


@needs_gcc
def test_a_function_the_file_does_not_define_is_refused(tmp_path, capsys):
    source = tmp_path / "planted.c"
    source.write_text(PLANTED)
    assert scaffold.main([str(source), "--function", "no_such_function", "--out", str(tmp_path / "case")]) == 2
    assert "not defined" in capsys.readouterr().out


def test_exactly_one_mode_is_asked_for(tmp_path):
    with pytest.raises(SystemExit):
        scaffold.main([str(tmp_path / "x.c"), "--out", str(tmp_path / "out")])
    with pytest.raises(SystemExit):
        scaffold.main([str(tmp_path / "x.c"), "--scan", "--function", "f", "--out", str(tmp_path / "out")])


def test_a_system_header_goes_back_to_being_an_include_and_a_project_header_stays_expanded():
    text = ('# 0 "x.c"\n# 0 "<built-in>"\n#define __STDC__ 1\n# 0 "<command-line>"\n#define _GNU_SOURCE 1\n#define OTHER 2\n# 1 "x.c"\n'
            '#define LOCAL 3\n# 1 "/usr/include/stdio.h" 1 3 4\n# 27 "/usr/include/stdio.h" 3 4\n# 1 "/usr/include/bits/types.h" 1 3 4\nextern int hidden;\n# 30 "/usr/include/stdio.h" 2 3 4\ntypedef int system_type;\n'
            '# 2 "x.c" 2\n# 1 "project.h" 1\ntypedef int project_type;\n# 3 "x.c" 2\n# 1 "/usr/include/stdio.h" 1 3 4\n# 4 "x.c" 2\n# 1 "/opt/odd/odd.h" 1 3\nextern int odd;\n# 5 "x.c" 2\nint f(void);\n')
    out = scaffold.strip_system_headers(text, ["/usr/include"]).splitlines()
    assert out == ["#define _GNU_SOURCE 1", "#include <stdio.h>", "typedef int project_type;", '#include "/opt/odd/odd.h"', "int f(void);"]


@needs_gcc
def test_a_real_file_keeps_its_includes_and_its_feature_macro(tmp_path):
    (tmp_path / "local.h").write_text("typedef int local_t;\n#define DOUBLE(x) ((x) * 2)\n")
    source = tmp_path / "x.c"
    source.write_text('#define _GNU_SOURCE\n#include <string.h>\n#include "local.h"\nlocal_t twice(local_t a)\n{\n\treturn DOUBLE(a);\n}\n')
    text = scaffold.preprocess(source, [], [])
    assert text.index("#define _GNU_SOURCE") < text.index("#include <string.h>")
    assert "typedef int local_t;" in text and "((a) * 2)" in text and "extern" not in text and "DOUBLE" not in text


@real
@needs_gcc
def test_a_draft_with_system_headers_compiles_natively_and_its_witness_replays(tmp_path):
    source = tmp_path / "x.c"
    source.write_text('#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\nint first(const char *s, size_t n)\n{\n\t(void)n;\n\treturn s[0] + (int)strlen("a");\n}\n')
    report = scaffold.scan(source, scan_args(tmp_path / "scan"))
    row = report["rows"][0]
    assert row["function"] == "first" and row["verdict"] == "counterexample" and row["candidate"]
    assert "memory_error" in row["witness_statuses"] and row["sample"]["status"] == "sanitizer_report"
