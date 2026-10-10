"""A missing optional-backend launcher is a packaging error on every platform."""
import ast

import py_sandbox


def test_landlock_launcher_is_shipped_and_parses():
    assert py_sandbox.LANDLOCK_EXEC.is_file(), "the advertised Landlock backend needs its launcher"
    ast.parse(py_sandbox.LANDLOCK_EXEC.read_text(encoding="utf-8"))
