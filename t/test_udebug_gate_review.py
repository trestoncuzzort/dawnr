import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Eight findings of the GPT-6 Astra review of 2026-10-13 on the uDebug gate, each reproduced before its fix: a cached verdict is bound to the graded source by hash; a failed lift never reuses an earlier outcome; systemd-run without a user manager falls back to an uncapped run; the judge's paths are absolute; isolation keeps PYTHONHASHSEED; a problem answered in Python and t keeps both kinds of rows; a rejected program is never an accepted text; a case without a stored output counts as skipped.


def test_changed_program_does_not_inherit_cached_acceptance():
    import json
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import udebug_gate as g

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        samples = root / 'samples'
        d = samples / 'uva-1' / 's0'
        d.mkdir(parents=True)
        tests = root / 'tests'
        tests.mkdir()
        (tests / 'a.in.txt').write_text('')
        (tests / 'a.out.txt').write_text('OK\n')
        rec = {'judge': 'uva', 'id': '1', 'sample_index': 0,
               'target': 'python', 'tests_dir': 'tests',
               'messages': [{'role': 'system', 'content': 'Write Python.'},
                            {'role': 'user', 'content': 'Print OK.'}]}
        (d / 'record.json').write_text(json.dumps(rec))
        prog = d / 'p1.py'
        prog.write_text("print('OK')\n")
        cached = {'judge_name': 'uva', 'id': '1', 'k': 0, 'dir': str(d),
                  'parse': 'python', 'proof': 'none', 'verify': None,
                  'judge': {'status': 'pass', 'passed': 1, 'total': 1},
                  'accepted': True}
        (d / 'result.json').write_text(json.dumps(cached))
        prog.write_text("print('WRONG')\n")
        bank = root / 'bank.jsonl'
        bank.write_text(json.dumps({'judge': 'uva', 'id': '1', 'split': 'train'}) + '\n')
        with patch.object(g.shutil, 'which', return_value=None), \
             patch.object(g, '_judge_slot', return_value=None), \
             patch.object(g, '_release_slot'), patch.object(g, 'report'):
            g.main(['--samples', str(samples), '--corpus', str(root), '--bank', str(bank)])
        assert (samples / 'rows.jsonl').read_text() == ''


def test_failed_lift_cannot_reuse_old_artifacts():
    import json
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import udebug_gate as g

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        out = d / 'lift'
        out.mkdir()
        (d / 'p1.dfy').write_text('method p1() returns (r: int) { r := 2; }')
        (out / 'old.json').write_text('{}')
        marker = {'methods': [{'method': 'p1', 'task_file': 'old.json', 'checked': True}]}
        (out / 'p1.outcome.json').write_text(json.dumps(marker))
        with patch.object(g, 'run', return_value=(1, 'lifter failed before writing outputs')), \
             patch.object(g.spec_experiment, 'rename_task', return_value={}), \
             patch.object(g.surface, 'print_task', return_value='OLD_TASK'):
            result = g.lift_dafny(d, '1', 10)
        assert result['status'] != 'lifted'
        assert not (d / 'p1.t').exists()


def test_installed_systemd_without_user_manager_falls_back():
    import subprocess
    import sys
    from pathlib import Path
    from unittest.mock import patch
    import udebug_gate as g

    def execute(cmd, **kwargs):
        if cmd[0] == 'systemd-run':
            return subprocess.CompletedProcess(cmd, 1, '', 'Failed to connect to bus: No medium found\n')
        return subprocess.CompletedProcess(cmd, 0, '42\n', '')

    with patch.object(g.shutil, 'which', return_value='/usr/bin/systemd-run'), \
         patch.object(g, '_judge_slot', return_value=None), \
         patch.object(g, '_release_slot'), \
         patch.object(g.subprocess, 'run', side_effect=execute):
        result = g.run([sys.executable, '-c', 'print(42)'], 5, Path.cwd())
    assert result == (0, '42\n')


def test_judge_preserves_relative_path_meaning():
    import os
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import udebug_gate as g

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp).resolve()
        (work / 'p1.t').write_text('task supplied by caller')
        (work / 'p1_io.py').write_text('')
        (work / 'tests').mkdir()
        previous = Path.cwd()
        try:
            os.chdir(work)
            with patch.object(g, 'run', return_value=(0, "1/1 test files match the judge's output\n")) as runner:
                g.judge(Path('p1.t'), Path('p1_io.py'), Path('tests'), 5)
            cmd, timeout, child_cwd = runner.call_args.args
            assert (Path(child_cwd) / cmd[2]).resolve() == work / 'p1.t'
            assert (Path(child_cwd) / cmd[cmd.index('--tests') + 1]).resolve() == work / 'tests'
        finally:
            os.chdir(previous)


def test_judge_python_honors_hash_seed():
    import os
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import udebug_gate as g

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        prog = root / 'p1.py'
        prog.write_text('import sys\nprint(sys.flags.hash_randomization)\n')
        tests = root / 'tests'
        tests.mkdir()
        (tests / 'a.in.txt').write_text('')
        (tests / 'a.out.txt').write_text('0\n')
        env = dict(os.environ, PYTHONHASHSEED='0')
        with patch.object(g.shutil, 'which', return_value=None), \
             patch.object(g, '_judge_slot', return_value=None), \
             patch.object(g, '_release_slot'):
            result = g.judge_python(prog, tests, 5, env=env)
        assert result['status'] == 'pass', result


def test_mixed_targets_keep_accepted_t_rows():
    import json
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import udebug_gate as g

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        td, pd = root / 's0', root / 's1'
        td.mkdir()
        pd.mkdir()
        (td / 'p1.t').write_text('T_TASK')
        (td / 'p1_io.py').write_text('')
        (td / 'record.json').write_text(json.dumps({'messages': [{'content': 'Statement.\nWrite the t task p1.'}]}))
        (pd / 'p1.py').write_text('print(0)\n')
        accepted = {'judge_name': 'uva', 'id': '1', 'k': 0, 'dir': str(td),
                    'parse': 'ok', 'accepted': True,
                    'judge': {'status': 'pass', 'passed': 1, 'total': 1},
                    'verify': {'counted': ['dafny']}}
        failed_python = {'judge_name': 'uva', 'id': '1', 'k': 1, 'dir': str(pd),
                         'parse': 'python', 'proof': 'none', 'accepted': False,
                         'judge': {'status': 'fail', 'passed': 0, 'total': 1}, 'verify': None}
        with patch.object(g.surface, 'parse_file', return_value={}), \
             patch.object(g.surface, 'print_task', return_value='T_TASK'), \
             patch.object(g.student_rows, 'row_for', return_value={}):
            rows, pairs, skipped = g.build_rows([accepted, failed_python], {'uva/1': {'split': 'train'}}, 4, 4)
        assert any(row['kind'] == 'statement-given' for row in rows)
        assert any(row['kind'] == 'spec-given' for row in rows)


def test_python_pairs_never_prefer_text_over_itself():
    import json
    import tempfile
    from pathlib import Path
    import udebug_gate as g

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        results = []
        code = 'import random\nprint(random.randrange(2))\n'
        for k, accepted in enumerate([False, True]):
            d = root / f's{k}'
            d.mkdir()
            (d / 'p1.py').write_text(code)
            (d / 'record.json').write_text(json.dumps({'messages': [
                {'content': 'Write Python.'}, {'content': 'Print 1.'}]}))
            results.append({'id': '1', 'k': k, 'dir': str(d), 'accepted': accepted,
                            'judge': {'status': 'pass' if accepted else 'fail',
                                      'passed': int(accepted), 'total': 1,
                                      'case': 'a.in.txt',
                                      'first_difference': None if accepted else "line 1: got '0' want '1'"}})
        rows, pairs = [], []
        g.python_rows('uva/1', results, rows, pairs, 4, 4,
                      {'duplicate-chosen': 0, 'over-cap': 0})
        assert all(pair['chosen'] != pair['rejected'] for pair in pairs), pairs


def test_missing_outputs_are_excluded_from_judged_total():
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import udebug_gate as g

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        prog = root / 'p1.py'
        prog.write_text("print('OK')\n")
        tests = root / 'tests'
        tests.mkdir()
        (tests / 'a.in.txt').write_text('')
        (tests / 'a.out.txt').write_text('OK\n')
        (tests / 'b.in.txt').write_text('')
        with patch.object(g, 'run', return_value=(0, 'OK\n', '')):
            result = g.judge_python(prog, tests, 5)
        assert (result['status'], result['passed'], result['total'], result['skipped']) == ('pass', 1, 1, 1)
