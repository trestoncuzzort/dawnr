import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Eight findings of the review on the Verus lowering, each reproduced before its fix: a spec function's invented domain is owed at its calls, the source loop measure is asserted non-negative under the guard, lemma bodies owe definedness, a value certificate certifies what the twin body computes, division bridges stay under their guards, a map-valued early-return slot, the split length law only for an int separator, the static scope follows the renamed identifiers.


@pytest.mark.skipif(shutil.which("verus") is None, reason="verus is not installed")
def test_partial_spec_function_is_not_verified():
    import lower_verus as lv
    import subprocess, tempfile
    from pathlib import Path
    I = lambda n: {'int': n}
    V = lambda n: {'var': n}
    O = lambda op, *a: {'op': op, 'args': list(a)}
    f = {'name': 'get', 'params': [{'name': 's', 'type': 'seq'}, {'name': 'k', 'type': 'int'}],
         'result': 'int', 'decreases': V('k'),
         'body': {'ite': {'cond': O('<=', V('k'), I(0)), 'then': I(0),
                          'else': O('at', V('s'), O('-', V('k'), I(1)))}}}
    task = {'t': 1, 'name': 'partial_spec', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [{'bool': True}], 'spec_funs': [f],
            'body': [{'assign': ['r', {'call': {'fun': 'get', 'args': [O('seq'), I(1)]}}]}]}
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'case.rs'
        p.write_text(lv.lower(task, task['body']))
        result = subprocess.run(['verus', '--no-cheating', str(p)], capture_output=True, text=True)
    assert result.returncode != 0, 'Verified a call outside the invented spec-function domain'


@pytest.mark.skipif(shutil.which("verus") is None, reason="verus is not installed")
def test_negative_source_loop_measure_is_rejected():
    import lower_verus as lv
    import subprocess, tempfile
    from pathlib import Path
    I = lambda n: {'int': n}
    V = lambda n: {'var': n}
    O = lambda op, *a: {'op': op, 'args': list(a)}
    w = {'cond': O('==', V('i'), I(-1)),
         'invariants': [O('<=', I(-2), V('i')), O('<=', V('i'), I(-1))],
         'decreases': V('i'), 'body': [{'assign': ['i', I(-2)]}]}
    task = {'t': 1, 'name': 'negative_measure', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [O('==', V('r'), I(0))],
            'body': [{'assign': ['r', I(0)]},
                     {'var': {'name': 'i', 'type': 'int', 'init': I(-1)}}, {'while': w}]}
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'case.rs'
        p.write_text(lv.lower(task, task['body']))
        result = subprocess.run(['verus', '--no-cheating', str(p)], capture_output=True, text=True)
    assert result.returncode != 0, 'Accepted a negative source measure while the guard holds'


@pytest.mark.skipif(shutil.which("verus") is None, reason="verus is not installed")
def test_undefined_lemma_assertion_is_rejected():
    import lower_verus as lv
    import subprocess, tempfile
    from pathlib import Path
    I = lambda n: {'int': n}
    O = lambda op, *a: {'op': op, 'args': list(a)}
    read = O('at', O('seq'), I(0))
    lemma = {'name': 'bad', 'params': [], 'requires': [],
             'ensures': [{'bool': True}], 'body': [{'assert': O('==', read, read)}]}
    task = {'t': 1, 'name': 'lemma_definedness', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [O('==', {'var': 'r'}, I(0))], 'lemmas': [lemma],
            'body': [{'lemma': {'name': 'bad', 'args': []}}, {'assign': ['r', I(0)]}]}
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'case.rs'
        p.write_text(lv.lower(task, task['body']))
        result = subprocess.run(['verus', '--no-cheating', str(p)], capture_output=True, text=True)
    assert result.returncode != 0, 'Verified a lemma containing an undefined assertion'


def test_value_certificate_rejects_result_not_produced_by_body():
    import lower_verus as lv
    task = {'t': 1, 'name': 'constant_zero', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [{'op': '==', 'args': [{'var': 'r'}, {'int': 0}]}],
            'body': [{'assign': ['r', {'int': 0}]}]}
    witness = {'_kind': 'value', '_ens': True, '_twin': 1}
    formula = lv.certificate_formula(task, task['body'], witness)
    assert formula is None or not lv.interp.ev(formula, {}, {}, lv.interp.St()), \
        'Produced a true refutation certificate for a result this body cannot return'


@pytest.mark.skipif(shutil.which("verus") is None, reason="verus is not installed")
def test_guarded_division_verifies():
    import lower_verus as lv
    import subprocess, tempfile
    from pathlib import Path
    I = lambda n: {'int': n}
    V = lambda n: {'var': n}
    O = lambda op, *a: {'op': op, 'args': list(a)}
    value = {'ite': {'cond': O('==', V('y'), I(0)), 'then': I(0),
                     'else': O('div', I(10), V('y'))}}
    task = {'t': 1, 'name': 'guarded_division', 'params': [{'name': 'y', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [{'bool': True}], 'body': [{'assign': ['r', value]}]}
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'case.rs'
        p.write_text(lv.lower(task, task['body']))
        result = subprocess.run(['verus', '--no-cheating', str(p)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_map_dummy_is_supported_or_refused_by_name():
    import lower_verus as lv
    try:
        result = lv._dummy({'map': ['int', 'int']})
    except NotImplementedError:
        return
    assert isinstance(result, str)


def test_sequence_separator_does_not_get_character_lemma():
    import lower_verus as lv
    V = lambda n: {'var': n}
    O = lambda op, *a: {'op': op, 'args': list(a)}
    task = {'t': 1, 'name': 'split_words',
            'params': [{'name': 's', 'type': 'seq'}, {'name': 'sep', 'type': 'seq'}],
            'returns': [{'name': 'r', 'type': {'seq': 'seq'}}],
            'requires': [O('>', O('len', V('sep')), {'int': 0})],
            'ensures': [{'bool': True}],
            'body': [{'assign': ['r', O('split', V('s'), V('sep'))]}]}
    source = lv.lower(task, task['body'])
    assert 't_lemma_split_len_law(s, sep);' not in source


def test_sanitized_map_parameter_keeps_its_type():
    import lower_verus as lv
    map_ty = {'map': ['int', 'int']}
    task = {'t': 1, 'name': 'map_update',
            'params': [{'name': 'type', 'type': map_ty}],
            'returns': [{'name': 'r', 'type': map_ty}], 'requires': [],
            'ensures': [{'bool': True}],
            'body': [{'assign': ['r', {'op': 'update', 'args': [
                {'var': 'type'}, {'int': -1}, {'int': 7}]}]}]}
    source = lv.lower(task, task['body'])
    assert '.insert(' in source and '.update(' not in source
