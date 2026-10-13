import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Eight findings of the GPT-6 Astra review of 2026-10-13 on the F* lowering, each reproduced before its fix: dead and overwritten partial values keep their definedness obligations (an env that records what the generated text reads unconditionally), a pair projection keeps the discarded component's obligations, an ensures-level certificate must concern an evaluated subexpression, a chain's aliases are frozen before the loop that rebinds them, the source loop measure is asserted non-negative under the guard, a quantifier's compound index gets a ranged domain fact, real actuals use the real renderer, a parameterless method takes unit.


def test_unused_initializer_keeps_definedness():
    import lower_fstar as lf
    task = {
        'name': 'dead_div',
        'params': [{'name': 'x', 'type': 'int'}],
        'returns': [{'name': 'r', 'type': 'int'}],
        'requires': [],
        'ensures': [{'op': '==', 'args': [{'var': 'r'}, {'int': 0}]}],
        'body': [
            {'var': {'name': 'unused', 'type': 'int', 'init': {'op': 'div', 'args': [{'int': 1}, {'int': 0}]}}},
            {'assign': ['r', {'int': 0}]}
        ]
    }
    try:
        src = lf.gen_fun(lf.Ctx(task), task, task['body'])
    except NotImplementedError:
        return
    assert ' / 0' in src, 'Reached division by zero disappeared from the generated function'


def test_projection_does_not_discard_partial_component():
    import lower_fstar as lf
    task = {'name': 'projection', 'params': [], 'returns': [{'name': 'r', 'type': 'int'}]}
    expr = {'op': 'fst', 'args': [{'op': 'pair', 'args': [
        {'int': 7}, {'op': 'div', 'args': [{'int': 1}, {'int': 0}]}
    ]}]}
    try:
        rendered = lf.Ctx(task).zx(expr, {}, {})
    except NotImplementedError:
        return
    assert ' / 0' in rendered, rendered


def test_unreachable_ensures_expression_cannot_refute():
    import lower_fstar as lf
    bad = {'op': 'div', 'args': [{'int': 1}, {'int': 0}]}
    task = {
        'name': 'guarded_post',
        'params': [{'name': 'x', 'type': 'int'}],
        'returns': [{'name': 'r', 'type': 'int'}],
        'requires': [],
        'ensures': [
            {'op': '==', 'args': [{'var': 'r'}, {'int': 0}]},
            {'op': 'or', 'args': [{'bool': True}, {'op': '==', 'args': [bad, {'int': 0}]}]}
        ],
        'body': [{'assign': ['r', {'int': 0}]}]
    }
    witness = {'x': 0, 'r': 0, '_kind': 'undefined', '_site': 'ensures', '_expr': bad, '_real': 'no value'}
    cert = lf._certificate(lf.Ctx(task), task, task['body'], witness)
    assert cert is None, cert


def test_chain_preserves_saved_sequence_value():
    import lower_fstar as lf
    def I(n): return {'int': n}
    def V(n): return {'var': n}
    def O(op, *args): return {'op': op, 'args': list(args)}
    def S(e): return O('seq', e)
    def loop(offset):
        return {
            'cond': O('<', V('i'), I(1)),
            'invariants': [O('<=', I(0), V('i')), O('<=', V('i'), I(1)),
                           O('==', V('s'), S(O('+', V('i'), I(offset))))],
            'decreases': O('-', I(1), V('i')),
            'body': [{'assign': ['s', S(I(offset + 1))]},
                     {'assign': ['i', O('+', V('i'), I(1))]}]
        }
    p1 = [{'var': {'name': 'i', 'type': 'int', 'init': I(0)}},
          {'var': {'name': 's', 'type': 'seq', 'init': S(I(0))}}]
    p2 = [{'var': {'name': 'saved', 'type': 'seq', 'init': V('s')}},
          {'assign': ['i', I(0)]}]
    suffix = [{'assign': ['r', V('saved')]}]
    task = {'name': 'snapshot', 'params': [{'name': 'x', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'seq'}], 'requires': [],
            'ensures': [O('==', V('r'), S(I(2)))]}
    try:
        src = lf.gen_loop_chain(lf.Ctx(task), task, [(p1, loop(0)), (p2, loop(1))], suffix)
    except NotImplementedError:
        return
    assert not src.rstrip().endswith('\n  s'), 'Returned the rebound state instead of its saved value:\n' + src


@pytest.mark.skipif(shutil.which("fstar.exe") is None, reason="fstar.exe is not installed")
def test_negative_source_decreases_is_not_verified():
    import subprocess
    import tempfile
    from pathlib import Path
    import lower_fstar as lf
    def I(n): return {'int': n}
    def V(n): return {'var': n}
    def O(op, *args): return {'op': op, 'args': list(args)}
    task = {'name': 'metric', 'params': [{'name': 'x', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [O('==', V('r'), I(0))]}
    prefix = [{'var': {'name': 'i', 'type': 'int', 'init': I(0)}}]
    w = {'cond': O('<', V('i'), I(1)),
         'invariants': [O('<=', I(0), V('i')), O('<=', V('i'), I(1))],
         'decreases': {'ite': {'cond': {'bool': True}, 'then': O('-', I(-1), V('i')), 'else': I(0)}},
         'body': [{'assign': ['i', O('+', V('i'), I(1))]}]}
    try:
        src = lf.gen_loop(lf.Ctx(task), task, prefix, w, [{'assign': ['r', I(0)]}])
    except NotImplementedError:
        return
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'Metric.fst'
        path.write_text('module Metric\nmodule Seq = FStar.Seq\n' + src)
        result = subprocess.run(['fstar.exe', '--z3rlimit', '50', str(path)], capture_output=True, text=True, timeout=60)
        assert result.returncode != 0, 'Kernel accepted a loop whose source measure is negative under its guard'


def test_quantifier_compound_index_has_no_free_bound_name():
    import re
    import lower_fstar as lf
    task = {'name': 'quant_index',
            'params': [{'name': 's', 'type': 'seq'}, {'name': 'n', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'bool'}]}
    q = {'exists': {'var': 'i', 'lo': {'int': 0}, 'hi': {'var': 'n'},
         'body': {'op': '==', 'args': [
             {'op': 'at', 'args': [{'var': 's'}, {'op': '+', 'args': [{'var': 'i'}, {'int': 1}]}]},
             {'int': 0}]}}}
    cx = lf.Ctx(task)
    try:
        cx.bx(q, {}, {})
    except NotImplementedError:
        return
    requires = cx.extra_defs[-1].split('(requires', 1)[1].split('(ensures', 1)[0]
    assert re.search(r'\bi\b', requires) is None, requires


def test_real_method_argument_uses_real_renderer():
    import lower_fstar as lf
    method = {'name': 'half_arg', 'params': [{'name': 'a', 'type': 'real'}],
              'returns': [{'name': 'b', 'type': 'real'}]}
    task = {'name': 'real_caller', 'params': [],
            'returns': [{'name': 'r', 'type': 'real'}], 'methods': [method]}
    try:
        text = lf.Ctx(task).call({'call': {'fun': 'half_arg', 'args': [{'rat': [1, 2]}]}}, {}, {})
    except NotImplementedError:
        return
    assert text == '(half_arg 0.5R)', text


def test_parameterless_method_call_applies_unit():
    import lower_fstar as lf
    method = {'name': 'seven', 'params': [], 'returns': [{'name': 'b', 'type': 'int'}]}
    task = {'name': 'caller', 'params': [{'name': 'x', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}], 'methods': [method]}
    assert lf.param_binders(method)[1] == '()'
    try:
        text = lf.Ctx(task).call({'call': {'fun': 'seven', 'args': []}}, {}, {})
    except NotImplementedError:
        return
    assert text == '(seven ())', text
