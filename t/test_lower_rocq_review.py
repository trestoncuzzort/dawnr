import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Fourteen findings of the GPT-6 Astra review of 2026-10-13, each reproduced before its fix (see the commit).
# The early-return test compiles its probe with coqc and skips where there is none.


def test_pair_sequence_components_use_extensional_equality():
    import lower_rocq as lr
    cx = lr.Ctx({'name': 'probe', 'params': [], 'returns': [{'name': 'r', 'type': 'int'}]})
    def pair_with_empty_fill(value):
        return {'op': 'pair', 'args': [
            {'op': 'fill', 'args': [{'int': 0}, {'int': value}]},
            {'int': 0}]}
    expr = {'op': '!=', 'args': [pair_with_empty_fill(0), pair_with_empty_fill(1)]}
    rendered = cx.prop(expr, {}, {})
    assert 'forall ' in rendered, 'Sequence equality inside a pair must ignore out-of-range function values: ' + rendered


def test_quantifier_bound_does_not_capture_outer_parameter():
    import lower_rocq as lr
    cx = lr.Ctx({'name': 'probe', 'params': [{'name': 'n', 'type': 'int'}],
                 'returns': [{'name': 'r', 'type': 'int'}]})
    expr = {'forall': {'var': 'n', 'lo': {'int': 0}, 'hi': {'var': 'n'},
                       'body': {'bool': False}}}
    rendered = cx.prop(expr, {}, {})
    assert '0 <= n < n' not in rendered, 'The upper bound must refer to the outer n: ' + rendered


def test_any_all_render_in_specification_position():
    import lower_rocq as lr
    cx = lr.Ctx({'name': 'probe', 'params': [{'name': 's', 'type': 'seq'}],
                 'returns': [{'name': 'r', 'type': 'int'}]})
    comp = {'comp': {'var': 'x', 'seq': {'var': 's'}, 'cond': {'bool': True},
                     'body': {'op': '>=', 'args': [{'var': 'x'}, {'int': 0}]}}}
    for op in ('all', 'any'):
        rendered = cx.prop({'op': op, 'args': [comp]}, {}, {})
        assert isinstance(rendered, str) and rendered


def test_match_preserves_unrelated_return_substitution():
    from unittest.mock import patch
    import lower_rocq as lr
    cx = lr.Ctx({'name': 'probe', 'params': [{'name': 'd', 'type': {'datatype': 'D'}}],
                 'returns': [{'name': 'value', 'type': 'int'}]})
    expr = {'match': {'scrutinee': {'var': 'd'}, 'arms': [
        {'ctor': 'C', 'binders': ['v'],
         'body': {'op': '==', 'args': [{'var': 'value'}, {'int': 7}]}}]}}
    # Supply the metadata for D = C(int); exercise the real substitution logic.
    with patch.object(cx, '_arm_types', return_value={'v': 'int'}), \
         patch.object(lr, '_rctor', return_value='C'):
        rendered = cx.prop(expr, {'value': '7'}, {})
    assert 'value' not in rendered, 'The unrelated return substitution was lost: ' + rendered


def test_sequence_pattern_definedness_uses_bound_length_projection():
    from unittest.mock import patch
    import lower_rocq as lr
    cx = lr.Ctx({'name': 'probe', 'params': [{'name': 'box', 'type': {'datatype': 'Box'}}],
                 'returns': [{'name': 'r', 'type': 'int'}]})
    xs = {'var': 'xs'}
    arm_body = {'ite': {
        'cond': {'op': '>', 'args': [{'op': 'len', 'args': [xs]}, {'int': 0}]},
        'then': {'op': 'at', 'args': [xs, {'int': 0}]},
        'else': {'int': 0}}}
    expr = {'match': {'scrutinee': {'var': 'box'}, 'arms': [
        {'ctor': 'Hold', 'binders': ['xs'], 'body': arm_body}]}}
    obligations = []
    # Supply the metadata for Box = Hold(seq).
    with patch.object(cx, '_arm_types', return_value={'xs': 'seq'}), \
         patch.object(lr, '_rctor', return_value='Hold'):
        cx.defs(expr, [], [], obligations, {}, {})
    assert len(obligations) == 1
    assert '(snd xs)' in obligations[0][2], obligations
    assert 'xs_len' not in obligations[0][2], obligations


def test_recursive_definedness_is_not_discarded():
    import sys
    sys.path.insert(0, 't')
    import lower_rocq as r
    I = lambda n: {'int': n}
    V = lambda n: {'var': n}
    O = lambda op, *a: {'op': op, 'args': list(a)}
    body = [{'if': {
        'cond': O('>', V('n'), I(0)),
        'then': [{'assign': ['r', {'call': {'fun': 'rec_undef', 'args': [O('-', V('n'), I(1))]}}]}],
        'else': [{'assign': ['r', O('div', I(1), I(0))]}]
    }}]
    task = {'t': 1, 'name': 'rec_undef',
            'params': [{'name': 'n', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}],
            'requires': [O('>=', V('n'), I(0))],
            'ensures': [O('==', I(0), I(0))],
            'decreases': V('n'), 'body': body}
    src = r.lower_v1(task, body)
    assert 'Lemma rec_undef_def_' in src, 'reachable division-by-zero obligation was discarded'


def test_return_before_loop_preserves_early_exit():
    import shutil, unittest
    if not shutil.which('coqc'):
        raise unittest.SkipTest('needs coqc')
    import sys, subprocess, tempfile
    from pathlib import Path
    sys.path.insert(0, 't')
    import lower_rocq as r
    prefix = [{'if': {'cond': {'var': 'b'},
                      'then': [{'return': ['r', {'int': 1}]}], 'else': []}}]
    w = {'cond': {'bool': False}, 'decreases': {'int': 0},
         'invariants': [], 'body': []}
    suffix = [{'assign': ['r', {'int': 2}]}]
    body = prefix + [{'while': w}] + suffix
    task = {'t': 1, 'name': 'early',
            'params': [{'name': 'b', 'type': 'bool'}],
            'returns': [{'name': 'r', 'type': 'int'}],
            'requires': [], 'ensures': [{'bool': True}], 'body': body}
    src = r.gen_loop(r.Ctx(task), prefix, w, suffix, [0])
    definitions = src.split('Lemma early_loop_spec', 1)[0]
    probe = ('From Stdlib Require Import ZArith Bool.\nOpen Scope Z_scope.\n'
             + definitions + '\nGoal early_t true = 1. Proof. reflexivity. Qed.\n')
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'Probe.v'
        path.write_text(probe)
        result = subprocess.run(['coqc', str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr


def test_lemma_call_requires_is_an_obligation():
    import sys
    sys.path.insert(0, 't')
    import lower_rocq as r
    positive = {'op': '>', 'args': [{'var': 'x'}, {'int': 0}]}
    call = {'lemma': {'name': 'positive', 'args': [{'int': 0}]}}
    task = {'t': 1, 'name': 'bad_lemma_call', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}],
            'requires': [], 'ensures': [{'bool': True}],
            'lemmas': [{'name': 'positive',
                        'params': [{'name': 'x', 'type': 'int'}],
                        'requires': [positive], 'ensures': [positive], 'body': []}],
            'body': [call, {'assign': ['r', {'int': 0}]}]}
    cx = r.Ctx(task)
    cx.lemma_sites = []
    obligations = []
    r.exec_straight(cx, [call], {'r': '0'}, {}, [], [], obligations)
    assert obligations, 'positive(0) must produce an unsatisfiable call-precondition obligation'


def test_value_certificate_rejects_out_of_domain_input():
    import sys
    sys.path.insert(0, 't')
    import lower_rocq as r
    task = {'t': 0, 'name': 'nonnegative_identity',
            'params': [{'name': 'n', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}],
            'requires': [{'op': '>=', 'args': [{'var': 'n'}, {'int': 0}]}],
            'ensures': [{'op': '>=', 'args': [{'var': 'r'}, {'int': 0}]}],
            'body': [{'assign': ['r', {'var': 'n'}]}]}
    witness = {'n': -1, '_kind': 'value', '_real': -1, '_twin': -1}
    assert r._v0_cert(task, task['body'], witness) is None


def test_undefined_certificate_rejects_foreign_expression():
    import sys
    sys.path.insert(0, 't')
    import lower_rocq as r
    task = {'t': 1, 'name': 'total_zero',
            'params': [{'name': 'n', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [{'op': '==', 'args': [{'var': 'r'}, {'int': 0}]}],
            'body': [{'assign': ['r', {'int': 0}]}]}
    foreign = {'op': '==', 'args': [
        {'op': 'div', 'args': [{'int': 1}, {'int': 0}]}, {'int': 0}]}
    witness = {'n': 0, '_kind': 'undefined', '_real': 'no value',
               '_site': 'ensures', '_expr': foreign}
    cert = r._undef_cert(r.Ctx(task, concrete=True), task, task['body'], witness)
    assert cert is None, 'an unrelated expression must not refute total_zero'


def test_return_is_not_an_invariant_preservation_failure():
    import sys
    sys.path.insert(0, 't')
    import lower_rocq as r
    eq = lambda a, b: {'op': '==', 'args': [a, b]}
    prefix = [{'assign': ['r', {'int': 0}]}]
    w = {'cond': {'bool': True}, 'decreases': {'int': 1},
         'invariants': [eq({'var': 'r'}, {'int': 0})],
         'body': [{'return': ['r', {'int': 1}]}]}
    task = {'t': 1, 'name': 'return_one',
            'params': [{'name': 'n', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [eq({'var': 'r'}, {'int': 1})],
            'body': prefix + [{'while': w}]}
    witness = {'n': 0, 'r': 0, '_kind': 'preservation', '_real': 1, '_twin': 1}
    cert = r._loop_cert(r.Ctx(task, concrete=True), task, prefix, w, [], witness)
    assert cert is None, 'this returning step satisfies its actual obligation'


def test_exit_certificate_respects_frozen_prefix_state():
    import sys
    sys.path.insert(0, 't')
    import lower_rocq as r
    I = lambda n: {'int': n}
    V = lambda n: {'var': n}
    O = lambda op, *a: {'op': op, 'args': list(a)}
    prefix = [{'assign': ['r', I(1)]},
              {'var': {'name': 'i', 'type': 'int', 'init': V('n')}}]
    w = {'cond': O('>', V('i'), I(0)), 'decreases': V('i'),
         'invariants': [O('>=', V('i'), I(0))],
         'body': [{'assign': ['i', O('-', V('i'), I(1))]}]}
    task = {'t': 1, 'name': 'framed_result',
            'params': [{'name': 'n', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}],
            'requires': [O('>=', V('n'), I(0))],
            'ensures': [O('==', V('r'), I(1))],
            'body': prefix + [{'while': w}]}
    witness = {'n': 1, 'i': 0, 'r': 0, '_kind': 'exit', '_real': 1, '_twin': 1}
    cert = r._loop_cert(r.Ctx(task, concrete=True), task, prefix, w, [], witness)
    assert cert is None, 'r=0 is not an admissible exit state for this framed variable'


def test_nested_replay_budget_aborts_the_entire_walk():
    import sys
    from unittest.mock import patch
    sys.path.insert(0, 't')
    import lower_rocq as r
    I = lambda n: {'int': n}
    V = lambda n: {'var': n}
    O = lambda op, *a: {'op': op, 'args': list(a)}
    inner = {'while': {'cond': O('<', V('i'), I(3)),
                       'decreases': O('-', I(3), V('i')), 'invariants': [],
                       'body': [{'assign': ['i', O('+', V('i'), I(1))]}]}}
    outer = {'while': {'cond': V('running'), 'decreases': I(1), 'invariants': [],
                       'body': [{'assign': ['running', {'bool': False}]}, inner]}}
    body = [outer, {'assign': ['r', O('div', I(1), O('-', V('i'), I(1)))]}]
    with patch.object(r, '_MAX_UNDEF_UNROLL', 2):
        fact = r._first_undef_body(body, {'running': True, 'i': 0}, {})
    assert fact is None, 'budget exhaustion must not expose an unreachable suffix state'


def test_synthetic_invariant_does_not_follow_mutable_initializer():
    import sys, re
    sys.path.insert(0, 't')
    import lower_rocq as r
    I = lambda n: {'int': n}
    V = lambda n: {'var': n}
    O = lambda op, *a: {'op': op, 'args': list(a)}
    prefix = [{'var': {'name': 'i', 'type': 'int', 'init': I(0)}},
              {'var': {'name': 'h', 'type': 'int', 'init': V('i')}}]
    w = {'cond': O('<', V('i'), I(1)), 'decreases': O('-', I(1), V('i')),
         'invariants': [O('>=', V('i'), I(0)), O('<=', V('i'), I(1))],
         'body': [{'assign': ['i', O('+', V('i'), I(1))]}]}
    suffix = [{'assign': ['r', V('h')]}]
    task = {'t': 1, 'name': 'frozen_initializer',
            'params': [{'name': 'n', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [O('==', V('r'), I(0))],
            'body': prefix + [{'while': w}] + suffix}
    src = r.gen_loop(r.Ctx(task), prefix, w, suffix, [0])
    assert not re.search(r'\bh\s*=\s*i\b', src), 'h == i is not a loop invariant'
