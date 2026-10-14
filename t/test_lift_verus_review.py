import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Fifteen findings of the GPT-6 Astra review of 2026-10-13 on the Verus lifter, each reproduced before its fix: a returns clause is an ensures on the result; a narrowing machine-integer cast is refused; a machine-typed quantifier keeps both bounds; a const keeps its executable semantics; a user-defined min/max/abs wins over the built-in; a hole inside a proof block is a trust hole; a branch's bindings end with the branch; a quantifier's binder shadows an outer rename; a let binder is translated like its references; identifier translation is injective; a for range reads its end once; pop of an empty Vec is a no-op; Vec::get is refused as an Option; spec functions reached only through the decreases are emitted; a unit parameter is a named refusal.


def test_returns_clause_is_not_discarded():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'fn f() -> (r: u8) ensures true, returns 7u8, { 7 } }')
    r = lv.render(src, target='f')
    assert r.refusal is not None or 'ensures (r == 7)' in r.dafny


def test_narrowing_cast_is_not_identity():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'fn f(n: u16) -> (r: u8) ensures r == n as u8, '
           '{ #[verifier::truncate] let v = n as u8; v } }')
    r = lv.render(src, target='f')
    assert r.refusal is not None or 'ensures (r == n)' not in r.dafny


def test_machine_quantifier_keeps_its_domain():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'fn f() -> (r: bool) '
           'ensures r == (exists|x: u8| x > 255), { false } }')
    r = lv.render(src, target='f')
    bad = '(exists x: int :: ((0 <= x) && (x > 255)))'
    assert r.refusal is not None or bad not in r.dafny


def test_constant_division_does_not_change_in_specs():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'const C: i32 = -3 / 2; '
           'fn f() -> (r: i32) ensures r == C, { -1 } }')
    r = lv.render(src, target='f')
    assert r.refusal is not None or 'ensures (r == (-3 / 2))' not in r.dafny


def test_user_defined_min_is_not_builtin_min():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'spec fn min(x: int, y: int) -> int { x + y } '
           'fn f() -> (r: u8) ensures r == min(2, 3), { 5 } }')
    r = lv.render(src, target='f')
    assert r.refusal is not None or 'function min(' in r.dafny


def test_named_target_checks_its_own_proof_holes():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'fn f() -> (r: bool) ensures false, '
           '{ proof { assume(false); } true } }')
    r = lv.render(src, target='f')
    assert r.refusal is not None and r.refusal[0] == 'trust-hole'


def test_branch_shadow_does_not_escape():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'fn f(x: i32) -> (r: i32) ensures r == x, '
           '{ if x > 0 { let x = 0; } x } }')
    r = lv.render(src, target='f')
    assert r.refusal is not None or '  r := x;' in r.dafny


def test_quantifier_shadows_outer_rename():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'proof fn f(x: int) -> (r: bool) ensures r, '
           '{ let x = 0; exists|x: int| x == 1 } }')
    r = lv.render(src, target='f')
    assert r.refusal is not None or 'exists x: int :: (x_1 == 1)' not in r.dafny


def test_spec_let_binder_is_renamed_consistently():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'spec fn h(n: int) -> int { let seq = n; seq } '
           'fn f(n: i32) -> (r: i32) ensures r == h(n as int), { n } }')
    r = lv.render(src, target='f')
    assert r.refusal is not None or '(var seq_v := n; seq_v)' in r.dafny


def test_identifier_translation_avoids_collisions():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'fn f(seq: i32, seq_v: i32) -> (r: i32) '
           'ensures r == seq, { seq } }')
    r = lv.render(src, target='f')
    bad = 'method f(seq_v: int, seq_v: int)'
    assert r.refusal is not None or bad not in r.dafny


def test_for_range_freezes_its_upper_bound():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'fn f() -> (r: u8) ensures r == 2, { '
           'let mut end: u8 = 2; let mut count: u8 = 0; '
           'for i in 0..end invariant count == i, i <= 2, '
           '{ end = 0; count += 1; } count } }')
    r = lv.render(src, target='f')
    assert r.refusal is not None or 'while i < end' not in r.dafny


def test_pop_of_empty_vector_is_not_negative_slice():
    import re
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'fn f() -> (r: Vec<i32>) ensures r.len() == 0, '
           '{ let mut v: Vec<i32> = Vec::new(); v.pop(); v } }')
    r = lv.render(src, target='f')
    if r.refusal is None:
        assert 'v[..|v| - 1]' not in r.dafny or re.search(r'\bif\b', r.dafny)


def test_vec_get_is_not_unconditional_indexing():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'fn f(a: Vec<i32>) -> (r: bool) '
           'requires a.len() == 0, ensures r, '
           '{ a.get(0) == a.get(1) } }')
    r = lv.render(src, target='f')
    assert r.refusal is not None or 'r := (a[0] == a[1]);' not in r.dafny


def test_target_decreases_dependencies_are_emitted():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'spec fn measure(n: int) -> int { n } '
           'fn f(n: u8) -> (r: u8) ensures r == n, '
           'decreases measure(n as int), { n } }')
    r = lv.render(src, target='f')
    assert r.refusal is not None or 'function measure(' in r.dafny


def test_unit_parameter_is_refused_without_crashing():
    import lift_verus as lv
    src = ('use vstd::prelude::*; verus! { '
           'fn f(x: ()) -> (r: bool) ensures r, { true } }')
    r = lv.render(src, target='f')
    assert r.refusal is not None
