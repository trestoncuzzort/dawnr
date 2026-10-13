import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Twelve findings of the GPT-6 Astra review of 2026-10-13, each reproduced before its fix (see the commit).


def test_unconsumed_definition_body_is_refused():
    import lift_lean as ll
    src = '''-- <vc-definitions>
def f (x : Int) : Int := x |> Int.neg
-- </vc-definitions>
theorem f_spec (x : Int) : f x = -x := by rfl
'''
    r = ll.render(src)
    assert r.refusal is not None, r.dafny


def test_nat_literal_subtraction_keeps_truncation():
    import lift_lean as ll
    src = '''-- <vc-definitions>
def f : Int := ((0 - 1 : Nat) : Int)
-- </vc-definitions>
theorem f_spec : f = 0 := by rfl
'''
    r = ll.render(src)
    assert r.refusal is not None or 'nat-sub-truncated' in r.rewrites, r.dafny


def test_typed_let_preserves_int_subtraction():
    import lift_lean as ll
    src = '''-- <vc-definitions>
def f (n : Nat) : Int :=
  let m : Int := n
  m - 1
-- </vc-definitions>
theorem f_spec (n : Nat) : f n = (n : Int) - 1 := by rfl
'''
    r = ll.render(src)
    assert r.refusal is not None or 'nat-sub-truncated' not in r.rewrites, r.dafny


def test_namespaces_do_not_overwrite_referenced_definition():
    import lift_lean as ll
    src = '''namespace A
def k : Int := 0
end A
namespace B
def k : Int := 1
end B
open A
-- <vc-definitions>
def f : Int := k
-- </vc-definitions>
theorem f_spec : f = 0 := by rfl
'''
    r = ll.render(src)
    assert r.refusal is not None or 'function k(): int\n{\n  1\n}' not in r.dafny, r.dafny


def test_theorem_proof_binder_becomes_requires():
    import lift_lean as ll
    src = '''-- <vc-definitions>
def f (x : Int) : Int := x
-- </vc-definitions>
theorem f_spec (x : Int) (h : x > 0) : f x > 0 := h
'''
    r = ll.render(src)
    assert r.refusal is not None or 'requires (x > 0)' in r.dafny, r.dafny


def test_int_bounded_quantifier_is_not_restricted_to_nat():
    import lift_lean as ll
    src = '''-- <vc-definitions>
def f (x : Int) : Int := 0
-- </vc-definitions>
theorem f_spec (x : Int) : ∀ i < x, f x = 0 := by
  intro i hi
  rfl
'''
    r = ll.render(src)
    assert r.refusal is not None or '0 <= i' not in r.dafny, r.dafny


def test_shadowed_parameter_is_not_the_current_call():
    import lift_lean as ll
    src = '''-- <vc-definitions>
def f (x : Int) : Int := x
-- </vc-definitions>
theorem f_spec (x : Int) : ∀ x : Int, f x = x := by
  intro x
  rfl
'''
    r = ll.render(src)
    assert r.refusal is not None and r.refusal[0] == 'spec-applies-program', r.dafny


def test_structure_parameter_is_not_erased_as_a_proof():
    import lift_lean as ll
    src = '''structure Payload where
  value : Int
-- <vc-definitions>
def f (p : Payload) : Int := 0
-- </vc-definitions>
theorem f_spec (p : Payload) : f p = 0 := by rfl
'''
    r = ll.render(src)
    assert r.refusal is not None and r.refusal[0] == 'datatype', r.dafny


def test_private_axiom_is_a_trust_hole():
    import lift_lean as ll
    src = '''private axiom bad : False
-- <vc-definitions>
def f : Int := 0
-- </vc-definitions>
theorem f_spec : f = 1 := False.elim bad
'''
    r = ll.render(src)
    assert r.refusal is not None and r.refusal[0] == 'trust-hole', r.dafny


def test_string_comment_marker_cannot_hide_sorry():
    import lift_lean as ll
    src = '''-- <vc-definitions>
def f : Int := 0
-- </vc-definitions>
theorem f_spec : f = 0 := by let s := "--"; sorry
'''
    r = ll.render(src)
    assert r.refusal is not None and r.refusal[0] == 'trust-hole', r.dafny


def test_identifier_normalization_does_not_merge_parameters():
    import lift_lean as ll
    src = '''-- <vc-definitions>
def f (x' x_p : Int) : Int := x' - x_p
-- </vc-definitions>
theorem f_spec (x' x_p : Int) : f x' x_p = x' - x_p := by rfl
'''
    r = ll.render(src)
    assert r.refusal is not None or 'method f(x_p: int, x_p: int)' not in r.dafny, r.dafny


def test_leading_zero_decimal_does_not_crash():
    import lift_lean as ll
    src = '''-- <vc-definitions>
def f : Int := 01
-- </vc-definitions>
theorem f_spec : f = 1 := by rfl
'''
    r = ll.render(src)
    assert r.refusal is not None or 'result := 1;' in r.dafny, r.dafny
