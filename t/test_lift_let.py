"""Dafny let-expressions through the lifter: parsed, substituted, checked (2026-09-26).

Before this, `lift_parse` refused every let-expression by name (`let-expression`),
and that was the largest single refusal of the 2026-09-26 lift: 432 of 1,886
vericoding-benchmark and HumanEval-Dafny programs. The Dafny reference manual defines
the construct (dafny.org/latest/DafnyRef/DafnyRef#sec-let-expression, section 9.31.7):
`var x := e; body` binds x to the value of e for the body only. Dafny expressions are
side-effect free and read one heap state, so the lifter lowers the plain form to
`body[x := e]`, capture-avoiding (the textbook rule, en.wikipedia.org/wiki/Lambda_calculus,
"capture-avoiding substitution"). The forms it cannot lower keep a refusal named for
what they are: `let-such-that` (`var x :| P; body`, a choice), `let-or-fail` (`:-`),
`let-pattern` (tuple or datatype destructuring) and `let-impure-rhs` (a method call on
the right, or a heap read the substitution would move under `old`).

No corpus is needed. The parser, the substitution and the classify/rewrite stages run
on text written here; the one end-to-end test runs dafny and is skipped without it.

    cd t && python3 -m unittest test_lift_let
    cd t && python3 test_lift_let.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lift_ast as A                                             # noqa: E402
import lift_check                                                # noqa: E402
import lift_classify                                             # noqa: E402
import lift_let                                                  # noqa: E402
import lift_parse as lp                                          # noqa: E402
import lift_resolve                                              # noqa: E402
import lift_rewrite                                              # noqa: E402
import lifter                                                    # noqa: E402
from verifiers import dafny as dafny_kernel                      # noqa: E402


def expr(text: str) -> A.Expr:
    """One Dafny expression, parsed by the lifter's own grammar."""
    tokens = lp._lex(text, 0, lp._compute_line_starts(text))
    parser = lp._Parser(tokens, text)
    e = parser.parse_expr()
    assert parser.at_eof(), f"trailing text after {text!r}"
    return e


def same(a, b) -> bool:
    """Structural equality ignoring rprint lines (the source cross-check's own rule)."""
    return lift_resolve._struct_eq(a, b)


def lift(text: str, method: str = "M"):
    """classify then rewrite one method of `text`: (task, record), or the Refusal."""
    module = lp.parse(text)
    m = next(d for d in lp.gradable_methods(module) if d.name == method)
    plan = lift_classify.classify(module, m)
    if isinstance(plan, A.Refusal):
        return plan
    result = lift_rewrite.rewrite(module, plan, "/nowhere/let_probe.dfy", "0" * 64)
    return result.task, result.record


# ---------------------------------------------------------------------- parse --

class LetParseTests(unittest.TestCase):
    def test_a_single_binding_parses_to_a_let_node(self):
        e = expr("var m: int := a + 1; r == m * m")
        self.assertIsInstance(e, A.LetExpr)
        self.assertEqual([b.name for b in e.binders], ["m"])
        self.assertEqual(e.binders[0].type.kind, "int")
        self.assertEqual(e.op, ":=")
        self.assertFalse(e.ghost)
        self.assertTrue(same(e.rhs, (expr("a + 1"),)))
        self.assertTrue(same(e.body, expr("r == m * m")))

    def test_multiple_bindings_keep_their_order(self):
        e = expr("var x: int, y: int := a, b + 1; x - y")
        self.assertEqual([b.name for b in e.binders], ["x", "y"])
        self.assertTrue(same(e.rhs, (expr("a"), expr("b + 1"))))

    def test_ghost_and_such_that_lets_keep_their_markers(self):
        g = expr("ghost var t: int := a; t + 1")
        self.assertTrue(g.ghost)
        s = expr("var k: int :| k > a; k")
        self.assertEqual(s.op, ":|")
        self.assertTrue(same(s.rhs, (expr("k > a"),)))

    def test_the_body_extends_as_far_right_as_it_can(self):
        e = expr("0 <= i ==> var x := s[i]; x > 0 && x < 9")
        self.assertIsInstance(e, A.Implies)
        self.assertIsInstance(e.right, A.LetExpr)
        self.assertTrue(same(e.right.body, expr("x > 0 && x < 9")))

    def test_a_let_whose_right_side_is_an_if_expression_parses(self):
        e = expr("var m := if a < b then a else b; m + 1")
        self.assertIsInstance(e.rhs[0], A.IfExpr)

    def test_a_tuple_pattern_is_refused_by_name(self):
        with self.assertRaises(lp.LiftParseError) as caught:
            expr("var (p: int, q: int) := t; p + q")
        self.assertEqual(caught.exception.reason, "let-pattern")

    def test_an_if_expression_that_ends_a_statement_is_not_a_hint_chain(self):
        # The parser used to read the statement's own ';' after an if-expression as a
        # statement sequenced inside an expression, and refused the whole file as a
        # let-expression: 61 of the 432 files of 2026-09-26, none of them a let.
        module = lp.parse("method M(a: int) returns (r: int)\n  ensures r >= 0\n{\n"
                          "  var z: int := if a > 0 then a else 0;\n"
                          "  r := z + if a > 0 then 0 else 1;\n}\n")
        m = lp.gradable_methods(module)[0]
        self.assertIsInstance(m.body[0].init[0], A.IfExpr)
        self.assertIsInstance(m.body[1], A.Assign)

    def test_a_statement_before_an_expression_is_refused_by_its_own_name(self):
        for body in ("Helper(x); x", "assert x > 0; x"):
            text = ("lemma Helper(x: int)\n  ensures true\n{\n}\n\n"
                    f"function F(x: int): int\n{{\n  {body}\n}}\n")
            with self.assertRaises(lp.LiftParseError) as caught:
                lp.parse(text)
            self.assertEqual(caught.exception.reason, "stmt-in-expression", body)

    def test_the_printer_round_trips_a_let(self):
        text = ("function Sq(n: int): int\n{\n  var m: int := n + 1; m * m\n}\n\n"
                "method M(a: int) returns (r: int)\n"
                "  ensures ghost var t: int, u: int := a, Sq(a); r == t + u\n"
                "{\n  r := a + Sq(a);\n}\n")
        first = lp.parse(text)
        again = lp.parse(lp.print_dafny(first))
        self.assertTrue(same(first.decls, again.decls))


# --------------------------------------------------------------- substitution --

class LetSubstitutionTests(unittest.TestCase):
    def test_a_single_binding_is_substituted(self):
        out = lift_let.expand(expr("var m := a + 1; m * m"))
        self.assertTrue(same(out.node, expr("(a + 1) * (a + 1)")))
        self.assertEqual(out.lets, 1)
        self.assertEqual(out.max_uses, 2)
        self.assertEqual(out.issues, [])

    def test_multiple_bindings_are_simultaneous(self):
        # Dafny evaluates every right-hand side before binding any name (measured on
        # dafny 4.11: `var x, y := y, x; x - y` at x=1, y=2 is 1), so a swap stays a swap.
        out = lift_let.expand(expr("var x, y := y, x; x - y"))
        self.assertTrue(same(out.node, expr("y - x")))

    def test_nested_lets_are_substituted_inside_out(self):
        out = lift_let.expand(expr("var a := n + 1; var b := a * a; b + a"))
        self.assertTrue(same(out.node, expr("(n + 1) * (n + 1) + (n + 1)")))
        self.assertEqual(out.lets, 2)

    def test_an_inner_binder_shadows_the_outer_one(self):
        out = lift_let.expand(expr("var x := 1; var x := x + 1; x * x"))
        self.assertTrue(same(out.node, expr("(1 + 1) * (1 + 1)")))

    def test_substitution_stops_at_a_quantifier_that_rebinds_the_name(self):
        out = lift_let.expand(expr("var k := n + 1; k < 3 && (forall k: int :: 0 <= k < 3 ==> s[k] > 0)"))
        self.assertTrue(same(out.node, expr("n + 1 < 3 && (forall k: int :: 0 <= k < 3 ==> s[k] > 0)")))

    def test_a_quantifier_that_would_capture_is_renamed(self):
        out = lift_let.expand(expr("var x := k + 1; forall k: int :: 0 <= k < n ==> s[k] < x"))
        q = out.node
        self.assertIsInstance(q, A.Quantifier)
        fresh = q.binders[0].name
        self.assertNotEqual(fresh, "k")
        self.assertTrue(same(q, expr(f"forall {fresh}: int :: 0 <= {fresh} < n ==> s[{fresh}] < k + 1")))
        self.assertEqual(lift_let.free_vars(q), {"k", "n", "s"})

    def test_the_growth_is_measured(self):
        # Inside out: b's body `b * b` becomes `(a + a) * (a + a)`, so a's right-hand
        # side is copied four times; max_uses counts the copies actually made.
        before = expr("var a := f(n, m); var b := a + a; b * b")
        out = lift_let.expand(before)
        self.assertEqual(out.max_uses, 4)
        self.assertTrue(same(out.node, expr("(f(n, m) + f(n, m)) * (f(n, m) + f(n, m))")))
        self.assertGreater(lift_let.size(out.node), lift_let.size(before))

    def test_a_substitution_that_would_blow_up_is_refused_not_built(self):
        # a1 := a0 + a0, a2 := a1 + a1, ...: every link doubles the copies of f(n).
        chain = "var a0 := f(n); " + "".join(f"var a{k} := a{k - 1} + a{k - 1}; " for k in range(1, 25))
        out = lift_let.expand(expr(chain + "a24"))
        self.assertIn("let-substitution-blowup", [i[1] for i in out.issues])
        self.assertLess(lift_let.size(out.node), lift_let.MAX_SUBSTITUTED_NODES)

    def test_a_let_without_a_let_is_returned_unchanged(self):
        e = expr("forall k: int :: 0 <= k < n ==> s[k] > 0")
        out = lift_let.expand(e)
        self.assertIs(out.node, e)
        self.assertEqual(out.lets, 0)

    def test_a_heap_read_moved_under_old_is_impure(self):
        # `ensures var v := a[0]; old(v) == v` verifies on dafny 4.11 after a[0] changes
        # (old has no effect on a bound value), and the substituted `old(a[0]) == a[0]`
        # does not: substitution would change the theorem, so it is refused by name.
        out = lift_let.expand(expr("var v := a[0]; old(v) == v"))
        self.assertEqual([i[1] for i in out.issues], ["let-impure-rhs"])
        self.assertIsInstance(out.node, A.LetExpr)

    def test_old_on_the_right_is_pure_and_is_substituted(self):
        out = lift_let.expand(expr("var v := old(a[0]); a[0] == v + 1"))
        self.assertEqual(out.issues, [])
        self.assertTrue(same(out.node, expr("a[0] == old(a[0]) + 1")))


# ------------------------------------------------------------ classify, rewrite --

SQ_WITH_LET = "function Sq(n: int): int\n{\n  var m: int := n + 1; m * m\n}\n\n"
SQ_WITHOUT = "function Sq(n: int): int\n{\n  (n + 1) * (n + 1)\n}\n\n"


def method(ensures: str, body: str = "r := (a + 1) * (a + 1);", head: str = "M(a: int) returns (r: int)") -> str:
    return f"method {head}\n  ensures {ensures}\n{{\n  {body}\n}}\n"


class LetClassifyRewriteTests(unittest.TestCase):
    def assert_same_lift(self, with_let: str, without: str, keys=("requires", "ensures", "body", "spec_funs")):
        got = lift(with_let)
        self.assertIsInstance(got, tuple, got)
        want = lift(without)
        self.assertIsInstance(want, tuple, want)
        for key in keys:
            self.assertEqual(got[0].get(key), want[0].get(key), key)
        return got

    def test_a_let_in_an_ensures_clause_lifts_by_substitution(self):
        task, record = self.assert_same_lift(method("var m: int := a + 1; r == m * m"),
                                             method("r == (a + 1) * (a + 1)"))
        self.assertIn("let-substituted", [w.rule for w in record.rewrites])

    def test_a_ghost_let_in_an_ensures_clause_lifts(self):
        self.assert_same_lift(method("ghost var t: int := a * 2; r == t + 1", "r := a * 2 + 1;"),
                              method("r == a * 2 + 1", "r := a * 2 + 1;"))

    def test_a_let_in_a_function_body_lifts_into_the_spec_fun(self):
        self.assert_same_lift(SQ_WITH_LET + method("r == Sq(a)"), SQ_WITHOUT + method("r == Sq(a)"))

    def test_multiple_and_nested_bindings_in_a_loop_invariant(self):
        loop = ("var i: int := 0;\n  r := 0;\n  while i < n\n"
                "    invariant {inv}\n    decreases n - i\n  {{\n    r := r + 2;\n    i := i + 1;\n  }}")
        head = "M(n: int) returns (r: int)\n  requires n >= 0"
        self.assert_same_lift(
            method("r == 2 * n", loop.format(inv="var lo: int, hi: int := 0, n; var w: int := 2 * i; lo <= i <= hi && r == w"), head),
            method("r == 2 * n", loop.format(inv="0 <= i <= n && r == 2 * i"), head))

    def test_a_such_that_let_is_refused_by_name(self):
        got = lift(method("var k: int :| k == a; r == k", "r := a;"))
        self.assertIsInstance(got, A.Refusal)
        self.assertEqual(got.reason, "let-such-that")

    def test_a_method_call_on_the_right_is_refused_as_impure(self):
        helper = "method Helper(x: int) returns (y: int)\n  ensures y == x\n{\n  y := x;\n}\n\n"
        got = lift(helper + method("var h: int := Helper(a); r == h", "r := a;"))
        self.assertIsInstance(got, A.Refusal)
        self.assertEqual(got.reason, "let-impure-rhs")

    def test_a_used_binder_of_a_type_t_lacks_is_refused_by_that_types_name(self):
        # A let binder is a local: once substituted its type is gone, and a real
        # literal in its right-hand side reached the rewrite as an unmapped node.
        got = lift(method("var h: real := 1.5; h > 1.0 ==> r == a", "r := a;"))
        self.assertIsInstance(got, A.Refusal)
        self.assertEqual((got.reason, got.token), ("real", "h"))

    def test_an_unused_binder_does_not_refuse(self):
        # `var x: real := 0.0; r == a` is `r == a`: the unused value is never read.
        task, _record = self.assert_same_lift(method("var x: real := 0.0; r == a", "r := a;"),
                                              method("r == a", "r := a;"))

    def test_a_let_outside_the_methods_closure_does_not_refuse_it(self):
        other = "function Other(n: int): int\n{\n  var k: int :| k == n; k\n}\n\n"
        got = lift(other + method("r == (a + 1) * (a + 1)"))
        self.assertIsInstance(got, tuple, got)

    def test_the_sidecar_records_the_substitution(self):
        task, record = lift(SQ_WITH_LET + method("var s: int := Sq(a + 1); r == s + s", "r := 2 * Sq(a + 1);"))
        census = record.let_substitution
        self.assertEqual(census["lets"], 2)
        self.assertEqual(census["max_uses"], 2)
        self.assertGreater(census["nodes_after"], census["nodes_before"])
        saved = lifter._record_to_dict(record)
        self.assertEqual(saved["let_substitution"], census)
        self.assertEqual(lifter._record_from_dict(saved).let_substitution, census)

    def test_a_let_free_program_carries_no_let_census(self):
        task, record = lift(method("r == (a + 1) * (a + 1)"))
        self.assertEqual(record.let_substitution, {})
        self.assertNotIn("let_substitution", lifter._record_to_dict(record))


# ------------------------------------------------ the source cross-check, checker --

class LetSourceAndCheckerTests(unittest.TestCase):
    def test_the_source_cross_check_keeps_a_lets_semicolon(self):
        # lift_resolve.check_against_source drops the optional ';' after a clause before
        # parsing the source's own clauses; a let's ';' is not optional.
        source = method("var m := a + 1; r == m * m;")
        rprint = method("var m: int := a + 1; r == m * m")
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        path = tmp / "let_source.dfy"
        path.write_text(source, encoding="utf-8")
        m = lp.gradable_methods(lp.parse(rprint))[0]
        warnings, refusal = lift_resolve.check_against_source(path, m)
        self.assertIsNone(refusal)
        self.assertEqual(warnings, [])

    def test_the_checker_prints_a_let_with_its_binders_renamed(self):
        text = lift_check._print_expr(expr("var m: int := a + 1; r == m * m"), {"m": "m_v", "a": "a_t"})
        self.assertEqual(text, "(var m_v: int := (a_t + 1); (r == (m_v * m_v)))")

    def test_the_checker_leaves_an_untyped_binder_untyped(self):
        text = lift_check._print_expr(expr("var m := a; m"), {})
        self.assertEqual(text, "(var m := a; m)")

    def test_the_checker_widens_a_nat_binder_to_int(self):
        # The lemma compares values; `nat` would add a subset-type obligation the lemma's
        # free variables cannot always discharge, and the lift keeps no such bound either.
        text = lift_check._print_expr(expr("var k: nat := i - 1; var s: seq<nat> := t; k + |s|"), {})
        self.assertEqual(text, "(var k: int := (i - 1); (var s: seq<int> := t; (k + |s|)))")


@unittest.skipUnless(dafny_kernel.DAFNY, "dafny is not installed here")
class LetEndToEndTests(unittest.TestCase):
    PROGRAM = """function Sq(n: int): int
{
  var m := n + 1; m * m
}

method SumSq(a: int, n: int) returns (r: int)
  requires n >= 0
  ensures var s := Sq(a); r == n * s
{
  var i := 0;
  r := 0;
  while i < n
    invariant var lo, hi := 0, n; lo <= i <= hi
    invariant r == i * Sq(a)
  {
    r := r + Sq(a);
    i := i + 1;
  }
}
"""

    def test_a_program_with_lets_lifts_and_its_checker_verifies(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        path = tmp / "let_e2e.dfy"
        path.write_text(self.PROGRAM, encoding="utf-8")
        outcome = lifter.lift_file(path, out_dir=tmp / "out", timeout_s=180.0, force=True)
        self.assertIsNone(outcome.parse_refusal)
        [mo] = outcome.methods
        self.assertIsNone(mo.refusal, mo.refusal)
        self.assertTrue(mo.checked)
        verdicts = mo.record.checker_verdicts
        # L_fun_sq, L_req, L_ens, L_inv_0: each source clause, lets and all, against its
        # substituted lift, proved equivalent by dafny (L_dec_0: the loop's measure).
        self.assertEqual(set(verdicts), {"L_fun_sq", "L_req", "L_ens", "L_inv_0", "L_dec_0"}, verdicts)
        self.assertEqual({v for v in verdicts.values()}, {"verified"}, verdicts)
        # The differential run compiles to C#; where dotnet is missing it reads
        # arm-unavailable, which is not a disagreement. A disagreement reads bad=N.
        self.assertFalse((mo.record.differential_verdict or "").startswith("bad="),
                         mo.record.differential_verdict)
        self.assertEqual(mo.record.let_substitution["lets"], 3)


def run(slow: bool = False) -> None:
    """test_lifter.py's contract: raise AssertionError on a failure."""
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        raise AssertionError(f"test_lift_let: {len(result.failures)} failure(s), {len(result.errors)} error(s)")


if __name__ == "__main__":
    unittest.main()
