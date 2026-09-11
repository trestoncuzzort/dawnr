#!/usr/bin/env python3
"""t/test_surface_errors.py -- ROADMAP 14.2 "Errors with a position",
parse side (2026-09-11).

Parses every .t file in t/malformed/ with surface.parse_file and checks
that it raises a SurfaceError whose `file`, `line`, `col` and `production`
match the row for that file in t/malformed/EXPECTED.tsv (read t/malformed/
EXPECTED.tsv's own header comment for what "production" means and the two
cases where it is a SYNTAX.md heading rather than an EBNF production
name). A file that parses without error, or whose error's fields do not
match, is a failure.

Standard library only. Exit code 0 on success, 1 on any failure; prints
one PASS/FAIL line per file plus a summary.

Measured 2026-09-11: `python3 t/test_surface_errors.py` -- see the command's
own printed summary for the live count, not a number frozen here.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import surface                                                # noqa: E402

MALFORMED_DIR = os.path.join(HERE, "malformed")
MANIFEST = os.path.join(MALFORMED_DIR, "EXPECTED.tsv")


def read_manifest(path: str) -> list:
    """[(file, line, col, production)], skipping the '#'-prefixed header
    comment and the column-name row."""
    rows = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if cols == ["file", "line", "col", "production"]:
                continue
            if len(cols) != 4:
                raise SystemExit("malformed manifest row (want 4 tab-"
                                 "separated columns): %r" % line)
            fname, ln, col, prod = cols
            rows.append((fname, int(ln), int(col), prod))
    return rows


def check_one(fname: str, want_line: int, want_col: int, want_prod: str):
    """Returns None on success, else a string describing the mismatch."""
    path = os.path.join(MALFORMED_DIR, fname)
    if not os.path.isfile(path):
        return "file listed in EXPECTED.tsv does not exist: %s" % path
    try:
        surface.parse_file(path)
    except surface.SurfaceError as exc:
        got = (exc.file, exc.line, exc.col, exc.production)
        want = (path, want_line, want_col, want_prod)
        if got != want:
            return ("mismatch: got file=%r line=%r col=%r production=%r, "
                    "want file=%r line=%r col=%r production=%r"
                    % (got[0], got[1], got[2], got[3],
                       want[0], want[1], want[2], want[3]))
        return None
    return "parsed with no error (expected a SurfaceError)"


def main() -> int:
    rows = read_manifest(MANIFEST)
    if not rows:
        print("EXPECTED.tsv has no rows; nothing to check")
        return 1

    listed = {r[0] for r in rows}
    # wf-*.t (ROADMAP 14.2, well-formedness side, added 2026-09-11): a
    # separate corpus of files that PARSE cleanly and are checked against
    # t/malformed/EXPECTED-WF.tsv by t/test_wf_errors.py instead -- they
    # have no row here by design, not by omission, so they are excluded
    # from this scan rather than counted as coverage gaps.
    on_disk = {f for f in os.listdir(MALFORMED_DIR)
              if f.endswith(".t") and not f.startswith("wf-")}
    extra = sorted(on_disk - listed)
    if extra:
        print("FAIL: .t file(s) in t/malformed/ with no EXPECTED.tsv row: %s"
              % " ".join(extra))

    fails = 0
    for fname, want_line, want_col, want_prod in rows:
        problem = check_one(fname, want_line, want_col, want_prod)
        if problem is None:
            print("PASS  %s" % fname)
        else:
            print("FAIL  %s: %s" % (fname, problem))
            fails += 1

    total = len(rows)
    print("\n%d of %d malformed files raised the expected file/line/col/"
          "production" % (total - fails, total))
    return 1 if (fails or extra) else 0


if __name__ == "__main__":
    sys.exit(main())
