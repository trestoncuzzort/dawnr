"""t/blockers.py: the per-kernel and sole-blocker sections of an agreement table, rendered from cells."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import blockers  # noqa: E402
def test_an_internal_flake_marker_cannot_create_a_refutation():
    """Named by the GPT-6 Astra review of 2026-10-13: only the trailing "(FLAKED)" marker is normalized; a marker
    inside a verdict word leaves the cell unrecognized, never 'refuted'."""
    section = blockers.render_kernels(["Lean", "Rocq"], {"task": {"Lean": "verified / re (FLAKED)futed", "Rocq": blockers.COUNTS}})
    assert "| Lean | 1 | 1 | 0 of 1 (0%) | 0 |" in section
    assert "Verified with the twin refuted in all two columns: 0 of 1 tasks." in section


# --- from the GPT-6 Astra review of 2026-10-13: each reproduced before the fix ---


def test_replace_preserves_following_level_one_section():
    from blockers import _replace_or_append
    tail = '# Appendix\n\nKeep this content.\n'
    original = '## Sole blockers\n\nOld report.\n\n' + tail
    replacement = '## Sole blockers\n\nNew report.\n'
    result = _replace_or_append(original, replacement, True)
    assert result.endswith(tail)


def test_parse_empty_final_cell_without_padding():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from blockers import COUNTS, parse_table
    with TemporaryDirectory() as directory:
        path = Path(directory) / 'table.md'
        path.write_text(
            '| task | Lean | Rocq |\n'
            '|---|---|---|\n'
            '| first | verified / refuted ||\n'
            '| later | verified / refuted | verified / refuted |\n',
            encoding='utf-8',
        )
        columns, rows = parse_table(path)
    assert columns == ['Lean', 'Rocq']
    assert rows == {
        'first': {'Lean': COUNTS, 'Rocq': ''},
        'later': {'Lean': COUNTS, 'Rocq': COUNTS},
    }


def test_parse_escaped_pipe_in_cell():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from blockers import parse_table
    cell = r'abstain(x\|y) / abstain'
    with TemporaryDirectory() as directory:
        path = Path(directory) / 'table.md'
        path.write_text(
            '| task | Lean | Rocq |\n'
            '|---|---|---|\n'
            f'| first | {cell} | verified / refuted |\n'
            '| later | verified / refuted | verified / refuted |\n',
            encoding='utf-8',
        )
        _, rows = parse_table(path)
    assert 'later' in rows
    assert rows['first']['Lean'] == cell


def test_single_column_zero_count_has_no_blockers():
    from blockers import analyze
    report = analyze(
        ['Lean'],
        {'unsupported': {'Lean': 'abstain / abstain'}},
    )
    assert report['sole'] == {'Lean': 0}
    assert report['sole_tasks'] == {'Lean': []}
    assert report['co'] == {'Lean': 0}
