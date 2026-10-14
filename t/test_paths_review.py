import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

# Seven findings of the GPT-6 Astra review of 2026-10-13 on state paths, each reproduced before its fix: an unknown home falls back to a temporary root; a tilde XDG base is ignored; an override keeps significant whitespace; an inaccessible candidate is rejected; a failed probe removes the directory it created; an override's parent is created; the probe never writes through a symlink.


def test_override_parent_is_created():
    import os
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import paths

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / 'new' / 'events.jsonl'
        with patch.dict(os.environ, {'T_TEST_PATHS_OVERRIDE': str(target)}):
            result = paths.state_path('T_TEST_PATHS_OVERRIDE', 'watch', 'events.jsonl')
        assert result == target
        assert result.parent.is_dir()


def test_probe_does_not_overwrite_symlink_target():
    import os
    import tempfile
    import unittest
    from pathlib import Path
    import paths

    if os.name != 'posix':
        raise unittest.SkipTest('POSIX symlink test')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        candidate = root / 'state'
        candidate.mkdir()
        events = root / 'events.jsonl'
        events.write_text('saved events\n', encoding='utf-8')
        probe = candidate / f'.locallm-write-probe-{os.getpid()}'
        probe.symlink_to(events)
        paths.writable(candidate)
        assert events.read_text(encoding='utf-8') == 'saved events\n'
        assert probe.is_symlink()


def test_inaccessible_candidate_is_rejected():
    import errno
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import paths

    with tempfile.TemporaryDirectory() as tmp:
        candidate = Path(tmp) / 'inaccessible' / 'state'
        error = PermissionError(errno.EACCES, 'Permission denied', str(candidate))
        with patch.object(Path, 'is_dir', side_effect=error):
            assert paths.writable(candidate) is False


def test_unknown_home_uses_temporary_fallback():
    import os
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import paths

    with tempfile.TemporaryDirectory() as tmp:
        program = Path(tmp) / 'not-a-directory'
        program.write_text('occupied', encoding='utf-8')
        emergency = Path(tmp) / 'emergency'
        emergency.mkdir()
        paths.state_root.cache_clear()
        try:
            with patch.dict(os.environ, {'XDG_STATE_HOME': '', 'LOCALAPPDATA': ''}), \
                 patch.object(Path, 'home', side_effect=RuntimeError('Could not determine home directory.')), \
                 patch.object(paths.tempfile, 'mkdtemp', return_value=str(emergency)):
                assert paths.state_root(program=program) == emergency
        finally:
            paths.state_root.cache_clear()


def test_failed_probe_removes_new_directory():
    import errno
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import paths

    def disk_full_after_creation(file, *args, **kwargs):
        file.touch()
        raise OSError(errno.ENOSPC, 'No space left on device')

    with tempfile.TemporaryDirectory() as tmp:
        candidate = Path(tmp) / 'state'
        with patch.object(Path, 'write_text', disk_full_after_creation):
            assert paths.writable(candidate) is False
        assert not candidate.exists()


def test_tilde_xdg_base_is_ignored():
    import os
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import paths

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with patch.dict(os.environ, {'XDG_CACHE_HOME': '~/cache'}), \
             patch.object(paths, 'state_root', return_value=root):
            result = paths.state_path('XDG_CACHE_HOME', 'geometry', env_join=('t-lab', 'geometry'))
        assert result == root / 'geometry'


def test_override_preserves_significant_whitespace():
    import os
    import tempfile
    import unittest
    from pathlib import Path
    from unittest.mock import patch
    import paths

    if os.name != 'posix':
        raise unittest.SkipTest('POSIX filename semantics')
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / 'events.jsonl '
        with patch.dict(os.environ, {'T_TEST_PATHS_OVERRIDE': str(target)}):
            result = paths.state_path('T_TEST_PATHS_OVERRIDE', 'watch', 'events.jsonl')
        assert result == target
