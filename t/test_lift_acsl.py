"""The C/ACSL front end (t/lift_acsl.py) and its checks (t/lift_acsl_check.py), per construct.

No corpus is needed: every test writes its own C and ACSL in the shape of ACSL by Example
(github.com/fraunhoferfokus/acsl-by-example). Front-end tests need nothing installed; the
end-to-end tests need dafny (the lifter's resolver), the WP tests frama-c, the differential
tests gcc, and each is skipped without it. The WP tests include negative controls: a lifted
clause, spec function or call site deliberately corrupted must leave its lemma unproved, so a
proved lemma is not a vacuous one.

    cd t && python3 -m unittest test_lift_acsl
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lift_acsl as L                                            # noqa: E402
import lift_acsl_check as C                                      # noqa: E402

TYPEDEFS = """
#ifndef TYPEDEFS_H_INCLUDED
#define TYPEDEFS_H_INCLUDED
#include <limits.h>
#ifndef __cplusplus
typedef int bool;
#define false ((bool)0)
#define true  ((bool)1)
#endif
typedef int value_type;
#define VALUE_TYPE_MAX INT_MAX
#define VALUE_TYPE_MIN INT_MIN
typedef unsigned int size_type;
#endif
"""

COUNT_ACSL = """
#ifndef COUNT_ACSL_INCLUDED
#define COUNT_ACSL_INCLUDED
#include "typedefs.h"
/*@
  logic integer
  Count(value_type* a, integer m, integer n, value_type v) =
    n <= m ? 0 : Count(a, m, n-1, v) + (a[n-1] == v ? 1 : 0);

  logic integer
  Count(value_type* a, integer n, value_type v) = Count(a, 0, n, v);

  lemma Count_Empty:
    \\forall value_type *a, v, integer m, n;  n <= m  ==>  Count(a, m, n, v) == 0;
*/
#endif
"""

COUNT_H = """
#ifndef COUNT_H_INCLUDED
#define COUNT_H_INCLUDED
#include "Count.acsl"
/*@
  requires   valid:  \\valid_read(a + (0..n-1));
  terminates         \\true;
  exits              \\false;
  assigns            \\nothing;
  ensures    bound:  0 <= \\result <= n;
  ensures    count:  \\result == Count(a, n, v);
*/
size_type count(const value_type* a, size_type n, value_type v);
#endif
"""

COUNT_C = """
#include "count.h"

size_type count(const value_type* a, size_type n, value_type v)
{
  size_type counted = 0u;
  /*@
    loop invariant bound: 0 <= i <= n;
    loop invariant bound: 0 <= counted <= i;
    loop invariant count: counted == Count(a, i, v);
    loop assigns i, counted;
    loop variant n-i;
  */
  for (size_type i = 0u; i < n; ++i) {
    if (a[i] == v) {
      counted++;
    }
  }
  return counted;
}
"""


class Corpus:
    """A throwaway StandardAlgorithms-shaped tree."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="lift_acsl_"))
        self.root = self.dir / "StandardAlgorithms"
        (self.root / "Logic").mkdir(parents=True)
        (self.root / "Algo").mkdir()
        (self.root / "typedefs.h").write_text(TYPEDEFS)

    def logic(self, name: str, text: str) -> None:
        (self.root / "Logic" / name).write_text(text)

    def fn(self, stem: str, header: str, body: str) -> Path:
        (self.root / "Algo" / f"{stem}.h").write_text(header)
        p = self.root / "Algo" / f"{stem}.c"
        p.write_text(body)
        return p

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def simple(stem: str, contract: str, sig: str, body: str, logic: str = "") -> tuple[str, str]:
    guard = stem.upper() + "_H"
    h = f"#ifndef {guard}\n#define {guard}\n#include \"typedefs.h\"\n{logic}\n/*@\n{contract}\n*/\n{sig};\n#endif\n"
    c = f"#include \"{stem}.h\"\n{sig}\n{{\n{body}\n}}\n"
    return h, c


class FrontEnd(unittest.TestCase):
    def setUp(self):
        self.c = Corpus()
        self.c.logic("Count.acsl", COUNT_ACSL)

    def tearDown(self):
        self.c.close()

    def lift(self, stem, contract, sig, body, logic=""):
        h, c = simple(stem, contract, sig, body, logic)
        return L.translate(self.c.fn(stem, h, c), self.c.root)

    def refused(self, reason, stem, contract, sig, body, logic=""):
        with self.assertRaises(L.AcslRefusal) as cm:
            self.lift(stem, contract, sig, body, logic)
        self.assertEqual(cm.exception.reason, reason, cm.exception)

    # -- preprocessing and parsing
    def test_include_once_and_macro_in_annotation(self):
        h, c = simple("mx", "requires v <= VALUE_TYPE_MAX - 1;\nassigns \\nothing;\nensures \\result == v + 1;",
                      "value_type mx(value_type v)", "return v + 1;")
        h = h.replace('#include "typedefs.h"', '#include "typedefs.h"\n#include "typedefs.h"')
        out = L.translate(self.c.fn("mx", h, c), self.c.root)
        self.assertIn("requires (v <= (2147483647 - 1))", out.dafny)

    def test_clause_names_are_dropped_not_ternaries(self):
        out = self.lift("tern", "assigns \\nothing;\nensures res: \\result == (v < 0 ? 0 : v);",
                        "value_type tern(value_type v)", "return v < 0 ? 0 : v;")
        self.assertIn("ensures (result == (if (v < 0) then 0 else v))", out.dafny)

    # -- types and parameters
    def test_valid_read_becomes_seq_and_length_becomes_len(self):
        out = L.translate(self.c.fn("count", COUNT_H, COUNT_C), self.c.root)
        self.assertIn("method count(a: seq<int>, v: int) returns (result: nat)", out.dafny)
        self.assertIn("ensures (result == Count4(a, 0, |a|, v))", out.dafny)
        self.assertEqual([p["role"] for p in out.params], ["seq", "len", "scalar"])
        self.assertIn(("valid-read-as-seq", 1), out.clauses_dropped)

    def test_unsigned_is_nat_and_generalisation_recorded(self):
        out = L.translate(self.c.fn("count", COUNT_H, COUNT_C), self.c.root)
        self.assertIn("var counted: nat := 0;", out.dafny)
        rules = [r for r, _ in out.clauses_added]
        self.assertIn("unsigned-as-nat", rules)
        self.assertIn("machine-int-generalized", rules)

    def test_two_arrays_one_length(self):
        out = self.lift("eq2", "requires \\valid_read(a + (0..n-1));\nrequires \\valid_read(b + (0..n-1));\n"
                               "assigns \\nothing;\nensures \\result <==> (\\forall integer i; 0 <= i < n ==> a[i] == b[i]);",
                        "bool eq2(const value_type* a, size_type n, const value_type* b)",
                        "/*@ loop invariant 0 <= i <= n;\n loop invariant \\forall integer k; 0 <= k < i ==> a[k] == b[k];"
                        "\n loop variant n - i; */\nfor (size_type i = 0u; i < n; i++) { if (a[i] != b[i]) { return false; } }"
                        "\nreturn true;")
        self.assertIn("requires |b| == |a|", out.dafny)
        self.assertIn("returns (result: bool)", out.dafny)
        self.assertIn("return false;", out.dafny)

    def test_mutated_parameter_is_copied(self):
        out = self.lift("acc", "requires \\valid_read(a + (0..n-1));\nassigns \\nothing;\nensures \\result == \\old(s);",
                        "value_type acc(const value_type* a, size_type n, value_type s)",
                        "/*@ loop invariant 0 <= i <= n;\n loop invariant s == \\at(s, Pre);\n loop variant n - i; */\n"
                        "for (size_type i = 0u; i < n; i++) { s = s + 0; }\nreturn s;")
        self.assertIn("method acc(a: seq<int>, s0: int)", out.dafny)
        self.assertIn("var s: int := s0;", out.dafny)
        self.assertIn("invariant (s == s0)", out.dafny)
        self.assertIn("ensures (result == s0)", out.dafny)

    # -- loops
    def test_for_is_init_then_while_with_step_last(self):
        out = L.translate(self.c.fn("count", COUNT_H, COUNT_C), self.c.root)
        lines = [x.strip() for x in out.dafny.splitlines()]
        w = lines.index("while (i < |a|)")
        self.assertEqual(lines[w - 1], "var i: nat := 0;")
        close = len(lines) - 1 - lines[::-1].index("}", len(lines) - lines.index("return counted;"))
        self.assertEqual(lines[lines.index("return counted;") - 2], "i := i + 1;")
        self.assertIn("decreases (|a| - i)", lines)
        self.assertTrue(close > w)

    def test_loop_without_variant_leaves_it_to_dafny(self):
        out = self.lift("nv", "requires \\valid_read(a + (0..n-1));\nassigns \\nothing;\nensures \\result == n;",
                        "size_type nv(const value_type* a, size_type n)",
                        "size_type i = 0u;\n/*@ loop invariant 0 <= i <= n; */\nwhile (i < n) { i++; }\nreturn i;")
        self.assertNotIn("decreases", out.dafny)
        self.assertIn("variant-inferred-by-dafny", out.rewrites)

    def test_loop_under_guard_becomes_early_return(self):
        body = ("if (0u < n) {\n size_type i = 0u;\n /*@ loop invariant 0 <= i <= n; loop variant n - i; */\n"
                " while (i < n) { if (a[i] == 0) { return i; } i++; }\n}\nreturn n;")
        out = self.lift("gi", "requires \\valid_read(a + (0..n-1));\nassigns \\nothing;\nensures \\result <= n;",
                        "size_type gi(const value_type* a, size_type n)", body)
        lines = [x.strip() for x in out.dafny.splitlines()]
        start = lines.index("{")
        self.assertEqual(lines[start + 1:start + 4], ["if !(0 < |a|) {", "return |a|;", "}"])
        self.assertEqual(lines[-2], "return |a|;")      # the fall-through path keeps its return
        self.assertIn("guard-inverted-early-return", out.rewrites)

    # -- logic definitions
    def test_recursive_logic_function_is_a_guarded_spec_fun(self):
        out = L.translate(self.c.fn("count", COUNT_H, COUNT_C), self.c.root)
        self.assertIn("function Count4(a: seq<int>, m: int, n: int, v: int): int", out.dafny)
        self.assertIn("decreases (n - m)", out.dafny)
        self.assertIn("(if 0 <= (n - 1) < |a| then a[(n - 1)] else 0)", out.dafny)
        rf = out.rec_funs[0]
        self.assertEqual(rf.rec_param, "n")
        self.assertEqual(rf.domain, ["0 <= m <= a_n", "0 <= n <= a_n"])

    def test_non_recursive_predicate_is_inlined_capture_avoiding(self):
        logic = "/*@ predicate AllBelow{L}(value_type* a, integer n, integer b) =\n" \
                "     \\forall integer i; 0 <= i < n ==> a[i] < b; */"
        out = self.lift("cap", "requires \\valid_read(a + (0..n-1));\nrequires \\forall integer i; 0 <= i < n ==> "
                               "AllBelow(a, n, i + 1);\nassigns \\nothing;\nensures \\result == 0;",
                        "value_type cap(const value_type* a, size_type n)", "return 0;", logic)
        req = [x for x in out.dafny.splitlines() if "requires" in x][0]
        # the predicate's own binder must not capture the caller's i
        self.assertIn("(i + 1)", req)
        self.assertIn("i2", req)

    def test_overloads_resolve_by_parameter_kind(self):
        logic = ("/*@ predicate Same{K,L}(value_type* a, integer m, integer n, value_type* b) =\n"
                 "     \\forall integer i; m <= i < n ==> \\at(a[i],K) == \\at(b[i],L);\n"
                 "   predicate Same{K,L}(value_type* a, integer m, integer n, integer p) =\n"
                 "     \\forall integer i; m <= i < n ==> \\at(a[i],K) == \\at(a[p],L); */")
        out = self.lift("ov", "requires \\valid_read(a + (0..n-1));\nrequires \\valid_read(b + (0..n-1));\n"
                              "assigns \\nothing;\nensures \\result == 0 ==> Same{Here,Here}(a, 0, n, b);",
                        "value_type ov(const value_type* a, size_type n, const value_type* b)", "return 1;", logic)
        self.assertIn("(a[i] == b[i])", out.dafny)
        self.assertIn("single-state-labels-merged", out.rewrites)

    def test_behaviors_become_implications(self):
        out = self.lift("beh", "assigns \\nothing;\nbehavior neg: assumes v < 0; ensures \\result == -v;\n"
                               "behavior pos: assumes v >= 0; ensures \\result == v;\ncomplete behaviors;\n"
                               "disjoint behaviors;",
                        "value_type beh(value_type v)", "return v < 0 ? -v : v;")
        self.assertIn("ensures ((v < 0) ==> (result == (-v)))", out.dafny)
        self.assertIn(("complete-behaviors", 1), out.clauses_dropped)
        self.assertIn(("disjoint-behaviors", 1), out.clauses_dropped)
        self.assertIn("behavior-to-implication", out.rewrites)

    def test_unsigned_division_lifts_signed_spec_division_is_flagged(self):
        out = self.lift("half", "assigns \\nothing;\nensures \\result == (c - 1) / 2;",
                        "size_type half(size_type c)", "return c > 0u ? (c - 1u) / 2u : 0u;")
        self.assertTrue(out.spec_division)
        self.assertIn("((c - 1) / 2)", out.dafny)

    # -- refusals, one per construct
    def test_refuse_array_write(self):
        self.refused("array-write", "fill1", "requires \\valid(a + (0..n-1));\nassigns a[0..n-1];\nensures \\true;",
                     "size_type fill1(value_type* a, size_type n)", "return 0u;")

    def test_refuse_non_const_pointer(self):
        self.refused("array-write", "nc", "requires \\valid_read(a + (0..n-1));\nassigns \\nothing;\nensures \\true;",
                     "size_type nc(value_type* a, size_type n)", "return 0u;")

    def test_refuse_signed_division_in_code(self):
        self.refused("signed-division", "sd", "assigns \\nothing;\nensures \\true;",
                     "value_type sd(value_type x)", "return x / 2;")

    def test_refuse_break_and_continue(self):
        loop = "size_type i = 0u;\n/*@ loop invariant 0 <= i <= n; loop variant n - i; */\nwhile (i < n) { %s i++; }\nreturn i;"
        for stmt, reason in (("if (i == 3u) break;", "break"), ("if (i == 3u) { i++; continue; }", "continue")):
            with self.subTest(reason=reason):
                self.refused(reason, "bk", "requires \\valid_read(a + (0..n-1));\nassigns \\nothing;\nensures \\true;",
                             "size_type bk(const value_type* a, size_type n)", loop % stmt)

    def test_refuse_call(self):
        h = "#include \"typedefs.h\"\n/*@ assigns \\nothing; ensures \\true; */\nvalue_type g(value_type x);\n" \
            "/*@ assigns \\nothing; ensures \\true; */\nvalue_type cl(value_type x);\n"
        p = self.c.fn("cl", h, "#include \"cl.h\"\nvalue_type cl(value_type x) { return g(x); }\n")
        with self.assertRaises(L.AcslRefusal) as cm:
            L.translate(p, self.c.root)
        self.assertEqual(cm.exception.reason, "calls-other-method")

    def test_refuse_pointer_arithmetic(self):
        self.refused("pointer-deref", "pa", "requires \\valid_read(a + (0..n-1));\nassigns \\nothing;\nensures \\true;",
                     "value_type pa(const value_type* a, size_type n)", "return *(a + 1);")

    def test_refuse_ghost_code(self):
        self.refused("ghost-code", "gh", "assigns \\nothing;\nensures \\true;", "value_type gh(value_type x)",
                     "//@ ghost int y = 0;\nreturn x;")

    def test_refuse_loop_without_invariant(self):
        self.refused("loop-without-invariant", "ni", "requires \\valid_read(a + (0..n-1));\nassigns \\nothing;\n"
                                                     "ensures \\true;", "size_type ni(const value_type* a, size_type n)",
                     "size_type i = 0u;\nwhile (i < n) { i++; }\nreturn i;")

    def test_refuse_mixed_sign_comparison(self):
        self.refused("mixed-sign-comparison", "ms", "assigns \\nothing;\nensures \\true;",
                     "bool ms(value_type x, size_type y)", "return x < y;")

    def test_refuse_struct_and_void(self):
        self.refused("void-result", "vd", "assigns \\nothing;\nensures \\true;", "void vd(value_type x)", "return;")

    def test_refuse_abstract_logic(self):
        logic = "/*@ axiomatic Ax { logic integer F(integer x); axiom f0: F(0) == 0; } */"
        self.refused("axiomatic", "ax", "assigns \\nothing;\nensures \\result == F(x);",
                     "value_type ax(value_type x)", "return 0;", logic)


# ------------------------------------------------------------------ check --

class Printing(unittest.TestCase):
    def test_bool_equality_is_iff_and_div_is_euclidean(self):
        pr = C.Printer({"r": "result", "x": "x"}, {}, {}, {"r": "bool", "x": "int"})
        e = {"op": "==", "args": [{"var": "r"}, {"op": "<", "args": [{"var": "x"}, {"int": 0}]}]}
        self.assertEqual(pr.pred(e), "((result != 0) <==> (x < 0))")
        d = {"op": "==", "args": [{"var": "x"}, {"op": "div", "args": [{"var": "x"}, {"int": 2}]}]}
        self.assertEqual(pr.pred(d), "(x == t_div(x, 2))")
        self.assertTrue(pr.divmod)

    def test_quantifier_and_len(self):
        pr = C.Printer({"s": "a"}, {"s": "n"}, {}, {"s": "seq"})
        e = {"forall": {"var": "i", "lo": {"int": 0}, "hi": {"op": "len", "args": [{"var": "s"}]},
                        "body": {"op": ">=", "args": [{"op": "at", "args": [{"var": "s"}, {"var": "i"}]},
                                                      {"int": 0}]}}}
        self.assertEqual(pr.pred(e), "(\\forall integer tq1_i; 0 <= tq1_i < n ==> (a[tq1_i] >= 0))")

    def test_call_contexts_follow_short_circuit(self):
        call = {"call": {"fun": "f", "args": [{"var": "i"}]}}
        e = {"op": "implies", "args": [{"op": "<", "args": [{"var": "i"}, {"int": 3}]}, call]}
        out = []
        C.calls_with_context(e, [], out, {"f"})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][1], [{"op": "<", "args": [{"var": "i"}, {"int": 3}]}])


def have(tool: str) -> bool:
    if tool == "frama-c":
        return os.path.exists(C.FRAMAC)
    if tool == "dafny":
        return shutil.which("dafny") is not None or os.path.exists(os.path.expanduser("~/.local/dafny/dafny"))
    return shutil.which(tool) is not None


def lift_to_t(c_file: Path, root: Path) -> tuple[dict, dict, dict]:
    """front end -> lifter (skip-check) -> (task, record dict, front-end sidecar)."""
    import lifter
    lifted = L.translate(c_file, root)
    d = Path(tempfile.mkdtemp(prefix="lift_acsl_dfy_"))
    try:
        dfy = d / f"acsl_{c_file.stem}.dfy"
        dfy.write_text(lifted.dafny)
        out = lifter.lift_file(dfy, out_dir=None, skip_check=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    mo = out.methods[0]
    if mo.task is None:
        raise AssertionError(f"lifter refused: {mo.refusal}")
    side = json.loads(json.dumps(lifted.sidecar(), default=str))
    side["c_file"] = str(c_file)
    return mo.task, lifter._record_to_dict(mo.record), side


@unittest.skipUnless(have("dafny"), "needs dafny (the lifter's resolver)")
class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PATH"] = os.path.expanduser("~/.local/dafny") + os.pathsep + os.environ["PATH"]
        cls.c = Corpus()
        cls.c.logic("Count.acsl", COUNT_ACSL)
        cls.cfile = cls.c.fn("count", COUNT_H, COUNT_C)
        cls.task, cls.record, cls.side = lift_to_t(cls.cfile, cls.c.root)

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    def test_lifted_task_shape(self):
        t = self.task
        self.assertEqual([p["type"] for p in t["params"]], ["seq", "int"])
        self.assertEqual(len(t["spec_funs"]), 1)
        self.assertEqual(len(C.body_loops(t["body"])), 1)

    def test_lemmas_named(self):
        built = C.build(self.task, self.record, self.side)
        names = [n for n, _ in built["lemmas"]]
        for n in ("tlift_pre", "tlift_post", "tlift_inv_0", "tlift_var_0", "tlift_eqn_Count4",
                  "tlift_close_Count4_0", "tlift_site_post_0", "tlift_site_inv0_1"):
            self.assertIn(n, names)

    @unittest.skipUnless(have("gcc"), "needs gcc")
    def test_differential_agrees_and_catches_a_wrong_body(self):
        d = Path(tempfile.mkdtemp())
        try:
            ok = C.run_differential(self.task, self.side, self.c.root, d / "ok", n=40)
            self.assertEqual(ok["verdict"], "agree")
            bad = json.loads(json.dumps(self.task))
            loop = C.body_loops(bad["body"])[0]
            hit = loop["body"][0]["if"]["then"][0]["assign"]         # counted := counted + 1
            hit[1]["args"][1] = {"int": 2}
            self.assertNotEqual(bad, self.task)
            res = C.run_differential(bad, self.side, self.c.root, d / "bad", n=40)
            self.assertEqual(res["verdict"], "disagree")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    @unittest.skipUnless(have("frama-c"), "needs frama-c")
    def test_wp_proves_the_lift_and_refuses_corruptions(self):
        d = Path(tempfile.mkdtemp())
        try:
            good = C.run_wp(self.side, C.build(self.task, self.record, self.side), self.c.root, d / "good", 2, 10)
            self.assertEqual(good["proved"], good["total"], good)
            # 1. a weaker postcondition (count from 1, not 0): tlift_post must fail
            t1 = json.loads(json.dumps(self.task))
            call = t1["ensures"][-1]["args"][1]["call"]
            call["args"][1] = {"int": 1}
            r1 = C.run_wp(self.side, C.build(t1, self.record, self.side), self.c.root, d / "post", 2, 5)
            self.assertNotEqual(r1["lemmas"]["tlift_post"], "valid")
            # 2. a spec function that adds 2 per hit: its equation must fail
            t2 = json.loads(json.dumps(self.task))
            t2["spec_funs"][0] = json.loads(json.dumps(t2["spec_funs"][0]).replace(
                '"then": {"int": 1}', '"then": {"int": 2}'))
            r2 = C.run_wp(self.side, C.build(t2, self.record, self.side), self.c.root, d / "eqn", 2, 5)
            self.assertNotEqual(r2["lemmas"]["tlift_eqn_Count4"], "valid")
            # 3. a call outside the function's domain (len(a) + 1): the site lemma must fail
            t3 = json.loads(json.dumps(self.task))
            call = t3["ensures"][-1]["args"][1]["call"]
            call["args"][2] = {"op": "+", "args": [call["args"][2], {"int": 1}]}
            r3 = C.run_wp(self.side, C.build(t3, self.record, self.side), self.c.root, d / "site", 2, 5)
            self.assertNotEqual(r3["lemmas"]["tlift_site_post_0"], "valid")
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
