#!/usr/bin/env python3
"""test_verify_names.py: `cli.py verify DIR` refuses a directory in which two files declare one task name (2026-10-06).
A table row and every lowered file (harness.OUT/<name>.<suffix>) are keyed by the declared name, so two such tasks
would overwrite each other's sources while both run and leave one row for two tasks; AlgoVeri's polymul_naive and
polymul_karatsuba both declared poly_multiply. The refusal comes before any kernel is probed or anything lowered."""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cli  # noqa: E402

TASK = """t 1
task {name}(x: int) returns (r: int)
  ensures r == x + {k}
{{
  r := x + {k};
}}
"""


def test_two_files_one_name_is_refused():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "first.t").write_text(TASK.format(name="same", k=1))
        Path(d, "second.t").write_text(TASK.format(name="same", k=2))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = cli.main(["verify", d, "--table", str(Path(d, "T.md"))])
        assert rc == 2, rc
        assert "2 files declare the task name same (first.t, second.t)" in err.getvalue(), err.getvalue()
        assert not Path(d, "T.md").exists()


if __name__ == "__main__":
    test_two_files_one_name_is_refused()
    print("test_two_files_one_name_is_refused: ok")
