import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Eighteen findings of the GPT-6 Astra review of 2026-10-13 on the Dafny lifter's parser and printer, each reproduced before its fix: a wildcard-only match keeps its subject; a named function result is kept and printed; explicit type arguments at a call are a call; an unterminated block comment and an unterminated type characteristic are parse failures; the arrow kind of a function type survives; angle brackets nest inside an allocation; a guarded while may carry loop specifications; a forall statement keeps its ensures; a bare collection type prints; multiset displays, multidimensional indices, ghost locals, such-that assignments, labels, ghost methods and skipped declarations print as read; an empty bitvector summary is no witness.


def test_wildcard_match_preserves_subject_obligations():
    import lift_parse as lp
    source = 'method M(x: int) ensures (match 1 / x { case _ => true }) {}'
    try:
        module = lp.parse(source)
    except lp.LiftParseError as exc:
        assert exc.reason != 'parse-failure'
        return
    assert not isinstance(module.decls[0].specs[0].expr, lp.BoolLit), 'The division obligation was erased'


def test_named_function_result_keeps_its_binding():
    import lift_parse as lp
    source = 'function F(x: int): (r: int) ensures r == x { x }'
    try:
        module = lp.parse(source)
    except lp.LiftParseError as exc:
        assert exc.reason != 'parse-failure'
        return
    output = lp.print_dafny(module)
    assert '(r: int)' in output, output


def test_explicit_type_arguments_do_not_become_comparisons():
    import lift_parse as lp
    source = 'function P<T>(x: T): bool { true }\nmethod M(x: int) ensures P<int>(x) {}'
    try:
        module = lp.parse(source)
    except lp.LiftParseError as exc:
        assert exc.reason != 'parse-failure'
        return
    assert isinstance(module.decls[1].specs[0].expr, lp.Call)


def test_unterminated_comment_is_not_a_successful_parse():
    import lift_parse as lp
    try:
        lp.parse('method M() ensures true {} /* unfinished')
    except lp.LiftParseError:
        return
    raise AssertionError('Accepted an unterminated block comment')


def test_unterminated_type_characteristic_terminates():
    import lift_parse as lp
    from unittest.mock import patch
    original = lp._Parser.advance
    calls = 0
    def bounded_advance(self):
        nonlocal calls
        calls += 1
        assert calls < 50, 'Parser is looping at EOF'
        return original(self)
    with patch.object(lp._Parser, 'advance', bounded_advance):
        try:
            lp.parse('method M<T(0')
        except lp.LiftParseError:
            return
    raise AssertionError('Accepted an unterminated type characteristic')


def test_function_type_arrow_is_preserved():
    import lift_parse as lp
    source = 'method M(f: int ~> int) ensures true {}'
    try:
        module = lp.parse(source)
    except lp.LiftParseError as exc:
        assert exc.reason != 'parse-failure'
        return
    assert '~>' in lp.print_dafny(module)


def test_allocation_type_argument_comma_is_not_an_rhs_separator():
    import lift_parse as lp
    module = lp.parse('method M() ensures true { var a := new map<int, bool>[1]; }')
    init = module.decls[0].body[0].init
    assert len(init) == 1
    assert isinstance(init[0], lp.NewRhs)
    assert init[0].text == 'new map<int, bool>[1]'


def test_guarded_while_accepts_loop_specs():
    import lift_parse as lp
    source = 'method M() ensures true { var x: int := 1; while invariant 0 <= x decreases x { case x > 0 => x := x - 1; } }'
    module = lp.parse(source)
    assert isinstance(module.decls[0].body[1], lp.WhileCaseStmt)


def test_forall_statement_postcondition_survives():
    import lift_parse as lp
    source = 'method M() ensures true { forall i: int | 0 <= i < 1 ensures i == 0 {} }'
    try:
        module = lp.parse(source)
    except lp.LiftParseError as exc:
        assert exc.reason != 'parse-failure'
        return
    assert lp.print_dafny(module).count('ensures') == 2


def test_bare_collection_type_prints_without_crashing():
    import lift_parse as lp
    module = lp.parse('predicate P(s: seq) { s == [0] }')
    output = lp.print_dafny(module)
    assert 's: seq' in output


def test_multiset_display_remains_a_multiset():
    import lift_parse as lp
    module = lp.parse('function F(): int { |multiset{1, 1}| }')
    reparsed = lp.parse(lp.print_dafny(module))
    assert reparsed.decls[0].body.arg.multiset


def test_multidimensional_index_prints_multiple_indices():
    import lift_parse as lp
    source = 'method M(a: array2<int>) ensures true { var x: int := a[0, 0]; }'
    output = lp.print_dafny(lp.parse(source))
    assert 'a[0, 0]' in output, output


def test_ghost_local_uses_dafny_keyword_order():
    import lift_parse as lp
    source = 'method M() ensures true { ghost var x: int := 0; }'
    output = lp.print_dafny(lp.parse(source))
    assert 'ghost var x: int' in output, output


def test_such_that_assignment_does_not_declare_a_new_variable():
    import lift_parse as lp
    source = 'method M() returns (x: int) ensures x == 1 { x :| x == 1; }'
    output = lp.print_dafny(lp.parse(source))
    assert '\n  x :|' in output, output


def test_statement_label_round_trips():
    import lift_parse as lp
    source = 'method M() ensures true { label L: { break L; } }'
    lp.parse(lp.print_dafny(lp.parse(source)))


def test_ghost_method_modifier_survives_printing():
    import lift_parse as lp
    module = lp.parse('ghost method G() ensures true {}')
    reparsed = lp.parse(lp.print_dafny(module))
    assert reparsed.decls[0].ghost


def test_skipped_type_declaration_keeps_its_name():
    import lift_parse as lp
    source = 'type T = int\nmethod M(x: T) ensures true {}'
    output = lp.print_dafny(lp.parse(source))
    assert 'type T = int' in output, output


def test_empty_bitvector_summary_does_not_relabel_errors():
    import lift_parse as lp
    source = '/*\n// bitvector types in use:\n*/\nmethod M() ensures true { var x: int := ; }'
    try:
        lp.parse(source)
    except lp.LiftParseError as exc:
        assert exc.reason == 'parse-failure', exc.reason
        return
    raise AssertionError('Expected a parse error')
