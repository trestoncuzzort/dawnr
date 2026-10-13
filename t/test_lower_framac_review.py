import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Fifteen findings of the GPT-6 Astra review of 2026-10-13, each reproduced before its fix (see the commit). The
# measure-certificate test passes a task that carries a measure, since a certificate without one is refused.


def test_at_checks_literal_elements():
    import lower_framac as m
    zero_div = {'op': 'div', 'args': [{'int': 1}, {'int': 0}]}
    e = {'op': 'at', 'args': [
        {'op': 'seq', 'args': [zero_div]}, {'int': 0}]}
    obligations = m.code_ats(e, {})
    assert any(o[0] == 'nz' and o[1] == {'int': 0}
               for o in obligations), obligations


def test_slice_alias_has_domain_obligation():
    import lower_framac as m
    e = {'op': 'slice', 'args': [
        {'var': 's'}, {'int': 1}, {'int': 0}]}
    ctx = m.Ctx({'s': 'seq'}, {})
    assertions = m.at_asserts(e, ctx, '')
    assert assertions, 'An invalid slice currently gets no assertion'
    assert any('s_n' in a for a in assertions)


def test_while_checks_guard_on_exit_edge():
    import re
    import lower_framac as m
    v = {'var': 'i'}
    op = lambda name, *args: {'op': name, 'args': list(args)}
    body = [
        {'var': {'name': 'i', 'type': 'int', 'init': {'int': 1}}},
        {'while': {
            'cond': op('and', op('==', op('div', {'int': 1}, v), {'int': 1}),
                       op('>', v, {'int': 0})),
            'invariants': [op('>=', v, {'int': 0}), op('<=', v, {'int': 1})],
            'decreases': v,
            'body': [{'assign': ['i', {'int': 0}]}]}}]
    text = '\n'.join(m.stmts(body, m.Ctx({}, {}), 'f', ''))
    after_write = text.rsplit('i = 0;', 1)[1]
    assert '!= 0' in after_write or re.search(
        r'loop invariant[^\n]*i[^\n]*!= 0', text), text


def test_invariant_element_read_requires_bounds():
    import lower_framac as m
    op = lambda name, *args: {'op': name, 'args': list(args)}
    i = {'var': 'i'}
    cell = op('at', {'var': 's'}, {'int': 0})
    w = {'while': {
        'cond': op('<', i, {'int': 1}),
        'invariants': [op('==', cell, cell)],
        'decreases': op('-', {'int': 1}, i),
        'body': [{'assign': ['i', op('+', i, {'int': 1})]}]}}
    text = '\n'.join(m.stmts([w], m.Ctx({'s': 'seq', 'i': 'int'}, {}), 'f', ''))
    assert 's_n' in text, text


def test_sequence_literal_assignment_is_a_snapshot():
    import pathlib, subprocess, tempfile
    import lower_framac as m
    at = lambda k: {'op': 'at', 'args': [{'var': 'r'}, {'int': k}]}
    e = {'op': 'seq', 'args': [at(1), at(0)]}
    code = '\n'.join(m.seq_assign_lines('r', e, m.Ctx({'r': 'seq'}, {}), '', {}, 'f'))
    source = ('int main(void) { int r[2] = {1,2}; int r_n = 2;\n' + code
              + '\nreturn r[0] != 2 || r[1] != 1; }')
    with tempfile.TemporaryDirectory() as d:
        exe = str(pathlib.Path(d) / 'probe')
        subprocess.run(['cc', '-std=c99', '-x', 'c', '-', '-o', exe],
                       input=source, text=True, check=True, capture_output=True)
        assert subprocess.run([exe]).returncode == 0


def test_exact_return_length_does_not_rewrite_history():
    import pathlib, subprocess, tempfile
    import lower_framac as m
    seq = lambda *xs: {'op': 'seq', 'args': list(xs)}
    body = [
        {'assign': ['r', seq({'int': 1})]},
        {'var': {'name': 'n', 'type': 'int',
                 'init': {'op': 'len', 'args': [{'var': 'r'}]}}},
        {'assign': ['r', seq({'var': 'n'}, {'int': 0})]}]
    task = {'name': 'length_history', 'params': [],
            'returns': [{'name': 'r', 'type': 'seq'}], 'requires': [],
            'ensures': [{'bool': True}], 'body': body}
    source = m.lower(task, body) + '\nint main(void) { int r[2]; length_history_t(r,2); return r[0] != 1; }'
    with tempfile.TemporaryDirectory() as d:
        exe = str(pathlib.Path(d) / 'probe')
        subprocess.run(['cc', '-std=c99', '-x', 'c', '-', '-o', exe],
                       input=source, text=True, check=True, capture_output=True)
        assert subprocess.run([exe]).returncode == 0


def test_at_uses_logical_length_not_capacity():
    import lower_framac as m
    ctx = m.Ctx({'r': 'seq'}, {}, seq_len={'r': 'r_len'})
    e = {'op': 'at', 'args': [{'var': 'r'}, {'int': 0}]}
    text = '\n'.join(m.at_asserts(e, ctx, ''))
    assert 'r_len' in text, text


def test_logic_call_passes_current_sequence_length():
    import lower_framac as m
    funs = {'size': {'params': [{'name': 's', 'type': 'seq'}],
                     'result': 'int', 'labeled': True, 'is_task': False}}
    ctx = m.Ctx({'r': 'seq'}, funs, seq_len={'r': 'r_len'})
    rendered = m.acsl_call({'fun': 'size', 'args': [{'var': 'r'}]}, ctx)
    assert '(r, r_len)' in rendered, rendered


def test_term_conditional_preserves_sequence_equality():
    import lower_framac as m
    ctx = m.Ctx({'a': 'seq', 'b': 'seq'}, {})
    eq = {'op': '==', 'args': [{'var': 'a'}, {'var': 'b'}]}
    e = {'ite': {'cond': eq, 'then': {'int': 1}, 'else': {'int': 0}}}
    try:
        rendered = m.term(e, ctx)
    except NotImplementedError:
        return
    assert '\\forall' in rendered, rendered


def test_spec_call_inherits_callee_domain():
    import lower_framac as m
    funs = {'f': {'params': [{'name': 'x', 'type': 'int'}],
                  'result': 'int', 'labeled': False, 'is_task': False,
                  'body': {'op': 'div', 'args': [{'int': 1}, {'var': 'x'}]}}}
    call = {'call': {'fun': 'f', 'args': [{'int': 0}]}}
    try:
        obligation = m.defs(call, m.Ctx({}, funs))
    except NotImplementedError:
        return
    assert obligation is not None


def test_prefix_fact_tracks_initializer_dependencies():
    import lower_framac as m
    body = [
        {'var': {'name': 'x', 'type': 'int', 'init': {'int': 0}}},
        {'var': {'name': 'h', 'type': 'int', 'init': {'var': 'x'}}},
        {'assign': ['x', {'int': 1}]},
        {'assign': ['r', {'int': 0}]},
        {'while': {'cond': {'op': '<', 'args': [{'var': 'r'}, {'int': 1}]},
                   'invariants': [], 'decreases': {'op': '-', 'args': [{'int': 1}, {'var': 'r'}]},
                   'body': [{'assign': ['r', {'int': 1}]}]}}]
    text = '\n'.join(m.stmts(body, m.Ctx({'r': 'int'}, {}), 'f', ''))
    assert 'loop invariant h == x;' not in text, text


def test_executable_large_literal_uses_safe_encoding():
    import lower_framac as m
    n = 2147483648
    assert m.cexpr({'int': n}, {}, {}, 'f') == m._int_lit(n)


def test_sequence_certificate_rejects_invented_result():
    import lower_framac as m
    body = [{'assign': ['r', {'op': 'seq', 'args': [{'int': 1}]}]}]
    task = {'name': 'f', 'params': [], 'returns': [{'name': 'r', 'type': 'seq'}],
            'requires': [], 'ensures': [{'op': '==', 'args': [
                {'op': 'len', 'args': [{'var': 'r'}]}, {'int': 1}]}], 'body': body}
    witness = {'_kind': 'value', '_ens': True, '_twin': []}
    cert = m.certificate(task, body, witness, {'r': 'seq'}, {}, {'f', 'r'})
    assert cert is None, cert


def test_measure_certificate_requires_a_real_measure_site():
    import lower_framac as m
    body = [{'assign': ['r', {'int': 0}]}]
    task = {'name': 'f', 'params': [], 'returns': [{'name': 'r', 'type': 'int'}],
            'requires': [], 'ensures': [{'bool': True}], 'body': body}
    witness = {'_kind': 'measure', '_site': 'missing',
               '_caller_measure': 0, '_callee_measure': 0}
    cert = m.certificate(task, body, witness, {'r': 'int'}, {}, {'f', 'r'})
    assert cert is None, cert


def test_large_witness_integer_does_not_overflow_python_stack():
    import lower_framac as m
    witness = {'_kind': 'measure', '_caller_measure': 10**13,
               '_callee_measure': 10**13}
    text = m._measure_certificate({'decreases': {'var': 'n'}}, [], witness, {}, {}, set())   # a task with a measure
    assert isinstance(text, str)
