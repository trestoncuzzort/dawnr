#!/usr/bin/env python3
"""test_ship.py: t/ship.py (programme R4b), the C proved at the width that ships. A routine with no arithmetic ships
for every int32 input; abs's `-x` overflows at INT_MIN and ships within a proved envelope; the envelope is written
into the contract as bounds. Needs Frama-C; skipped when it is absent."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ship  # noqa: E402
import tasks_io  # noqa: E402
import tlib  # noqa: E402
from verifiers import framac  # noqa: E402

needs_framac = pytest.mark.skipif(not framac.FRAMAC, reason="frama-c is not installed")


def test_the_envelope_is_written_as_bounds():
    task = tasks_io.load_task(str(HERE / "tasks" / "abs.t"))
    src = ship._with_envelope(tlib.lower(task, "framac"), task, 20)
    assert "requires -1048576 <= x <= 1048576;" in src


@needs_framac
def test_clamp_ships_for_every_input():
    assert ship.ship_file(str(HERE / "tasks" / "clamp.t"))["status"] == "ships for every int32 input"


@needs_framac
def test_abs_ships_within_an_envelope():
    r = ship.ship_file(str(HERE / "tasks" / "abs.t"))
    assert r["status"] == "ships within ±2^30" and any("rte_signed_overflow" in g for g in r["open"]), r
