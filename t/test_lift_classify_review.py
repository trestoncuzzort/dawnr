import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Nine findings of the GPT-6 Astra review of 2026-10-13, each reproduced before its fix: a residual range survives
# the last pinned binder, substitution avoids capture, a nat binder keeps its floor, a tuple carries its components
# issues, a disjunction states no bound, a set union is no sequence range, a binder cannot bound itself, an
# attribute string hides no axiom, a string is not an assume statement.


def test_eliminated_binder_keeps_residual_range():
    from lift_classify import bound_quantifier
    from lift_ast import Quantifier, Param, Chain, Ident, IntLit, BoolLit, NaryBool
    q = Quantifier(line=1, kind='exists', attrs=(),
        binders=(Param(line=1, name='i', type=None),),
        range=NaryBool(1, '&&', (
            Chain(1, ('==',), (Ident(1, 'i'), IntLit(1, 0))),
            BoolLit(1, False))), body=BoolLit(1, True))
    got = bound_quantifier(q)
    def evaluate(e):
        if isinstance(e, BoolLit):
            return e.value
        assert isinstance(e, NaryBool) and e.op == '&&'
        return all(evaluate(a) for a in e.args)
    assert got is None or not evaluate(got['body'])


def test_substitution_avoids_quantifier_capture():
    from lift_classify import _subst_ast
    from lift_ast import Quantifier, Param, Chain, Ident, IntLit
    inner = Quantifier(line=1, kind='exists', attrs=(),
        binders=(Param(line=1, name='y', type=None),),
        range=Chain(1, ('<=', '<'),
                    (IntLit(1, 0), Ident(1, 'y'), IntLit(1, 2))),
        body=Chain(1, ('!=',), (Ident(1, 'x'), Ident(1, 'y'))))
    substituted = _subst_ast(inner, 'x', Ident(1, 'y'))
    assert substituted.binders[0].name != 'y', 'free y was captured'


def test_nat_quantifier_excludes_negative_witnesses():
    from types import SimpleNamespace
    from lift_classify import bound_quantifier
    from lift_ast import Quantifier, Param, Chain, Ident, IntLit, BoolLit
    q = Quantifier(line=1, kind='exists', attrs=(),
        binders=(Param(line=1, name='i', type=SimpleNamespace(kind='nat')),),
        range=Chain(1, ('<=', '<'),
                    (IntLit(1, -1), Ident(1, 'i'), IntLit(1, 0))),
        body=BoolLit(1, True))
    got = bound_quantifier(q)
    wrong = ([('i', IntLit(1, -1), IntLit(1, 0), None)], BoolLit(1, True))
    assert got is None or (got['binders'], got['body']) != wrong


def test_tuple_parameter_does_not_bypass_nat_sequence_refusal():
    from types import SimpleNamespace as T
    from lift_classify import _type_issue
    seq_nat = T(kind='seq', args=(T(kind='nat'),))
    pair = T(kind='tuple', args=(seq_nat, T(kind='int')))
    assert _type_issue(seq_nat) == 'nat-seq-elements'
    assert _type_issue(pair) is not None


def test_disjunctive_requires_does_not_prove_char_cast_safe():
    from types import SimpleNamespace
    from lift_classify import _cast_bounds_env, _char_cast_safe
    from lift_ast import RequiresClause, NaryBool, Chain, Ident, IntLit
    x = Ident(1, 'x')
    requirement = NaryBool(1, '||', (
        Chain(1, ('==',), (x, IntLit(1, -1))),
        Chain(1, ('<=', '<='), (IntLit(1, 0), x, IntLit(1, 10)))))
    root = SimpleNamespace(specs=(RequiresClause(line=1, expr=requirement),))
    env = _cast_bounds_env(root, set())
    assert not _char_cast_safe(x, set(), set(), env)


def test_set_union_is_not_a_sequence_quantifier_range():
    from lift_classify import _bind_binders
    from lift_ast import Binary, Chain, Ident
    union = Binary(1, '+', Ident(1, 'A'), Ident(1, 'B'))
    guard = Chain(1, ('in',), (Ident(1, 'x'), union))
    got = _bind_binders(['x'], [guard], None, set(),
                        set_lookup=lambda name: name in {'A', 'B'})
    assert got is None


def test_binder_cannot_depend_on_itself():
    from types import SimpleNamespace
    from lift_classify import _order_binders
    from lift_ast import Binary, Ident, IntLit
    bound = {'i': (IntLit(1, 0),
                   Binary(1, '+', Ident(1, 'i'), IntLit(1, 1)), None)}
    assert _order_binders((SimpleNamespace(name='i'),), bound) is None


def test_attribute_string_cannot_hide_lemma_axiom():
    from types import SimpleNamespace
    from lift_classify import _lemma_is_axiomatised
    lemma = SimpleNamespace(text='lemma {:note "("} {:axiom} L() ensures false;')
    assert _lemma_is_axiomatised(lemma)


def test_assume_inside_string_is_not_a_statement():
    from types import SimpleNamespace
    from lift_classify import _lemma_has_assume
    lemma = SimpleNamespace(text='lemma L() { assert "assume" == "assume"; }')
    assert not _lemma_has_assume(lemma)
