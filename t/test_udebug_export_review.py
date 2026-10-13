import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Six findings of the review on the export, each reproduced before its fix: a lane's provider is read from its first readable record; the exported bytes are the bytes every seed run judged; no seeds is a named refusal with nothing written; a cached solution from an excluded provider is dropped wherever its lane lives; --only-new keeps only an entry whose program is present; a confirmed solution beyond --limit stands.


def test_malformed_first_record_does_not_hide_excluded_provider():
    import json
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import udebug_export as ux

    with tempfile.TemporaryDirectory() as d:
        lane = Path(d) / 'teacher-openai'
        first = lane / 'UVa-100' / 's1'
        second = lane / 'UVa-100' / 's2'
        first.mkdir(parents=True)
        second.mkdir(parents=True)
        (first / 'record.json').write_text('{')
        (second / 'record.json').write_text(json.dumps({'provider': 'openai'}))
        (second / 'result.json').write_text(json.dumps({
            'judge_name': 'UVa', 'id': '100', 'parse': 'python',
            'accepted': True, 'judge': {'status': 'pass'}
        }))
        original_glob = Path.glob
        def ordered_glob(path, pattern):
            return iter(sorted(original_glob(path, pattern)))
        excluded = set()
        with patch.object(Path, 'glob', ordered_glob):
            found = ux.scan_lanes([str(lane)], excluded)
        assert not found
        assert excluded == {'teacher-openai'}


def test_confirm_does_not_export_unchecked_replacement():
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import udebug_export as ux

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        sample = root / 'sample'
        sample.mkdir()
        prog = sample / 'p100.py'
        original = b'print(1)'
        prog.write_bytes(original)
        calls = 0
        def grade(*args, **kwargs):
            nonlocal calls
            assert prog.read_bytes() == original
            calls += 1
            # Model a writer replacing the source after the final check.
            if calls == 2:
                prog.write_bytes(b'print(2)')
            return {'status': 'pass', 'passed': 1, 'total': 1,
                    'skipped': 0, 'max_case_s': 0.01}
        candidate = {'sample_dir': str(sample), 'lane': 'teacher',
                     'judge': {'status': 'pass', 'max_case_s': 0.01}}
        with patch.object(ux.ug, 'judge_python', side_effect=grade):
            entry = ux.confirm(('UVa', '100'), {'tests_dir': '.', 'n_scored': 1},
                               [candidate], root, root / 'out', [0, 4242], 1.0)
        assert entry['status'] != 'solved' or Path(entry['solution']).read_bytes() == original


def test_empty_seeds_leave_no_unconfirmed_submission():
    import tempfile
    from pathlib import Path
    import udebug_export as ux

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        sample = root / 'sample'
        sample.mkdir()
        (sample / 'p100.py').write_text('print(1)')
        candidate = {'sample_dir': str(sample), 'lane': 'teacher',
                     'judge': {'status': 'pass'}}
        out = root / 'out'
        try:
            ux.confirm(('UVa', '100'), {'tests_dir': '.'},
                       [candidate], root, out, [], 1.0)
        except ValueError:
            pass
        assert not (out / 'UVa' / '100.py').exists()


def test_unscanned_openai_cache_is_not_retained():
    import json
    import tempfile
    from pathlib import Path
    import udebug_export as ux

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        sample = root / 'teacher-openai' / 'UVa-100' / 's1'
        sample.mkdir(parents=True)
        (sample / 'record.json').write_text(json.dumps({'provider': 'openai'}))
        bank = root / 'bank.jsonl'
        bank.write_text(json.dumps({'judge': 'UVa', 'id': '100',
                                   'statement': 'S', 'n_scored': 1, 'tests_dir': '.'}))
        out = root / 'out'
        dest = out / 'UVa'
        dest.mkdir(parents=True)
        solution = dest / '100.py'
        solution.write_text('print(1)')
        entry = {'judge': 'UVa', 'id': '100', 'status': 'solved',
                 'lane': 'teacher-openai', 'sample_dir': str(sample),
                 'solution': str(solution), 'cases': 1, 'max_case_s': 0.01}
        (dest / '100.json').write_text(json.dumps(entry))
        (out / 'INDEX.jsonl').write_text(json.dumps(entry))
        ux.main(['--bank', str(bank), '--corpus', str(root), '--out', str(out),
                 '--lanes', str(root / 'teacher-allowed-*'), '--only-new'])
        current = json.loads((out / 'INDEX.jsonl').read_text())
        assert current['status'] != 'solved'
        assert not solution.exists()


def test_only_new_does_not_report_missing_program_as_solved():
    import json
    import tempfile
    from pathlib import Path
    import udebug_export as ux

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        bank = root / 'bank.jsonl'
        bank.write_text(json.dumps({'judge': 'UVa', 'id': '100',
                                   'statement': 'S', 'n_scored': 1, 'tests_dir': '.'}))
        out = root / 'out'
        dest = out / 'UVa'
        dest.mkdir(parents=True)
        solution = dest / '100.py'
        entry = {'judge': 'UVa', 'id': '100', 'status': 'solved',
                 'lane': 'teacher-allowed', 'sample_dir': str(root / 'old-sample'),
                 'solution': str(solution), 'cases': 1, 'max_case_s': 0.01}
        (dest / '100.json').write_text(json.dumps(entry))
        (out / 'INDEX.jsonl').write_text(json.dumps(entry))
        ux.main(['--bank', str(bank), '--corpus', str(root), '--out', str(out),
                 '--lanes', str(root / 'nonexistent-*'), '--only-new'])
        current = json.loads((out / 'INDEX.jsonl').read_text())
        assert current['status'] != 'solved' or solution.is_file()


def test_limited_upgrade_preserves_existing_solution():
    import json
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import udebug_export as ux

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        bank = root / 'bank.jsonl'
        records = [{'judge': 'UVa', 'id': ident, 'statement': 'S',
                    'n_scored': 1, 'tests_dir': '.'} for ident in ('100', '200')]
        bank.write_text('\n'.join(json.dumps(r) for r in records))
        out = root / 'out'
        dest = out / 'UVa'
        dest.mkdir(parents=True)
        solution = dest / '200.py'
        solution.write_text('print(1)')
        previous = {'judge': 'UVa', 'id': '200', 'status': 'solved',
                    'lane': 'old', 'sample_dir': str(root / 'old200'),
                    'solution': str(solution), 'cases': 1, 'max_case_s': 1.0}
        (dest / '200.json').write_text(json.dumps(previous))
        (out / 'INDEX.jsonl').write_text(json.dumps(previous))
        def accepted(ident, lane, elapsed):
            return {'judge_name': 'UVa', 'id': ident, 'parse': 'python',
                    'accepted': True, 'lane': lane, 'sample_dir': str(root / (lane + ident)),
                    'judge': {'status': 'pass', 'max_case_s': elapsed}}
        results = {('UVa', '100'): [accepted('100', 'new', 0.1)],
                   ('UVa', '200'): [accepted('200', 'old', 1.0), accepted('200', 'new', 0.1)]}
        first_result = {'judge': 'UVa', 'id': '100',
                        'status': 'accepted-but-not-confirmed', 'attempts': []}
        with patch.object(ux, 'scan_lanes', return_value=results), patch.object(ux, 'confirm', return_value=first_result):
            ux.main(['--bank', str(bank), '--corpus', str(root), '--out', str(out),
                     '--lanes', 'unused', '--only-new', '--limit', '1'])
        assert solution.is_file()
        entries = [json.loads(line) for line in (out / 'INDEX.jsonl').read_text().splitlines()]
        assert next(e for e in entries if e['id'] == '200')['status'] == 'solved'
