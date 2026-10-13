import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Five findings of the GPT-6 Astra review of 2026-10-13 on the Agda adapter, each reproduced before its fix.


def test_killed_agda_is_not_a_refutation():
    import subprocess
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    from verifiers import agda

    with tempfile.TemporaryDirectory() as td:
        source = Path(td) / 'T_Unit.agda'
        source.write_text('module T_Unit where\n', encoding='utf-8')
        killed = subprocess.CompletedProcess(['agda'], -9, '', '')
        with patch.object(agda, 'AGDA', '/fake/agda'), \
             patch.object(agda, 'run_tree', return_value=killed), \
             patch.object(agda, 'version', return_value='Agda version 2.8.0'):
            result = agda.verify(source)
        assert result.outcome == agda.Outcome.TOOL_ERROR


def test_verdict_hash_binds_the_checked_snapshot():
    import hashlib
    import subprocess
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    from verifiers import agda

    bad = b'module T_Unit where\nbad : Set\nbad = Set\n'
    good = b'module T_Unit where\n'
    checked = []

    def hash_then_replace(path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.write_bytes(good)  # Deterministic interleaving with another writer.
        return digest

    def kernel(argv, **kwargs):
        unit = Path(kwargs['cwd']) / 'T_Unit.agda'
        checked.append(unit.read_text(encoding='utf-8').encode('utf-8'))
        return subprocess.CompletedProcess(argv, 0, '', '')

    with tempfile.TemporaryDirectory() as td:
        source = Path(td) / 'T_Unit.agda'
        source.write_bytes(bad)
        with patch.object(agda, 'AGDA', '/fake/agda'), \
             patch.object(agda, 'sha256_file', side_effect=hash_then_replace), \
             patch.object(agda, 'run_tree', side_effect=kernel), \
             patch.object(agda, 'version', return_value='Agda version 2.8.0'), \
             patch.object(agda, 'Result') as result_constructor:
            agda.verify(source)
            recorded_hash = result_constructor.call_args.args[2]
        assert recorded_hash == hashlib.sha256(checked[0]).hexdigest()


def test_leading_comment_preserves_module_filename_consistency():
    import subprocess
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    from verifiers import agda

    def kernel(argv, **kwargs):
        unit = Path(kwargs['cwd']) / argv[-1]
        submitted = unit.read_text(encoding='utf-8')
        assert f'module {unit.stem} where' in submitted
        return subprocess.CompletedProcess(argv, 0, '', '')

    with tempfile.TemporaryDirectory() as td:
        source = Path(td) / 'Original.agda'
        source.write_text('-- Generated file\nmodule Original where\n', encoding='utf-8')
        with patch.object(agda, 'AGDA', '/fake/agda'), \
             patch.object(agda, 'run_tree', side_effect=kernel), \
             patch.object(agda, 'version', return_value='Agda version 2.8.0'):
            agda.verify(source)


def test_comment_does_not_make_safe_source_vacuous():
    import subprocess
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    from verifiers import agda

    with tempfile.TemporaryDirectory() as td:
        source = Path(td) / 'T_Unit.agda'
        source.write_text('module T_Unit where\n-- This file uses no postulate.\n', encoding='utf-8')
        accepted = subprocess.CompletedProcess(['agda'], 0, '', '')
        with patch.object(agda, 'AGDA', '/fake/agda'), \
             patch.object(agda, 'run_tree', return_value=accepted), \
             patch.object(agda, 'version', return_value='Agda version 2.8.0'):
            result = agda.verify(source)
        assert result.outcome == agda.Outcome.VERIFIED


def test_missing_agda_is_a_named_refusal():
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    from verifiers import agda

    with tempfile.TemporaryDirectory() as td:
        source = Path(td) / 'T_Unit.agda'
        source.write_text('module T_Unit where\n', encoding='utf-8')
        launch_error = FileNotFoundError(2, 'No such file or directory', 'None')
        with patch.object(agda, 'AGDA', None), \
             patch.object(agda, '_AGDA_WHY', 'agda unavailable; configure T_AGDA'), \
             patch.object(agda, 'run_tree', side_effect=launch_error):
            try:
                result = agda.verify(source)
            except SystemExit as exc:
                assert 'agda' in str(exc).lower()
            else:
                assert result.outcome == agda.Outcome.TOOL_ERROR
