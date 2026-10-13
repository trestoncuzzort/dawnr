import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Five findings of the GPT-6 Astra review of 2026-10-13, each reproduced before its fix: the gate counts every
# present kernel, distinct ids name distinct tasks, a reused output directory grades only this set, an extraction
# refusal is not a success, an unreadable assertion leaves a suite incomplete.


def test_missing_present_kernel_keeps_gate_closed():
    from pathlib import Path
    from unittest.mock import patch
    import grade as g

    cols = [('dafny', 'v1'), ('verus', 'v1')]
    rows = {'f': {'dafny': (g.Outcome.VERIFIED, g.Outcome.REFUTED, True)}}
    with (
        patch.object(g.harness, 'load', return_value={'name': 'f'}),
        patch.object(g.harness, 'twin_cached', return_value=({}, 'one-edit', {})),
        patch.object(g.harness, 'witness', return_value='w'),
        patch.object(g.harness, 'decorative_kind', return_value=None),
    ):
        result = g.build_verdicts(cols, rows, {}, [Path('f.json')], 3, 0.0)
    assert result['tasks']['f']['gate'] is False


def test_distinct_ids_have_distinct_task_names():
    import grade as g

    first = g._safe_name('g', 'case-1', 'f')
    second = g._safe_name('g', 'case_1', 'f')
    assert first != second


def test_previous_extraction_is_not_dispatched_again():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace
    from unittest.mock import patch
    import grade as g

    with TemporaryDirectory() as directory:
        root = Path(directory)
        out = root / 'out'
        (out / 'tasks').mkdir(parents=True)
        stale = out / 'tasks' / 'g_new__f.json'
        stale.write_text(json.dumps({'name': 'g_new__f'}), encoding='utf-8')
        source = root / 'replies.jsonl'
        source.write_text(json.dumps({'id': 'new', 'reply': ''}), encoding='utf-8')
        args = SimpleNamespace(out=out, replies=source, jobs=1, kernels=None, flake=3, min_kernels=2)
        kernels = ([('dafny', 'v1'), ('verus', 'v1')], ['dafny', 'verus'], {}, {}, 0.0, True)
        with (
            patch.object(g, 'run_kernels', return_value=kernels) as dispatch,
            patch.object(g, 'write_outputs'),
            patch.object(g.harness, 'OUT', out),
        ):
            g.cmd_replies_main(args)
        assert not dispatch.called or stale not in dispatch.call_args.args[0]


def test_extraction_refusal_prevents_success_exit():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace
    from unittest.mock import patch
    import grade as g

    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / 'replies.jsonl'
        records = [{'id': 'ok', 'reply': 'valid task'}, {'id': 'bad', 'reply': ''}]
        source.write_text('\n'.join(json.dumps(r) for r in records), encoding='utf-8')
        out = root / 'out'
        args = SimpleNamespace(out=out, replies=source, jobs=1, kernels=None, flake=3, min_kernels=2)
        extracted = [
            {'stage': 'task', 'name': 'g_ok__f', 'task': {'name': 'g_ok__f'}},
            {'stage': 'no-block'},
        ]
        names = ['dafny', 'verus']
        rows = {'g_ok__f': {k: (g.Outcome.VERIFIED, g.Outcome.REFUTED, True) for k in names}}
        kernels = ([(k, 'v1') for k in names], names, rows, {}, 0.0, True)
        with (
            patch.object(g, 'extract_one', side_effect=extracted),
            patch.object(g, 'run_kernels', return_value=kernels),
            patch.object(g, 'write_outputs'),
            patch.object(g.harness, 'OUT', out),
        ):
            status = g.cmd_replies_main(args)
        assert status == 1


def test_refused_assertion_prevents_overall_test_pass():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace
    from unittest.mock import patch
    import grade as g

    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / 'replies.jsonl'
        record = {'id': 'x', 'reply': 'valid task', 'tests': ['assert f(0) == 0', 'assert f(1) > 0']}
        source.write_text(json.dumps(record), encoding='utf-8')
        args = SimpleNamespace(out=root / 'out', replies=source)
        extracted = {'stage': 'task', 'name': 'g_x__f', 'task': {'name': 'g_x__f'}}
        with (
            patch.object(g, 'extract_one', return_value=extracted),
            patch.object(g.mbpp_dfy, 'parse_assertion', side_effect=[{'ok': True}, {'ok': False}]),
            patch.object(g.se, 'run_point', return_value={'verdict': 'pass'}),
        ):
            result = g.cmd_replies(args)
        assert result['extract']['x']['tests_refused'] == 1
        assert result['tests']['x']['overall'] != 'pass'
