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
