import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Three findings of the GPT-6 Astra review of 2026-10-13, each reproduced before its fix: the ladder applies the
# well-formedness filter twin_for applies, a lowering that abstains is a named refusal, every task runs and reports.


def test_ladder_excludes_ill_typed_projections():
    import harness as h
    from types import SimpleNamespace
    from unittest.mock import patch

    expr = {'op': 'proj', 'args': [{'var': 'p'}, {'int': 1}]}
    task = {
        'name': 'projection',
        'params': [{'name': 'p', 'type': {'tuple': ['bool', 'int', 'bool']}}],
        'returns': [{'name': 'r', 'type': 'int'}],
        'requires': [],
        'ensures': [{'op': '==', 'args': [{'var': 'r'}, expr]}],
        'body': [{'return': ['r', expr]}],
    }
    values = [False, 7, True]

    def replay(body):
        index = body[0]['return'][1]['args'][1]['int']
        got = values[index]
        return {'_kind': 'value', 'p': values, '_real': 7,
                '_twin': got, '_ens': got != 7}

    def ill_formed(t, body):
        index = body[0]['return'][1]['args'][1]['int']
        return t['params'][0]['type']['tuple'][index] != 'int'

    ref = SimpleNamespace(points=[({'p': values}, 7)], witness=replay)
    # Isolate the harness from the interpreter and checker while supplying
    # their concrete replay results and static typing judgments.
    with patch.object(h.interp, 'Reference', return_value=ref), \
         patch.object(h, '_ill_formed', side_effect=ill_formed):
        assert h.ladder_rungs(task) == []


def test_unsupported_lowering_is_a_named_refusal():
    import harness as h
    import io
    from contextlib import redirect_stdout
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from unittest.mock import patch

    def quotient(d):
        return [{'return': ['r', {'op': 'div', 'args': [
            {'var': 'n'}, {'int': d}]}]}]

    task = {'name': 'quotient', 'body': quotient(2)}
    w = {'_kind': 'value', 'n': 2, '_real': 1, '_twin': 0, '_ens': True}

    def lower(task, body, witness=None):
        raise NotImplementedError('unsupported construct: div')

    output = io.StringIO()
    with TemporaryDirectory() as directory, \
         patch.object(h, 'OUT', Path(directory)), \
         patch.object(h, 'load', return_value=task), \
         patch.object(h, 'twin_cached', return_value=(quotient(3), 'off-by-one', w)), \
         redirect_stdout(output):
        assert h.run_task(Path('quotient.t'), lower, object(), 'dfy') is False
    assert 'REFUSED' in output.getvalue()
    assert 'div' in output.getvalue()


def test_run_all_does_not_skip_tasks_after_refusal():
    import harness as h
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace
    from unittest.mock import patch

    with TemporaryDirectory() as directory:
        paths = [Path(directory) / 'first.t', Path(directory) / 'second.t']
        for path in paths:
            path.touch()
        backend = SimpleNamespace(version=lambda: 'test backend')
        with patch.object(h, 'run_task', side_effect=[False, True]) as run:
            status = h.run_all([str(p) for p in paths], object(), backend, 'dfy')
        assert status == 1
        assert [call.args[0] for call in run.call_args_list] == paths
