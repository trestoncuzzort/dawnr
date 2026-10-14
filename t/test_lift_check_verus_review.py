import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Five findings of the review on the Verus lift checker: proved needs the kernel to refute the negated equivalence (a one-edit twin); only an identity map closure is bridged to the view; an unnamed result beside a parameter called result gets a fresh name; a verifier ended by a signal is an error; a renderer refusal is named.


def test_success_without_twin_is_not_a_proof():
    import sys
    import tempfile
    import subprocess
    from pathlib import Path
    from unittest.mock import patch
    import lift_check_verus as m
    text = 'use vstd::prelude::*; verus! { proof fn t_eq_requires() ensures true {} proof fn t_eq_ensures() ensures true {} } fn main() {}'
    success = subprocess.CompletedProcess([], 0, '{"errors": 0, "verified": 2}', '')
    with tempfile.TemporaryDirectory() as d, patch.object(m.subprocess, 'run', return_value=success):
        result = m.run(text, Path(d), 'equivalence')
    assert result['verdict'] != 'proved', 'No kernel refutation of a twin was obtained'


def test_shifted_map_is_not_bridged_to_identity_view():
    import sys
    from pathlib import Path
    from types import SimpleNamespace as NS
    import lift_check_verus as m
    elem = NS(kind='int', text='i32')
    vec = NS(kind='seq', text='Vec<i32>', elem=elem)
    expression = 'v @ . map_values ( | x : i32 | x as int + 1 )'
    fn = NS(params=[NS(name='v', type=vec)], ret_name=None,
            requires_src=[expression + ' == ' + expression], ensures_src=[])
    assert m._map_bridges(fn, m.Views(), False) == ''


def test_unnamed_return_does_not_duplicate_result_parameter():
    import sys
    from pathlib import Path
    from types import SimpleNamespace as NS
    from contextlib import ExitStack
    from unittest.mock import patch
    import lift_check_verus as m
    ty = NS(kind='int', text='i32')
    fn = NS(params=[NS(name='result', type=ty, type_src='i32')],
            ret=ty, ret_name=None, ret_src='i32', attrs=[],
            requires=[], ensures=[], requires_src=[], ensures_src=[])
    vf = NS(exec_fns={'f': fn}, const_text={}, spec_fns={})
    rendered = NS(file=vf, target='f', refusal=None)
    task = {'params': [{'name': 'result', 'type': 'int'}],
            'returns': [{'name': 'out', 'type': 'int'}],
            'requires': [], 'ensures': [], 'spec_funs': []}
    with ExitStack() as stack:
        for obj, name, value in [
            (m.lift_verus, 'render', rendered),
            (m.lift_verus, 'Renderer', NS(called_specs=set())),
            (m.lift_verus, '_reach', []),
            (m, '_t_type', 'int'),
            (m.lower_verus, '_uses_strlib', False),
        ]:
            stack.enter_context(patch.object(obj, name, return_value=value))
        stack.enter_context(patch.object(m.names, 'sanitize', side_effect=lambda t, *a, **k: (t, {})))
        try:
            text, _ = m.build('', task, {})
        except m.NoHarness:
            return
    assert 'proof fn t_eq_ensures(result: i32, result: i32)' not in text


def test_killed_verifier_is_an_execution_error():
    import sys
    import tempfile
    import subprocess
    from pathlib import Path
    from unittest.mock import patch
    import lift_check_verus as m
    killed = subprocess.CompletedProcess([], -9, '', 'error: assertion failed\n')
    with tempfile.TemporaryDirectory() as d, patch.object(m.subprocess, 'run', return_value=killed):
        result = m.run('proof fn t_eq_requires() {}', Path(d), 'killed')
    assert result['verdict'] == 'error'


def test_renderer_refusal_preserves_construct_name():
    import sys
    from pathlib import Path
    from types import SimpleNamespace as NS
    from unittest.mock import patch
    import lift_check_verus as m
    rendered = NS(file=None, target=None, refusal='unsupported construct: match')
    with patch.object(m.lift_verus, 'render', return_value=rendered):
        try:
            m.build('', {}, {})
        except m.NoHarness as exc:
            assert 'match' in str(exc)
        else:
            assert False, 'Expected a named refusal'
