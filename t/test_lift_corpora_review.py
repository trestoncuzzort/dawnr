import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Five findings of the review on the corpora stage: a HumanEval task that fails its pool tests is refused; a failed lifter run never returns an earlier summary; whitespace inside a literal of the English specification is kept; colliding staged stems are refused; recovery never deletes the lift it reads from.


def test_failed_humaneval_curation_is_a_refusal():
    from types import SimpleNamespace
    from unittest.mock import Mock, patch
    import lift_corpora as m

    stem = 'humaneval_dafny_999_absolute'
    task = {'name': stem + '__abs'}
    gates = SimpleNamespace(forbids=lambda tid: None)
    gate = Mock()
    gate.admit.return_value = True
    pool = {m.se.HUMANEVAL_BASE + 999: {
        'points': [{'args': [('int', 5)], 'expected': ('int', 6)}]}}
    with patch.object(m.se, 'run_point', return_value={'verdict': 'fail'}), \
         patch.object(m.surface, 'print_task', return_value='document'), \
         patch.object(m, 'twin_of', return_value=None):
        verdict = m.screen(stem, task, {}, {stem: 'Return the absolute value.'},
                           pool, gates, gate, {}, None)
    assert verdict['refused'] is not None, verdict


def test_failed_lifter_cannot_reuse_old_summary():
    import json
    import subprocess
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import lift_corpora as m

    def failed_run(cmd, **kwargs):
        if kwargs.get('check'):
            raise subprocess.CalledProcessError(1, cmd)
        return subprocess.CompletedProcess(cmd, 1)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        staged, out = root / 'staged', root / 'lift'
        staged.mkdir()
        out.mkdir()
        (out / 'run_summary.json').write_text(json.dumps({'verdict_counts': {'pass': 1}}))
        with patch.object(m.subprocess, 'run', side_effect=failed_run):
            try:
                m.run_lifter(staged, out, 1, True)
            except (SystemExit, subprocess.CalledProcessError):
                return
        assert False, 'Failed invocation returned a stale lifter summary'


def test_source_literal_spaces_are_preserved():
    import lift_corpora as m

    statement = 'Return true exactly when s equals "a  b".'
    rows = {'DX1': {'vc-description': statement, 'source': 'apps',
                    'source-id': 'apps_test_9'}}
    head, _, _ = m.head_for('vericoding_DX1', {'name': 'literal'},
                            rows, {}, {}, None)
    assert head['problem'] == statement


def test_staging_does_not_silently_merge_sources():
    import tempfile
    from pathlib import Path
    import lift_corpora as m

    with tempfile.TemporaryDirectory() as tmp:
        src, staged = Path(tmp) / 'src', Path(tmp) / 'staged'
        (src / 'text-descriptions').mkdir(parents=True)
        (src / '001-a-b.dfy').write_text('method Zero() returns (x: int) ensures x == 0 { x := 0; }')
        (src / '001-a_b.dfy').write_text('method One() returns (x: int) ensures x == 1 { x := 1; }')
        (src / 'text-descriptions' / '001-a-b.txt').write_text('function `Zero`: Return zero.')
        try:
            m.stage_humaneval_dafny(src, staged)
        except (SystemExit, ValueError):
            return
        assert len(list(staged.glob('*.dfy'))) == 2, 'Distinct sources were silently merged'


def test_publish_preserves_source_lift_with_partial_prefix():
    import tempfile
    from pathlib import Path
    import lift_corpora as m

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        original = root / 'tasks.partial-123'
        meta = root / 'tasks.partial-123.meta'
        original.mkdir()
        meta.mkdir()
        marker = meta / 'source-marker'
        marker.write_text('must survive')
        recovered, rmeta = root / 'tasks', root / 'tasks.meta'
        m.claim_destination(recovered, rmeta)
        try:
            m.publish(recovered, rmeta, [], meta, [], [], {'kind': m.RECOVERY_KIND})
        except SystemExit:
            pass
        assert original.is_dir() and marker.is_file(), 'Recovery deleted its source lift'
