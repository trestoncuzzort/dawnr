import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Seven findings of the GPT-6 Astra review of 2026-10-13, each reproduced before its fix: loop states an enclosing
# branch rules out, quantifiers over sets without an order, break/continue in a trial iteration, self-calls checking
# requires, pow under the magnitude cap, an empty real sum read at the declared type, map order with signed zero.


def test_invariant_witness_preserves_enclosing_guard():
    from interp import invariant_witness
    def v(n): return {'var': n}
    def i(n): return {'int': n}
    def op(n, *args): return {'op': n, 'args': list(args)}
    r_nonneg = op('>=', v('r'), i(0))
    n_nonneg = op('>=', v('n'), i(0))
    loop = {'cond': op('<', v('r'), v('n')),
            'invariants': [r_nonneg, n_nonneg],
            'decreases': op('-', v('n'), v('r')),
            'body': [{'assign': ['r', op('+', v('r'), i(1))]}]}
    task = {'name': 'f', 'params': [{'name': 'n', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}],
            'requires': [], 'ensures': [r_nonneg],
            'body': [{'assign': ['r', i(0)]},
                     {'if': {'cond': n_nonneg,
                             'then': [{'while': loop}, {'assign': ['r', v('n')]}],
                             'else': [{'assign': ['r', op('neg', v('n'))]}]}}]}
    assert invariant_witness(task, loop, [r_nonneg],
                             [('n', 'int'), ('r', 'int')], limit=9) is None


def test_quantifier_over_set_of_pairs():
    from interp import ev, St
    def pair(n):
        return {'op': 'pair', 'args': [{'int': n}, {'int': 0}]}
    expr = {'forall': {'var': 'p',
                       'in': {'op': 'set', 'args': [pair(0), pair(1)]},
                       'body': {'bool': True}}}
    assert ev(expr, {}, {}, St()) is True


def test_invariant_witness_handles_break():
    from interp import invariant_witness
    true = {'bool': True}
    loop = {'cond': true, 'invariants': [true, true],
            'body': [{'break': True}]}
    task = {'name': 'f', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}],
            'requires': [], 'ensures': [true],
            'body': [{'assign': ['r', {'int': 0}]}, {'while': loop}]}
    assert invariant_witness(task, loop, [true], [('r', 'int')], limit=1) is None


def test_self_call_checks_requires():
    import unittest
    from interp import ev, funs_of, St, Undef
    n = {'var': 'n'}
    zero = {'int': 0}
    task = {'name': 'f', 'params': [{'name': 'n', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}],
            'requires': [{'op': '>=', 'args': [n, zero]}], 'ensures': [],
            'body': [{'if': {
                'cond': {'op': '>', 'args': [n, zero]},
                'then': [{'return': ['r', {'call': {'fun': 'f', 'args': [{'int': -1}]}}]}],
                'else': [{'return': ['r', zero]}]}}]}
    with unittest.TestCase().assertRaises(Undef):
        ev({'call': {'fun': 'f', 'args': [{'int': 1}]}},
           {}, funs_of(task, task['body']), St())


def test_power_obeys_magnitude_budget():
    import unittest
    from interp import ev, St, Budget
    expr = {'op': 'tostr', 'args': [
        {'op': 'pow', 'args': [{'int': 10}, {'int': 5000}]}]}
    with unittest.TestCase().assertRaises(Budget):
        ev(expr, {}, {}, St())


def test_empty_real_sum_has_no_zero_twin_witness():
    from interp import Reference
    zero = {'rat': [0, 1]}
    task = {'name': 'f',
            'params': [{'name': 's', 'type': {'seq': 'real'}}],
            'returns': [{'name': 'r', 'type': 'real'}],
            'requires': [{'op': '==', 'args': [
                {'op': 'len', 'args': [{'var': 's'}]}, {'int': 0}]}],
            'ensures': [{'op': '==', 'args': [{'var': 'r'}, zero]}],
            'body': [{'assign': ['r', {'op': 'sum', 'args': [{'var': 's'}]}]}]}
    ref = Reference(task, limit=1)
    assert ref.witness([{'assign': ['r', zero]}]) is None


def test_map_equality_is_extensional_for_signed_zero():
    from interp import MapV
    a = MapV.of([(0.0, 11), (-1.0, 22)])
    b = MapV.of([(-0.0, 11), (-1.0, 22)])
    assert all(a.get(k) == b.get(k) for k in (0.0, -1.0))
    assert a == b
