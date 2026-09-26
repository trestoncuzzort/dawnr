"""t/test_lift_verus.py: unit tests for the Verus front end (t/lift_verus.py), one per
construct it renders and one per refusal it names, plus the equivalence harness's shape
(t/lift_check_verus.py) where it can be checked without running Verus.

    python3 t/test_lift_verus.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lift_check_verus as lcv
import lift_verus as lv


def wrap(spec: str, code: str = "{\n    0\n}", preamble: str = "", helpers: str = "") -> str:
    return ("use vstd::prelude::*;\n// <vc-preamble>\nverus! {\n" + preamble + "\n// </vc-preamble>\n"
            "// <vc-helpers>\n" + helpers + "\n// </vc-helpers>\n// <vc-spec>\n" + spec +
            "\n// </vc-spec>\n// <vc-code>\n" + code + "\n// </vc-code>\n}\nfn main() {}\n")


def render(spec, code="{\n    0\n}", preamble="", helpers=""):
    return lv.render(wrap(spec, code, preamble, helpers))


def refusal(spec, code="{\n    0\n}", preamble="", helpers=""):
    r = render(spec, code, preamble, helpers)
    return r.refusal[0] if r.refusal else None


class Types(unittest.TestCase):
    def test_signed_scalar_is_int(self):
        r = render("fn f(n: i8) -> (r: i8)\n    ensures r == n,", "{\n    n\n}")
        self.assertIn("method f(n: int) returns (r: int)", r.dafny)

    def test_unsigned_scalar_is_nat(self):
        r = render("fn f(n: usize) -> (r: usize)\n    ensures r == n,", "{\n    n\n}")
        self.assertIn("method f(n: nat) returns (r: nat)", r.dafny)

    def test_vec_is_seq_and_unsigned_elements_bound(self):
        r = render("fn f(a: &Vec<u32>) -> (r: u32)\n    requires a.len() > 0,\n    ensures r == a[0],",
                   "{\n    a[0]\n}")
        self.assertIn("a: seq<int>", r.dafny)
        self.assertIn("forall i: int :: 0 <= i < |a| ==> a[i] >= 0", r.dafny)
        self.assertIn("unsigned-elements-bound", r.rewrites)

    def test_slice_and_string(self):
        r = render("fn f(a: &[i32], s: &str) -> (r: bool)\n    ensures r == (a.len() == s@.len()),",
                   "{\n    a.len() == s.unicode_len()\n}")
        self.assertEqual(r.refusal[0], "std-method")   # unicode_len is not read; the types were
        r = render("fn f(s: Vec<char>) -> (r: usize)\n    ensures r == s.len(),", "{\n    s.len()\n}")
        self.assertIn("s: seq<char>", r.dafny)

    def test_float_refused(self):
        self.assertEqual(refusal("fn f(a: Vec<f32>) -> (r: f32)\n    ensures true,"), "float")

    def test_tuple_return_refused(self):
        self.assertEqual(refusal("fn f(a: i8) -> (r: (i8, i8))\n    ensures r.0 == a,"), "tuple")

    def test_mut_ref_refused(self):
        self.assertEqual(refusal("fn f(a: &mut Vec<i32>)\n    ensures a.len() == old(a).len(),", "{\n}"),
                         "mut-ref-param")

    def test_option_refused(self):
        self.assertEqual(refusal("fn f(a: i8) -> (r: Option<i8>)\n    ensures true,"), "datatype")


class Expressions(unittest.TestCase):
    def spec(self, ens, params="n: i32", ret="i32"):
        return render(f"fn f({params}) -> (r: {ret})\n    ensures {ens},", "{\n    0\n}")

    def test_precedence_and_over_compare(self):
        r = self.spec("r >= 0 && r <= n")
        self.assertIn("((r >= 0) && (r <= n))", r.dafny)

    def test_implication_is_looser_than_and(self):
        r = self.spec("n > 0 ==> r > 0 && r < n")
        self.assertIn("((n > 0) ==> ((r > 0) && (r < n)))", r.dafny)

    def test_chain(self):
        r = self.spec("0 <= r < n")
        self.assertIn("(0 <= r < n)", r.dafny)

    def test_forall_bounded(self):
        r = self.spec("forall|i: int| 0 <= i < a.len() ==> a[i] <= r", "a: Vec<i32>")
        self.assertIn("(forall i: int :: ((0 <= i < |a|) ==> (a[i] <= r)))", r.dafny)

    def test_view_and_cast_dropped(self):
        r = self.spec("r as int == a@[0] as int", "a: Vec<i32>")
        self.assertIn("(r == a[0])", r.dafny)
        self.assertIn("machine-int-widened", r.rewrites)

    def test_identity_map_dropped(self):
        r = render("fn f(a: Vec<i8>) -> (r: i8)\n    ensures r == g(a@.map(|i: int, x: i8| x as int)),",
                   preamble="spec fn g(s: Seq<int>) -> int { s.len() as int }")
        self.assertIsNone(r.refusal)
        self.assertIn("ensures (r == g(a))", r.dafny)

    def test_other_closure_refused(self):
        r = render("fn f(a: Vec<i8>) -> (r: i8)\n    ensures r == g(a@.map(|i: int, x: i8| x + 1)),",
                   preamble="spec fn g(s: Seq<int>) -> int { s.len() as int }")
        self.assertEqual(r.refusal[0], "higher-order")

    def test_extensional_equality(self):
        r = self.spec("r@ =~= a@", "a: Vec<i32>", "Vec<i32>")
        self.assertIn("(r == a)", r.dafny)

    def test_seq_methods(self):
        r = self.spec("r@ == a@.subrange(1, a.len() as int) + a@.take(1)", "a: Vec<i32>", "Vec<i32>")
        self.assertIn("a[1..|a|]", r.dafny)
        self.assertIn("a[..1]", r.dafny)

    def test_ghost_division_is_euclidean(self):
        r = self.spec("r == n / 2")
        self.assertIn("(n / 2)", r.dafny)

    def test_if_expression(self):
        r = self.spec("r == if n > 0 { n } else { -n }")
        self.assertIn("(if (n > 0) then n else -n)", r.dafny)

    def test_bullets(self):
        r = self.spec("&&& r > 0 &&& r < 10")
        self.assertIn("((r > 0)) && ((r < 10))", r.dafny)

    def test_char_literal_cast(self):
        r = self.spec("r as int == (c as int) - ('a' as int)", "c: char")
        self.assertIn("('a' as int)", r.dafny)

    def test_spec_fn_closure_rendered(self):
        r = render("fn f(n: i32) -> (r: i32)\n    ensures ok(n, r),",
                   preamble="spec fn ok(n: int, r: int) -> bool { r == dbl(n) }\n"
                            "spec fn dbl(n: int) -> int { 2 * n }\nspec fn unused(n: int) -> int { n }")
        self.assertIn("predicate ok(n: int, r: int)", r.dafny)
        self.assertIn("function dbl(n: int): int", r.dafny)
        self.assertNotIn("unused", r.dafny)

    def test_let_in_spec_fn(self):
        r = render("fn f(n: i32) -> (r: i32)\n    ensures r == h(n),",
                   preamble="spec fn h(n: int) -> int { let k = n + 1; k * k }")
        self.assertIn("(var k := (n + 1); (k * k))", r.dafny)

    def test_reserved_identifier_renamed(self):
        r = self.spec("r == seq", "seq: i32")
        self.assertIn("seq_v: int", r.dafny)

    def test_bitwise_refused(self):
        self.assertEqual(self.spec("r == n & 1").refusal[0], "bitvector")

    def test_match_refused(self):
        self.assertEqual(self.spec("r == match n { 0 => 1, _ => 2 }").refusal[0], "match")

    def test_multiset_refused(self):
        self.assertEqual(self.spec("r@.to_multiset() == a@.to_multiset()", "a: Vec<i32>", "Vec<i32>").refusal[0],
                         "multiset")


class Statements(unittest.TestCase):
    SPEC = "fn f(a: &Vec<i32>) -> (r: i32)\n    requires a.len() > 0,\n    ensures r >= a[0],"

    def test_while_with_invariants(self):
        r = render(self.SPEC, "{\n    let mut m = a[0];\n    let mut i: usize = 1;\n    while i < a.len()\n"
                              "        invariant 1 <= i <= a.len(), m >= a[0],\n        decreases a.len() - i\n"
                              "    {\n        if a[i] > m { m = a[i]; }\n        i += 1;\n    }\n    m\n}")
        self.assertIsNone(r.refusal)
        self.assertIn("while (i < |a|)", r.dafny)
        self.assertIn("invariant (1 <= i <= |a|)", r.dafny)
        self.assertIn("decreases (|a| - i)", r.dafny)
        self.assertIn("i := (i + 1);", r.dafny)
        self.assertIn("r := m;", r.dafny)

    def test_for_range_becomes_while(self):
        r = render(self.SPEC, "{\n    let mut m = a[0];\n    for i in 0..a.len()\n        invariant m >= a[0],\n"
                              "    {\n        if a[i] > m { m = a[i]; }\n    }\n    m\n}")
        self.assertIn("var i := 0;", r.dafny)
        self.assertIn("while i < |a|", r.dafny)
        self.assertIn("invariant (0 <= i <= |a|)", r.dafny)
        self.assertIn("for-range-as-while", r.rewrites)

    def test_push_and_new(self):
        r = render("fn f(n: i32) -> (r: Vec<i32>)\n    ensures r.len() == 1,",
                   "{\n    let mut v = Vec::new();\n    v.push(n);\n    v\n}")
        self.assertIn("var v := [];", r.dafny)
        self.assertIn("v := v + [n];", r.dafny)

    def test_shadowing_let_renamed(self):
        r = render("fn f(n: i32) -> (result: i32)\n    ensures result == n,",
                   "{\n    let result = n;\n    result\n}")
        self.assertIn("var result_1 := n;", r.dafny)
        self.assertIn("result := result_1;", r.dafny)

    def test_proof_code_dropped(self):
        r = render("fn f(n: i32) -> (r: i32)\n    ensures r == n,",
                   "{\n    proof { assert(n == n); }\n    assert(n == n) by { };\n    lemma_x(n);\n    n\n}",
                   helpers="proof fn lemma_x(n: i32) {}")
        self.assertIsNone(r.refusal)
        self.assertNotIn("assert", r.dafny)
        self.assertNotIn("lemma_x", r.dafny)

    def test_return(self):
        r = render("fn f(n: i32) -> (r: i32)\n    ensures r >= n,",
                   "{\n    if n > 0 {\n        return n;\n    }\n    n + 1\n}")
        self.assertIn("r := n;", r.dafny)
        self.assertIn("return;", r.dafny)

    def test_exec_signed_division_written_out(self):
        r = render("fn f(n: i8) -> (r: i8)\n    ensures true,", "{\n    n / 7\n}")
        self.assertIn("(if n >= 0 then n / 7 else -((-n) / 7))", r.dafny)

    def test_exec_unsigned_division_direct(self):
        r = render("fn f(n: u8) -> (r: u8)\n    ensures true,", "{\n    n / 7\n}")
        self.assertIn("r := (n / 7);", r.dafny)

    def test_exec_signed_division_by_variable_refused(self):
        self.assertEqual(refusal("fn f(n: i8, d: i8) -> (r: i8)\n    requires d > 0,\n    ensures true,",
                                 "{\n    n / d\n}"), "exec-signed-div")

    def test_loop_refused(self):
        self.assertEqual(refusal("fn f(n: i8) -> (r: i8)\n    ensures true,", "{\n    loop { break; }\n    n\n}"),
                         "loop-exit")

    def test_helper_exec_call_refused(self):
        self.assertEqual(refusal("fn f(n: i8) -> (r: i8)\n    ensures true,", "{\n    g(n)\n}",
                                 helpers="fn g(n: i8) -> i8 { n }"), "calls-other-method")


class FileLevel(unittest.TestCase):
    def test_trust_holes(self):
        self.assertEqual(refusal("fn f(n: i8) -> (r: i8)\n    ensures r == n,", "{\n    assume(false);\n    n\n}"),
                         "trust-hole")
        self.assertEqual(refusal("fn f(n: i8) -> (r: i8)\n    ensures r == n,", "{\n    n\n}",
                                 helpers="#[verifier::external_body]\nfn g() {}"), "trust-hole")

    def test_hole_in_comment_is_not_a_hole(self):
        r = render("fn f(n: i8) -> (r: i8)\n    ensures r == n,", "{\n    // assume(false) was here\n    n\n}")
        self.assertIsNone(r.refusal)

    def test_target_is_the_exec_fn_after_a_spec_fn(self):
        text = wrap("spec fn g(n: int) -> int { n }\nfn f(n: i8) -> (r: i8)\n    ensures r == g(n as int),",
                    "{\n    n\n}")
        self.assertEqual(lv.target_name(text), "f")

    def test_no_ensures_refused(self):
        self.assertEqual(refusal("fn f(n: i8) -> (r: i8)", "{\n    n\n}"), "zero-ensures")

    def test_source_text_kept_for_the_harness(self):
        r = render("fn f(a: Vec<i8>) -> (r: i8)\n    requires a.len() > 0,\n    ensures r == a[0],",
                   "{\n    a[0]\n}")
        fn = r.file.exec_fns["f"]
        self.assertEqual(fn.requires_src, ["a . len ( ) > 0"])
        self.assertEqual(fn.ensures_src, ["r == a [ 0 ]"])
        self.assertEqual([p.type_src for p in fn.params], ["Vec < i8 >"])


class Harness(unittest.TestCase):
    """The equivalence harness's text, built from a hand-written lifted task (no Verus run)."""
    SRC = wrap("fn f(a: Vec<i8>) -> (r: i8)\n    requires a.len() > 0,\n    ensures r == g(a@.map(|i: int, x: i8| x as int)),",
               "{\n    a[0]\n}", preamble="spec fn g(s: Seq<int>) -> int { s[0] }")
    TASK = {"t": 1, "name": "f", "params": [{"name": "a", "type": "seq"}],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [{"op": ">", "args": [{"op": "len", "args": [{"var": "a"}]}, {"int": 0}]}],
            "ensures": [{"op": "==", "args": [{"var": "r"}, {"call": {"fun": "g", "args": [{"var": "a"}]}}]}],
            "spec_funs": [{"name": "g", "params": [{"name": "s", "type": "seq"}], "result": "int",
                           "decreases": {"int": 0}, "body": {"op": "at", "args": [{"var": "s"}, {"int": 0}]}}],
            "body": [{"assign": ["r", {"op": "at", "args": [{"var": "a"}, {"int": 0}]}]}]}

    def test_views_and_source_clauses(self):
        text, lemmas = lcv.build(self.SRC, self.TASK, {})
        self.assertEqual(lemmas[:2], ["t_eq_requires", "t_eq_ensures"])
        self.assertIn("spec fn g ( s : Seq < int > ) -> int { s [ 0 ] }", text)      # the source, verbatim
        self.assertIn("spec fn t_lift_g(", text)                                         # the lift, prefixed
        self.assertIn("proof fn t_eq_requires(a: Vec < i8 >)", text)
        self.assertIn("t_lift_pre(t_view_i8(a@))", text)
        self.assertIn("t_lift_post(t_view_i8(a@), (r as int))", text)
        self.assertIn("broadcast use t_view_i8_len, t_view_i8_index, t_view_i8_eq, t_view_i8_sub, t_view_i8_add, t_view_i8_push;", text)
        # the source's own closure map is bridged to the view by extensionality
        self.assertTrue(re.search(r"assert\(a @ \. map \( \| i : int , x : i8 \| x as int \) =~= t_view_i8\(a@\)\);",
                                  text))

    def test_view_ranges(self):
        v = lcv.Views()
        self.assertEqual(v.view("x", lv.VType("int", "i8")), "(x as int)")
        fam = v.family(lv.VType("nat", "usize"))
        self.assertEqual(fam, "t_view_usize")
        self.assertIn("0 <= (x as int)", v.fams["usize"])
        self.assertNotIn("<= None", v.fams["usize"])


if __name__ == "__main__":
    unittest.main()
