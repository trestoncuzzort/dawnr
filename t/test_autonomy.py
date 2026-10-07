#!/usr/bin/env python3
"""test_autonomy.py: the autonomy suite (t/autonomy/, NORTH-STAR.md target 2). Every routine is well-formed, prints
and parses back, has a twin whose witness falsifies its ensures, and hands back to Python agreeing with t; the README
lists every routine. Standard library only, no kernel runs."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_wf  # noqa: E402
import harness  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402
import to_python  # noqa: E402

SUITE = HERE / "autonomy"


def test_every_routine():
    files = sorted(SUITE.glob("*.t"))
    assert len(files) >= 25, len(files)
    readme = (SUITE / "README.md").read_text()
    for f in files:
        t = tasks_io.load_task(str(f))
        assert t["name"] == f.stem, f
        assert check_wf.check_wf(t) == [], (f, check_wf.check_wf(t))
        assert surface.parse(surface.print_task(t)) == t, f
        tw, op, w = harness.twin_for(t)
        assert tw is not None and w.get("_ens") is True, (f, op, w)
        src, fn = to_python.translate(t)
        r = to_python.check(t, src, fn)
        assert r["agrees"], (f, r)
        assert f"| {f.stem} |" in readme, f"{f.stem} is not in the README"


if __name__ == "__main__":
    test_every_routine()
    print("ok")
