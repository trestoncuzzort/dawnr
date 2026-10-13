import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Five findings of the review on the teacher, each reproduced before its fix: a slow index that qualifies nothing selects nothing; a transient failure while refreshing the Vertex token is retried; a truncated record.json is redone, not skipped; a closing fence is a line of its own; a hint is quoted whole or not at all.


def test_slow_index_with_no_slow_entries_selects_nothing():
    import json
    import tempfile
    from pathlib import Path
    import udebug_teacher as m

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        bank = root / 'bank.jsonl'
        rec = dict(judge='UVa', id='1', statement='Print 42.',
                   sample_in='', sample_out='42\n', tests_dir='tests',
                   io_shape='int', split='train', hand_solved=False,
                   in_bytes=0, n_scored=1)
        bank.write_text(json.dumps(rec) + '\n', encoding='utf-8')
        index = root / 'INDEX.jsonl'
        index.write_text(json.dumps(dict(judge='UVa', id='1', status='solved',
                                         max_case_s=1.0)) + '\n', encoding='utf-8')
        out = root / 'out'
        m.main(['--bank', str(bank), '--exemplars', str(root), '--tag', 'test',
                '--target', 'python', '--out', str(out), '--slow-index', str(index),
                '--slow-above', '2', '--dry-run'])
        assert not list(out.rglob('prompt.json')), 'No problem qualifies for a speed-up'


def test_vertex_retries_transient_token_refresh_failure():
    import io
    import json
    import os
    import tempfile
    import urllib.error
    from pathlib import Path
    from unittest.mock import patch
    import udebug_teacher as m

    with tempfile.TemporaryDirectory() as td:
        adc = Path(td) / 'adc.json'
        adc.write_text(json.dumps(dict(client_id='id', client_secret='secret',
                                       refresh_token='refresh')), encoding='utf-8')
        responses = [
            urllib.error.URLError('temporary DNS failure'),
            io.BytesIO(b'{"access_token":"token","expires_in":3600}'),
            io.BytesIO(b'{"choices":[{"message":{"content":"ok"}}]}'),
        ]
        with patch.dict(os.environ, {'GOOGLE_OAUTH_ACCESS_TOKEN': ''}), \
             patch('urllib.request.urlopen', side_effect=responses), \
             patch.object(m.time, 'sleep'):
            result = m.vertex_call('https://example.invalid/completions',
                                   m.VertexToken(str(adc)), 'model', [], 16, 0.0,
                                   max_attempts=2)
        assert result == ('ok', 0, 0, None)


def test_resume_does_not_silently_skip_truncated_record():
    import json
    import tempfile
    from pathlib import Path
    import udebug_teacher as m

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        bank = root / 'bank.jsonl'
        rec = dict(judge='UVa', id='1', statement='Print 42.',
                   sample_in='', sample_out='42\n', tests_dir='tests',
                   io_shape='int', split='train', hand_solved=False,
                   in_bytes=0, n_scored=1)
        bank.write_text(json.dumps(rec) + '\n', encoding='utf-8')
        out = root / 'out'
        sample = out / 'UVa-1' / 's1'
        sample.mkdir(parents=True)
        (sample / 'record.json').write_text('{', encoding='utf-8')
        try:
            rc = m.main(['--bank', str(bank), '--exemplars', str(root),
                         '--tag', 'test', '--target', 'python', '--out', str(out),
                         '--dry-run'])
        except (ValueError, SystemExit):
            return  # Explicit rejection of the corrupt record is also acceptable.
        assert rc != 0 or (sample / 'prompt.json').is_file(), \
            'A corrupt record must not silently suppress the unfinished sample'


def test_extract_preserves_backticks_inside_python_string():
    import udebug_teacher as m

    program = 'print("```")\n'
    reply = '```python\n' + program + '```\n'
    assert m.extract(reply, 'python') == (program, program)


def test_python_hint_is_not_silently_truncated():
    import json
    import tempfile
    from pathlib import Path
    import udebug_teacher as m

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        bank = root / 'bank.jsonl'
        rec = dict(judge='UVa', id='1', statement='Print 42.',
                   sample_in='', sample_out='42\n', tests_dir='tests',
                   io_shape='int', split='train', hand_solved=False,
                   in_bytes=0, n_scored=1)
        bank.write_text(json.dumps(rec) + '\n', encoding='utf-8')
        bundle = root / 'solutions'
        (bundle / 'UVa').mkdir(parents=True)
        program = '# comment\n' * 1300 + 'print(42)\n'
        (bundle / 'UVa' / '1.py').write_text(program, encoding='utf-8')
        out = root / 'out'
        m.main(['--bank', str(bank), '--exemplars', str(root),
                '--exemplar-names', '', '--tag', 'test', '--target', 'dafny',
                '--out', str(out), '--python-hint-from', str(bundle), '--dry-run'])
        messages = json.loads((out / 'UVa-1' / 's1' / 'prompt.json').read_text())
        assert program.rstrip() in messages[1]['content'], \
            'The purported accepted program has lost its executable suffix'
