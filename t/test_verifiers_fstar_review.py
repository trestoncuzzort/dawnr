import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Eight findings of the GPT-6 Astra review of 2026-10-13 on the F* adapter, each reproduced before its fix.


def test_certificate_cannot_use_an_admitted_lemma():
    import json
    import subprocess
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import t.verifiers.fstar as f

    source = ('module C\n'
              'let failed () : Lemma False = ()\n'
              'let t_refutation_certificate () : Lemma False = failed ()\n')
    # These are the two kernel results: ordinary checking fails, while
    # admitting failed makes the dependent certificate discharge.
    responses = [
        subprocess.CompletedProcess([], 1, '', json.dumps({
            'level': 'Error', 'number': 19,
            'msg': ['Failed to prove: Prims.l_False']})),
        subprocess.CompletedProcess([], 0, f._OK_LINE + '\n', '')]
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'C.fst'
        path.write_text(source)
        with patch.object(f, 'FSTAR', 'fstar'), patch.object(f, 'version', return_value='test'), patch.object(f, 'run_tree', side_effect=responses):
            result = f.verify(path)
    assert result.outcome != f.Outcome.REFUTED


def test_commented_certificate_cannot_refute():
    import json
    import subprocess
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import t.verifiers.fstar as f

    source = ('module C\n'
              'let failed () : Lemma False = ()\n'
              '(*\nlet t_refutation_certificate () : Lemma True = ()\n*)\n')
    responses = [
        subprocess.CompletedProcess([], 1, '', json.dumps({
            'level': 'Error', 'number': 19,
            'msg': ['Failed to prove: Prims.l_False']})),
        subprocess.CompletedProcess([], 0, f._OK_LINE + '\n', '')]
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'C.fst'
        path.write_text(source)
        with patch.object(f, 'FSTAR', 'fstar'), patch.object(f, 'version', return_value='test'), patch.object(f, 'run_tree', side_effect=responses):
            result = f.verify(path)
    assert result.outcome == f.Outcome.UNPROVED


def test_verdict_hash_binds_the_checked_snapshot():
    import hashlib
    import subprocess
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import t.verifiers.fstar as f

    original = b'module Race\nlet p (x:int) : Lemma (x + 1 < x) = ()\n'
    replacement = b'module Race\nlet p (x:int) : Lemma (x + 1 > x) = ()\n'
    checked = {}

    def hash_then_replace(path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.write_bytes(replacement)
        return digest

    def kernel(argv, **kwargs):
        cwd = Path(kwargs['cwd'])
        checked['bytes'] = (cwd / argv[-1]).read_bytes()
        (cwd / 'queries-Race.smt2').write_text('; STATUS: unsat\n')
        return subprocess.CompletedProcess(argv, 0, f._OK_LINE + '\n', '')

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'Race.fst'
        path.write_bytes(original)
        with patch.object(f, 'FSTAR', 'fstar'), patch.object(f, 'version', return_value='test'), patch.object(f, 'sha256_file', side_effect=hash_then_replace), patch.object(f, 'run_tree', side_effect=kernel), patch.object(f, 'Result') as result:
            f.verify(path)
            reported_hash = result.call_args.args[2]
    assert reported_hash == hashlib.sha256(checked['bytes']).hexdigest()


def test_crashed_vacuity_probe_is_not_a_discharge():
    import json
    import subprocess
    from unittest.mock import patch
    import t.verifiers.fstar as f

    source = ('module V\nlet f (x:int)\n'
              '  : Pure int\n'
              '    (requires True)\n'
              '    (ensures (fun r -> r == x))\n'
              '  = x\n')
    responses = [
        subprocess.CompletedProcess([], 1, '', json.dumps({
            'level': 'Error', 'number': 19,
            'msg': ['Failed to prove: Prims.l_False']})),
        subprocess.CompletedProcess([], -11, '', '')]
    with patch.object(f, 'FSTAR', 'fstar'), patch.object(f, 'run_tree', side_effect=responses):
        status, detail = f._probe_vacuity(source, 'V', 50)
    assert status == 'unusable', (status, detail)


def test_timed_out_vacuity_probe_is_undecided():
    import json
    import subprocess
    from unittest.mock import patch
    import t.verifiers.fstar as f

    source = ('module V\nlet f (x:int)\n'
              '  : Pure int\n'
              '    (requires True)\n'
              '    (ensures (fun r -> r == x))\n'
              '  = x\n')
    def failure(message):
        return subprocess.CompletedProcess([], 1, '', json.dumps({
            'level': 'Error', 'number': 19, 'msg': [message]}))
    responses = [
        failure('Failed to prove: Prims.l_False'),
        failure('Failed to prove: Prims.l_False\nThe SMT solver timed out')]
    with patch.object(f, 'FSTAR', 'fstar'), patch.object(f, 'run_tree', side_effect=responses):
        status, detail = f._probe_vacuity(source, 'V', 1)
    assert status == 'unusable', (status, detail)


def test_single_line_false_precondition_is_not_clean():
    from unittest.mock import patch
    import t.verifiers.fstar as f

    source = ('module V\n'
              'let f (x:int) : Pure int (requires False) '
              '(ensures (fun _ -> False)) = 0\n')
    with patch.object(f, '_run_vacuity_file', side_effect=[
            ['Failed to prove: Prims.l_False'], []]):
        status, detail = f._probe_vacuity(source, 'V', 50)
    assert status != 'clean', (status, detail)


def test_missing_input_returns_tool_error():
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import t.verifiers.fstar as f

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'missing.fst'
        with patch.object(f, 'FSTAR', 'fstar'), patch.object(f, 'version', return_value='test'):
            result = f.verify(path)
    assert result.outcome == f.Outcome.TOOL_ERROR


def test_commented_module_does_not_choose_filename():
    import subprocess
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import t.verifiers.fstar as f

    source = ('(*\nmodule Old\n*)\nmodule Real\n'
              'let p (x:int) : Lemma (x + 1 > x) = ()\n')
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'Real.fst'
        path.write_text(source)
        with patch.object(f, 'FSTAR', 'fstar'), patch.object(f, 'version', return_value='test'), patch.object(f, 'run_tree', return_value=subprocess.CompletedProcess([], 1, '', '')) as run:
            f.verify(path)
    assert run.call_args.args[0][-1] == 'Real.fst'
