#!/usr/bin/env python3
"""test_build.py: t/build.py (programme R4), the proven lowerings compiled and run against the interpreter. The C
harness reads the lowering's own signature (data, lengths, result and scratch buffers, renamed keywords); a C
build agrees with the interpreter inside int32, and a disagreement beyond it is classed as C's integer width, not a
lowering bug. Needs gcc; the Dafny target is skipped when dafny is absent."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build  # noqa: E402

needs_gcc = pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")


def run(name: str, target: str = "c") -> dict:
    return build.build_file(str(HERE / "tasks" / f"{name}.t"), target)


@needs_gcc
def test_a_scalar_routine_agrees():
    r = run("gcd")
    assert r["status"] == "agrees" and r["points"] > 0, r


@needs_gcc
def test_a_sequence_result_comes_back_in_its_buffer():
    r = run("reverse")
    assert r["status"] == "agrees", r


@needs_gcc
def test_a_sequence_local_gets_its_scratch_buffer():
    r = run("doubled_head")
    assert r["status"] in ("agrees", "agrees within int32"), r


@needs_gcc
def test_an_array_written_in_place_is_read_back():
    r = run("clamp_all")
    assert r["status"] in ("agrees", "agrees within int32"), r


@needs_gcc
def test_a_renamed_keyword_parameter_is_mapped_back():
    r = run("probe_names_framac")
    assert r["status"] in ("agrees", "agrees within int32"), r


@needs_gcc
def test_c_int_width_is_named_not_counted_as_a_lowering_bug():
    narrow, wide = run("clamp"), run("clamp", "c64")
    assert narrow["status"] == "agrees within int32" and narrow["beyond_int32"] > 0, narrow
    assert wide["status"] == "agrees", wide


def test_a_type_the_harness_does_not_build_is_named():
    r = build.build_file(str(HERE / "tasks" / "color_code.t"), "c")
    assert r["status"].startswith("not built"), r


@pytest.mark.skipif(build.DAFNY is None, reason="dafny is not installed")
def test_dafny_python_agrees():
    r = run("reverse", "dafny-py")
    assert r["status"] == "agrees", r
