"""Four findings of the GPT-6 Astra review of 2026-10-13 on the lifter's cache
and resumability (t/lifter.py), each reproduced before its fix: a checked outcome
must not be attributed to a different source file, artifacts must be invalidated
before they are overwritten, a method named "outcome" must not collide with the
per-file resumability marker, and a missing or malformed referenced artifact must
be treated as an invalid cache entry. Source: this repository's own cache/receipt
design; dafny.org/latest/DafnyRef/DafnyRef for the lifted language."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

def test_cache_does_not_cross_source_paths():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from unittest.mock import patch
    import lifter as l

    with TemporaryDirectory() as td:
        root = Path(td)
        a, b = root / 'a' / 'M.dfy', root / 'b' / 'M.dfy'
        a.parent.mkdir()
        b.parent.mkdir()
        a.write_text('method M() returns (r: int) ensures r == 0 { r := 0; }', encoding='utf-8')
        b.write_text('method M() returns (r: int) ensures r == 1 { r := 0; }', encoding='utf-8')
        out = root / 'out'
        record = l._record_from_dict({
            'source_path': str(a), 'method': 'M', 'rprint_sha256': '0' * 64,
            'checker_verdicts': {'original': 'verified', 'twin': 'refuted'},
        })
        previous = l.FileOutcome(a, methods=[l.MethodOutcome(
            'M', task={'name': 'M'}, record=record, checked=True)])
        l._write_outcome(previous, out, a.stem)
        with patch.object(l.lift_resolve, 'resolve', side_effect=NotImplementedError):
            result = l.lift_file(b, out_dir=out)
        assert result.resolve_refusal is not None, 'Reused another source file\'s checked outcome'
        assert result.resolve_refusal.reason == 'module-not-implemented'

def test_failed_write_cannot_reuse_old_verdict_for_new_task():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from unittest.mock import patch
    import lifter as l

    with TemporaryDirectory() as td:
        out = Path(td)
        source = out / 'x.dfy'
        old_task = {'name': 'M', 'ensures': ['r == 0']}
        new_task = {'name': 'M', 'ensures': ['r == 1']}
        old_record = l._record_from_dict({
            'source_path': str(source), 'method': 'M', 'rprint_sha256': '0' * 64,
            'checker_verdicts': {'original': 'verified', 'twin': 'refuted'},
        })
        new_record = l._record_from_dict({
            'source_path': str(source), 'method': 'M', 'rprint_sha256': '1' * 64,
        })
        l._write_outcome(l.FileOutcome(source, methods=[l.MethodOutcome(
            'M', task=old_task, record=old_record, checked=True)]), out, 'x')
        replacement = l.FileOutcome(source, methods=[l.MethodOutcome(
            'M', task=new_task, record=new_record, checked=False)])
        real_open = Path.open
        sidecar = out / 'x.M.lift.json'

        def deny_sidecar_write(path, mode='r', *args, **kwargs):
            if path == sidecar and mode == 'w':
                raise PermissionError('read-only sidecar')
            return real_open(path, mode, *args, **kwargs)

        with patch.object(Path, 'open', deny_sidecar_write):
            try:
                l._write_outcome(replacement, out, 'x')
            except PermissionError:
                pass
        cached = l._load_outcome(out, 'x', source)
        assert cached is None or all(
            not mo.checked or mo.task != new_task for mo in cached.methods
        ), 'An unchecked replacement task inherited the previous checked verdict'

def test_method_named_outcome_preserves_its_task():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory
    import lifter as l

    with TemporaryDirectory() as td:
        out = Path(td)
        task = {'name': 'outcome', 'body': []}
        result = l.FileOutcome(Path('x.dfy'), methods=[
            l.MethodOutcome('outcome', task=task)
        ])
        l._write_outcome(result, out, 'x')
        marker = json.loads(l._marker_path(out, 'x').read_text(encoding='utf-8'))
        task_path = out / marker['methods'][0]['task_file']
        assert json.loads(task_path.read_text(encoding='utf-8')) == task

def test_invalid_task_artifacts_invalidate_cache():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    import lifter as l

    for damage in ('missing', 'truncated'):
        with TemporaryDirectory() as td:
            out = Path(td)
            source = out / 'x.dfy'
            record = l._record_from_dict({
                'source_path': str(source), 'method': 'M',
                'rprint_sha256': '0' * 64,
            })
            result = l.FileOutcome(source, methods=[l.MethodOutcome(
                'M', task={'name': 'M'}, record=record, checked=True)])
            l._write_outcome(result, out, 'x')
            task_path = out / 'x.M.json'
            if damage == 'missing':
                task_path.unlink()
            else:
                task_path.write_text('{', encoding='utf-8')
            assert l._load_outcome(out, 'x', source) is None, damage
