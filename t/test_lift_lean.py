"""t/test_lift_lean.py: unit tests for the Lean 4 front end (t/lift_lean.py), one per
construct it renders and one per refusal it names, plus the equivalence harness's shape
(t/lift_check_lean.py) where it can be checked without running Lean.

    python3 t/test_lift_lean.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lift_check_lean as lcl
import lift_lean as ll


def prepost(pre: str, sig: str, body: str, post: str, preamble: str = "", helpers: str = "") -> str:
    """A vericoding-shaped file: `sig` is the binders of `solve` (without the proof), `post`
    the postcondition body over those binders and `result`."""
    names = " ".join(n for grp in __import__("re").findall(r"\(([^:]+):", sig) for n in grp.split())
    return ("import Mathlib\n-- <vc-preamble>\n" + preamble + "\n"
            f"@[reducible, simp]\ndef solve_precond {sig} : Prop :=\n  {pre}\n-- </vc-preamble>\n\n"
            "-- <vc-helpers>\n" + helpers + "\n-- </vc-helpers>\n\n"
            f"-- <vc-definitions>\ndef solve {sig} (h_precond : solve_precond {names}) : Int :=\n  {body}\n"
            "-- </vc-definitions>\n\n-- <vc-theorems>\n@[reducible, simp]\n"
            f"def solve_postcond {sig} (result : Int) (h_precond : solve_precond {names}) : Prop :=\n  {post}\n\n"
            f"theorem solve_spec_satisfied {sig} (h_precond : solve_precond {names}) :\n"
            f"    solve_postcond {names} (solve {names} h_precond) h_precond := by\n  simp\n"
            "-- </vc-theorems>\n")


def spec_thm(defn: str, thm: str, preamble: str = "") -> str:
    return ("import Mathlib\n-- <vc-preamble>\n" + preamble + "\n-- </vc-preamble>\n\n-- <vc-helpers>\n-- </vc-helpers>\n\n"
            "-- <vc-definitions>\n" + defn + "\n-- </vc-definitions>\n\n-- <vc-theorems>\n" + thm +
            " :=\nby\n  simp\n-- </vc-theorems>\n")


class PrePost(unittest.TestCase):
    def test_basic(self):
        r = ll.render(prepost("n ≥ 1", "(n : Int)", "n + 1", "result = n + 1 ∧ result ≥ 2"))
        self.assertIsNone(r.refusal)
        self.assertIn("method solve(n: int) returns (result: int)", r.dafny)
        self.assertIn("requires (n >= 1)", r.dafny)
        self.assertIn("ensures ((result == (n + 1)) && (result >= 2))", r.dafny)
        self.assertIn("result := (n + 1);", r.dafny)
        self.assertEqual(r.shape, "pre-post")

    def test_preamble_def_with_proof_argument_dropped(self):
        pre = "def Valid (n : Int) : Prop :=\n  n > 0\n\ndef F (n : Int) (h : Valid n) : Int :=\n  n * 2\n"
        r = ll.render(prepost("Valid n", "(n : Int)", "F n h_precond", "result = F n h_precond", preamble=pre))
        self.assertIsNone(r.refusal, r.refusal)
        self.assertIn("function F(n: int): int", r.dafny)
        self.assertIn("predicate Valid(n: int)", r.dafny)
        self.assertIn("ensures (result == F(n))", r.dafny)

    def test_let_layout(self):
        pre = "def G (n m : Int) : Int :=\n  let k := n % m\n  if k < 2 then k else 0\n"
        r = ll.render(prepost("m > 0", "(n m : Int)", "G n m", "result = G n m", preamble=pre))
        self.assertIn("(var k := (n % m); (if (k < 2) then k else 0))", r.dafny)

    def test_nat_subtraction_truncated(self):
        r = ll.render(prepost("True", "(n : Nat)", "0", "result = ((n - 1 : Nat) : Int)"))
        self.assertIn("(if n >= 1 then n - 1 else 0)", r.dafny)
        self.assertIn("nat-sub-truncated", r.rewrites)

    def test_int_subtraction_plain(self):
        r = ll.render(prepost("True", "(n : Int)", "n - 1", "result = n - 1"))
        self.assertIn("result := (n - 1);", r.dafny)

    def test_array_param_and_index(self):
        r = ll.render(prepost("a.size > 0", "(a : Array Int)", "a[0]!", "result = a[0]!"))
        self.assertIn("method solve(a: seq<int>)", r.dafny)
        self.assertIn("requires (|a| > 0)", r.dafny)
        self.assertIn("ensures (result == a[0])", r.dafny)

    def test_nat_elements_bound(self):
        r = ll.render(prepost("a.length > 0", "(a : List Nat)", "0", "result ≥ 0"))
        self.assertIn("forall i: int :: 0 <= i < |a| ==> a[i] >= 0", r.dafny)

    def test_forall_binder_predicate(self):
        r = ll.render(prepost("True", "(a : Array Int)", "0", "∀ i < a.size, a[i]! ≤ result"))
        self.assertIn("(forall i: int :: (0 <= i && i < |a|) ==> (a[i] <= result))", r.dafny)

    def test_forall_untyped_index_binder_is_nat(self):
        r = ll.render(prepost("True", "(a : Array Int)", "0", "∀ i, i < a.size → a[i]! ≤ result"))
        self.assertIn("forall i: int :: (0 <= i) ==>", r.dafny)

    def test_exists(self):
        r = ll.render(prepost("True", "(a : Array Int)", "0", "∃ i : Nat, i < a.size ∧ a[i]! = result"))
        self.assertIn("(exists i: int :: (0 <= i) && ", r.dafny)

    def test_min_max_decide_ite(self):
        r = ll.render(prepost("True", "(a b : Int)", "if decide (a ≤ b) then a else b", "result = min a b"))
        self.assertIn("(if a <= b then a else b)", r.dafny)
        self.assertIn("result := (if ((a <= b)) then a else b);", r.dafny)

    def test_toNat(self):
        r = ll.render(prepost("True", "(a : Int)", "0", "result = (a.toNat : Int)"))
        self.assertIn("(if a >= 0 then a else 0)", r.dafny)


class SpecTheorem(unittest.TestCase):
    def test_hypotheses_and_conclusion(self):
        r = ll.render(spec_thm("def Abs (x : Int) : Int :=\nif x ≥ 0 then x else -x",
                               "theorem Abs_spec (x : Int) :\nx > -10 →\n(x ≥ 0 → Abs x = x) ∧ (x < 0 → x + Abs x = 0)"))
        self.assertIsNone(r.refusal, r.refusal)
        self.assertEqual(r.shape, "spec-theorem")
        self.assertIn("requires (x > (-10))", r.dafny)
        self.assertIn("ensures ((((x >= 0) ==> (result == x))) && (((x < 0) ==> ((x + result) == 0))))", r.dafny)

    def test_let_result(self):
        r = ll.render(spec_thm("def Twice (x : Int) : Int :=\n2 * x",
                               "theorem Twice_spec (x : Int) :\nlet r := Twice x\nr = x + x"))
        self.assertIn("returns (r: int)", r.dafny)
        self.assertIn("ensures (r == (x + x))", r.dafny)

    def test_extra_binder_refused(self):
        r = ll.render(spec_thm("def F (x : Int) : Int :=\nx",
                               "theorem F_spec (x : Int) (y : Int) :\nF x = x"))
        self.assertEqual(r.refusal[0], "theorem-binders")

    def test_program_on_other_arguments_refused(self):
        r = ll.render(spec_thm("def F (x : Int) : Int :=\nx",
                               "theorem F_spec (x : Int) :\nF (x + 1) = x + 1"))
        self.assertEqual(r.refusal[0], "spec-applies-program")


class Refusals(unittest.TestCase):
    def refusal(self, **kw):
        base = dict(pre="True", sig="(n : Int)", body="n", post="result = n")
        base.update(kw)
        r = ll.render(prepost(**base))
        return r.refusal[0] if r.refusal else None

    def test_sorry(self):
        self.assertEqual(self.refusal(body="sorry"), "trust-hole")

    def test_axiom(self):
        self.assertEqual(self.refusal(preamble="axiom g : Int → Int"), "trust-hole")

    def test_instance_override(self):
        self.assertEqual(self.refusal(helpers="local instance : LE Int where\n  le := fun _ _ => True"), "trust-hole")

    def test_lambda(self):
        self.assertEqual(self.refusal(post="result = (List.range 3).foldl (fun a b => a + b) 0"), "higher-order")

    def test_string(self):
        # feature 6 (2026-09-27): a String parameter renders as Dafny's
        # `string` (row 28 lifts it as code points); `String.Pos` and the
        # library members with no Dafny expression still refuse by name
        self.assertIsNone(self.refusal(sig="(s : String)", body="0", post="result = 0"))
        self.assertEqual(self.refusal(sig="(s : String)", body="(s.get 0).toNat", post="result ≥ 0"),
                         "string-pos")
        self.assertEqual(self.refusal(sig="(s : String)", body="(s.splitOn \" \").length",
                                      post="result ≥ 0"), "string-lib")

    def test_float(self):
        self.assertEqual(self.refusal(sig="(x : Float)", body="0", post="result = 0"), "float")

    def test_tuple(self):
        self.assertEqual(self.refusal(sig="(p : Int × Int)", body="0", post="result = 0"), "tuple")

    def test_pow(self):
        self.assertEqual(self.refusal(post="result = n ^ 2"), "pow")

    def test_recursion_in_program(self):
        self.assertEqual(self.refusal(body="solve n h_precond"), "recursion")

    def test_hoare_triple(self):
        text = ("-- <vc-definitions>\ndef f (x : Int) : Id Int :=\n  pure x\n-- </vc-definitions>\n"
                "-- <vc-theorems>\ntheorem f_spec (x : Int) :\n    ⦃⌜True⌝⦄ f x ⦃⇓r => ⌜r = x⌝⦄ := by\n  simp\n"
                "-- </vc-theorems>\n")
        self.assertEqual(ll.render(text).refusal[0], "hoare-triple")


class Harness(unittest.TestCase):
    def test_prepost_harness_uses_the_source_definitions(self):
        src = prepost("n ≥ 1", "(n : Int)", "n + 1", "result = n + 1")
        task = {"t": 1, "name": "solve", "params": [{"name": "n", "type": "int"}],
                "returns": [{"name": "result", "type": "int"}],
                "requires": [{"op": ">=", "args": [{"var": "n"}, {"int": 1}]}],
                "ensures": [{"op": "==", "args": [{"var": "result"}, {"op": "+", "args": [{"var": "n"}, {"int": 1}]}]}],
                "body": [{"assign": ["result", {"op": "+", "args": [{"var": "n"}, {"int": 1}]}]}]}
        text, lemmas = lcl.build(src, task)
        self.assertEqual(lemmas, ["t_eq_requires", "t_eq_ensures"])
        self.assertIn("def solve_precond (n : Int) : Prop :=\n  n ≥ 1", text)
        self.assertIn("(solve_precond n) ↔ t_lift_pre n", text)
        self.assertIn("(solve_postcond n result h) ↔ t_lift_post n result", text)
        self.assertIn("#print axioms t_eq_ensures", text)
        self.assertNotIn("import Mathlib", text)

    def test_views(self):
        self.assertEqual(lcl._view("a", ll.LType("seq", "Array Int", ll.LType("int", "Int"))), "a.toList")
        self.assertEqual(lcl._view("n", ll.LType("nat", "Nat")), "((n : Nat) : Int)")

    def test_program_substitution(self):
        self.assertEqual(lcl._substitute_program("(f x) = x ∧ f x > 0", "f", ["x"], "result"),
                         "result = x ∧ result > 0")
        with self.assertRaises(lcl.NoHarness):
            lcl._substitute_program("f (x + 1) = x", "f", ["x"], "result")


if __name__ == "__main__":
    unittest.main()
