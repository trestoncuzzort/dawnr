import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Nine findings of the GPT-6 Astra review of 2026-10-13, each reproduced before its fix (see the commit).


def test_sequence_equality_is_not_pointer_equality():
    import sys
    sys.path.insert(0, 't')
    import lift_acsl_check as m
    p = m.Printer({'a': 'pa', 'b': 'pb'}, {'a': 'na', 'b': 'nb'}, {}, {'a': 'seq', 'b': 'seq'})
    e = {'op': '==', 'args': [{'var': 'a'}, {'var': 'b'}]}
    try:
        text = p.pred(e)
    except ValueError:
        return  # Explicit refusal is also sound.
    assert text != '(pa == pb)', text


def test_quantifier_call_range_preserves_outer_bound():
    import sys
    sys.path.insert(0, 't')
    import lift_acsl_check as m
    p = m.Printer({'i': 'outer_i'}, {}, {'F': ('G', 'bool')}, {'i': 'int'})
    e = {'forall': {'var': 'i', 'lo': {'int': 0}, 'hi': {'var': 'i'}, 'body': {'call': {'fun': 'F', 'args': [{'var': 'i'}]}}}}
    sites = []
    m.calls_with_context(e, [], sites, {'F'})
    call, pc = sites[0]
    formula = m.pc_formula(p, [], pc, lambda: 'D(' + p.term(call['args'][0]) + ')')
    assert 'outer_i' in formula, formula


def test_cross_function_call_requires_callee_domain():
    import sys
    sys.path.insert(0, 't')
    import lift_acsl_check as m
    def call(name, arg):
        return {'call': {'fun': name, 'args': [arg]}}
    x = {'var': 'x'}
    fs = [
        {'name': 'F', 'params': [{'name': 'x', 'type': 'int'}], 'body': call('H', x), 'decreases': {'int': 0}},
        {'name': 'H', 'params': [{'name': 'x', 'type': 'int'}], 'body': {'ite': {'cond': {'op': '>=', 'args': [x, {'int': 0}]}, 'then': x, 'else': {'int': 0}}}, 'decreases': {'int': 0}}
    ]
    recs = [{'dafny_name': name, 'acsl_name': 'G_' + name, 'result': 'int', 'params': [('x', 'int')], 'domain': domain} for name, domain in [('F', []), ('H', ['x >= 0'])]]
    task = {'params': [], 'returns': [{'name': 'r', 'type': 'int'}], 'body': [], 'requires': [], 'ensures': [{'op': '==', 'args': [{'var': 'r'}, call('F', {'int': -1})]}], 'spec_funs': fs}
    side = {'params': [], 'locals': [], 'rec_funs': recs, 'ret': {'c_type': 'int'}, 'src_pre': [], 'src_post': ['result == G_F(-1)'], 'src_loops': []}
    built = m.build(task, {}, side)
    obligations = [body for name, body in built['lemmas'] if name != 'tlift_eqn_H']
    assert any('tlift_D_H(' in body for body in obligations), built['lemmas']


def test_harness_preserves_wide_return_value():
    import sys, shutil, subprocess, tempfile
    from pathlib import Path
    sys.path.insert(0, 't')
    import lift_acsl_check as m
    if not shutil.which('gcc'):
        return
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / 'f.c'
        source.write_text('long long f(void) { return 4294967296LL; }\n')
        side = {'params': [], 'c_file': str(source), 'function': 'f', 'ret': {'c_type': 'long long'}}
        task = {'params': [], 'returns': [{'name': 'r', 'type': 'int'}]}
        harness = root / 'diff.c'
        harness.write_text(m.c_harness(side, task, [{}]))
        exe = root / 'diff.bin'
        subprocess.run(['gcc', '-std=c99', '-O0', str(harness), '-o', str(exe)], check=True, capture_output=True)
        output = subprocess.check_output([str(exe)], text=True).strip()
        assert output == '4294967296', output


def test_call_site_binder_does_not_escape():
    import sys
    sys.path.insert(0, 't')
    import lift_acsl_check as m
    p = m.Printer({'i': 'outer_i'}, {}, {'F': ('G', 'bool')}, {'i': 'int'})
    e = {'forall': {'var': 'i', 'lo': {'int': 0}, 'hi': {'int': 1}, 'body': {'call': {'fun': 'F', 'args': [{'var': 'i'}]}}}}
    sites = []
    m.calls_with_context(e, [], sites, {'F'})
    call, pc = sites[0]
    m.pc_formula(p, [], pc, lambda: 'D(' + p.term(call['args'][0]) + ')')
    assert p.term({'var': 'i'}) == 'outer_i', p.names


def test_spec_function_division_requests_helpers():
    import sys
    sys.path.insert(0, 't')
    import lift_acsl_check as m
    f = {'name': 'half', 'params': [{'name': 'x', 'type': 'int'}], 'body': {'op': 'div', 'args': [{'var': 'x'}, {'int': 2}]}, 'decreases': {'int': 0}}
    task = {'params': [], 'returns': [{'name': 'r', 'type': 'int'}], 'body': [], 'requires': [], 'ensures': [{'op': '==', 'args': [{'var': 'r'}, {'call': {'fun': 'half', 'args': [{'int': 4}]}}]}], 'spec_funs': [f]}
    src = {'dafny_name': 'half', 'acsl_name': 'half', 'result': 'int', 'params': [('x', 'int')], 'domain': ['x >= 0']}
    side = {'params': [], 'locals': [], 'rec_funs': [src], 'ret': {'c_type': 'int'}, 'src_pre': [], 'src_post': ['result == half(4)'], 'src_loops': []}
    built = m.build(task, {}, side)
    assert built['divmod'], built


def test_unsupported_lowering_is_refused_despite_differential_agreement():
    import sys, tempfile
    from pathlib import Path
    from unittest.mock import patch
    sys.path.insert(0, 't')
    import lift_acsl_check as m
    seq = {'ite': {'cond': {'bool': True}, 'then': {'var': 'a'}, 'else': {'var': 'a'}}}
    task = {'params': [{'name': 'a', 'type': 'seq'}], 'returns': [{'name': 'r', 'type': 'int'}], 'body': [], 'requires': [], 'ensures': [{'op': '>=', 'args': [{'op': 'len', 'args': [seq]}, {'int': 0}]}]}
    side = {'params': [{'role': 'seq', 'dafny_name': 'a', 'c_type': 'const value_type *', 'of': 'n'}, {'role': 'len', 'dafny_name': 'n', 'c_type': 'unsigned int', 'of': 'a'}], 'locals': [], 'rec_funs': [], 'ret': {'c_type': 'int'}, 'src_pre': [], 'src_post': [], 'src_loops': []}
    with tempfile.TemporaryDirectory() as td, patch.object(m, 'run_differential', return_value={'inputs': 1, 'agree': 1, 'verdict': 'agree'}):
        result = m.check(task, {}, side, Path(td), Path(td))
    assert result['wp']['error'].startswith('len of')
    assert result['trust'] is None and result['refusal'] is not None, result


def test_writable_source_parameter_gets_writable_storage():
    import sys, shutil, subprocess, tempfile
    from pathlib import Path
    sys.path.insert(0, 't')
    import lift_acsl_check as m
    if not shutil.which('gcc'):
        return
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / 'f.c'
        source.write_text('typedef int value_type;\nint f(value_type *a, unsigned n) { a[0] = 7; return a[0]; }\n')
        side = {'c_file': str(source), 'function': 'f', 'ret': {'c_type': 'int'}, 'params': [{'role': 'seq', 'c_name': 'a', 'dafny_name': 'a', 'c_type': 'value_type *', 'of': 'n'}, {'role': 'len', 'c_name': 'n', 'dafny_name': 'n', 'c_type': 'unsigned int', 'of': 'a'}]}
        task = {'params': [{'name': 'a', 'type': 'seq'}], 'returns': [{'name': 'r', 'type': 'int'}]}
        harness = root / 'diff.c'
        harness.write_text(m.c_harness(side, task, [{'a': (0,)}]))
        p = subprocess.run(['gcc', '-std=c99', '-Werror=discarded-qualifiers', '-fsyntax-only', str(harness)], capture_output=True, text=True)
        assert p.returncode == 0, p.stderr


def test_source_timeout_returns_a_structured_failure():
    import sys, subprocess, tempfile
    from pathlib import Path
    from unittest.mock import patch
    sys.path.insert(0, 't')
    import lift_acsl_check as m
    task = {'params': [], 'returns': [{'name': 'r', 'type': 'int'}], 'body': []}
    side = {'params': [], 'c_file': 'f.c', 'function': 'f', 'ret': {'c_type': 'int'}}
    effects = [subprocess.CompletedProcess(['gcc'], 0, '', ''), subprocess.TimeoutExpired(['diff.bin'], 60)]
    with tempfile.TemporaryDirectory() as td, patch.object(m, 'draw_inputs', return_value=[{}]), patch.object(m, 'run_lifted', return_value=0), patch.object(m.subprocess, 'run', side_effect=effects):
        result = m.run_differential(task, side, Path(td), Path(td), n=1)
    assert result['verdict'] not in ('agree', 'no-input'), result
