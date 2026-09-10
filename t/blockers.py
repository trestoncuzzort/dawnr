#!/usr/bin/env python3
"""blockers.py: ROADMAP WS-19 move 4, the sole-blocker count.

The Lean Kernel Arena makes each checker's gap legible by naming, per
checker, how many tasks it alone keeps out of the all-checkers bar. This
is the same instrument over t's own sweep tables (AGREEMENT.md,
COVERAGE-lifted-785.md): a table has one row per task and one cell per
kernel reading "real / twin"; a cell counts when it reads exactly
"verified / refuted" (anything else, including a "(FLAKED)" suffix,
"no-twin / no-twin", "abstain / abstain" and "lower-error / lower-error",
is non-counting by the same plain string test, no special-casing needed).

For every task, the columns split into the ones that count and the ones
that do not. A non-counting column is a "sole blocker" of a task that
counts in exactly N-1 columns (N being the table's own column count, 7 in
both of t's tables, so "exactly six" in the prose): it is the only thing
standing between that task and the seven-of-seven bar. A non-counting
column is a "co-blocker" of a task that counts in N-2 or fewer columns
but at least one, because removing it alone would not have been enough;
some other column already keeps the task out. A task that counts in all
N columns has no blockers; a task that counts in zero has none either
(nothing there is "almost passing").

Two entry points:
  - `analyze(col_names, cell_rows)` and `render_block(...)` operate on
    already-parsed data: `col_names` is the ordered list of kernel column
    names, `cell_rows` maps task name -> {kernel: cell text exactly as it
    reads in the table}. run_par.format_table calls `render_section`
    directly on the rows it just built (the cell text it is about to
    write), so the table it appends to is never re-parsed.
  - `parse_table(path)` reads a committed .md file in this format and
    returns the same (col_names, cell_rows) shape, for the CLI below and
    for anyone re-deriving the block from a committed table instead of a
    live run.

CLI:
    python3 blockers.py PATH
        parse the table at PATH and print the block to stdout.
    python3 blockers.py PATH --append OUT
        also append the block, under a "## Sole blockers" heading, to the
        end of OUT (after any existing "## Reading" section).
    python3 blockers.py PATH --append OUT --replace
        if OUT already has a "## Sole blockers" section, replace it in
        place instead of appending a second one.
"""
from __future__ import annotations

import argparse
from pathlib import Path

COUNTS = "verified / refuted"

# Number words for the small counts this prose ever needs (six of seven
# kernels, seven kernels total); anything else falls back to the numeral.
_WORDS = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
          6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def _word(n: int) -> str:
    return _WORDS.get(n, str(n))


def parse_table(path: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    """Parse a `| task | k1 | k2 | ... |` table out of a committed .md
    file: the header line (literally starting `| task |`), its `|---|...`
    separator, and every `|`-prefixed line after it up to the first line
    that is not a table row. Returns (col_names, cell_rows) where
    cell_rows[task][kernel] is the cell text exactly as it reads in the
    table (whitespace-trimmed, nothing else touched)."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    header_idx = next((i for i, l in enumerate(lines) if l.startswith("| task |")), None)
    if header_idx is None:
        raise SystemExit(f"blockers.py: no '| task |' header found in {path}")
    header_cells = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    col_names = header_cells[1:]
    cell_rows: dict[str, dict[str, str]] = {}
    for line in lines[header_idx + 2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(header_cells):
            break
        cell_rows[cells[0]] = dict(zip(col_names, cells[1:]))
    return col_names, cell_rows


def analyze(col_names: list[str], cell_rows: dict[str, dict[str, str]]) -> dict:
    """Compute, from the cells alone, every kernel's sole-blocker and
    co-blocker counts and the names of the tasks it alone blocks, plus
    the total number of tasks counting in exactly N-1 columns."""
    n = len(col_names)
    sole = {k: 0 for k in col_names}
    co = {k: 0 for k in col_names}
    sole_tasks: dict[str, list[str]] = {k: [] for k in col_names}
    total_almost = 0
    for tname, cells in cell_rows.items():
        counting = [k for k in col_names if cells.get(k, "").strip() == COUNTS]
        blocking = [k for k in col_names if k not in counting]
        n_count = len(counting)
        if n_count == n - 1:
            total_almost += 1
            (only,) = blocking
            sole[only] += 1
            sole_tasks[only].append(tname)
        elif 1 <= n_count <= n - 2:
            for k in blocking:
                co[k] += 1
        # n_count == n (no blockers) and n_count == 0 (nothing to block)
        # contribute to neither bucket.
    return {"n": n, "sole": sole, "co": co, "sole_tasks": sole_tasks,
            "total_almost": total_almost}


def render_block(col_names: list[str], cell_rows: dict[str, dict[str, str]]) -> str:
    """The block itself: the sole/co-blocker table sorted by sole-blocker
    count descending (ties keep the table's own column order), each row's
    list of the tasks it alone blocks by name, and the one-line total.
    No heading; the caller adds one when appending a section."""
    report = analyze(col_names, cell_rows)
    n = report["n"]
    sole, co, sole_tasks = report["sole"], report["co"], report["sole_tasks"]
    out_of = f"all {_word(n)}" if n in _WORDS else f"all {n}"
    order = sorted(range(len(col_names)), key=lambda i: -sole[col_names[i]])
    lines = [f"| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of {out_of} |",
             "|---|---|---|---|"]
    for i in order:
        k = col_names[i]
        names = ", ".join(sorted(sole_tasks[k])) if sole_tasks[k] else "(none)"
        lines.append(f"| {k} | {sole[k]} | {co[k]} | {names} |")
    almost_word = _word(n - 1) if (n - 1) in _WORDS else str(n - 1)
    parts = [f"{sole[col_names[i]]} {'is' if sole[col_names[i]] == 1 else 'are'} "
             f"{col_names[i]} alone"
             for i in order if sole[col_names[i]] > 0]
    total_line = (f"Of the {report['total_almost']} tasks in {almost_word}, "
                  + (", ".join(parts) + "." if parts else "none are blocked alone."))
    lines += ["", total_line]
    return "\n".join(lines) + "\n"


def render_section(col_names: list[str], cell_rows: dict[str, dict[str, str]]) -> str:
    """render_block, wrapped in the '## Sole blockers' heading used both
    by the CLI's --append and by run_par.format_table, so a table built
    in memory and a table re-parsed from disk produce byte-identical
    sections."""
    return "## Sole blockers\n\n" + render_block(col_names, cell_rows)


def _replace_or_append(text: str, section: str, replace: bool) -> str:
    lines = text.splitlines(keepends=True)
    if replace:
        start = next((i for i, l in enumerate(lines)
                      if l.rstrip("\n") == "## Sole blockers"), None)
        if start is not None:
            end = next((j for j in range(start + 1, len(lines))
                        if lines[j].startswith("## ")), len(lines))
            return "".join(lines[:start]) + section + "".join(lines[end:])
    if text and not text.endswith("\n\n"):
        text = text.rstrip("\n") + "\n\n"
    return text + section


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("table", type=Path, help="a committed table in this format")
    ap.add_argument("--append", type=Path, default=None,
                    help="append the block, under a '## Sole blockers' heading, to this file")
    ap.add_argument("--replace", action="store_true",
                    help="with --append, replace an existing '## Sole blockers' section in place")
    args = ap.parse_args()

    col_names, cell_rows = parse_table(args.table)
    block = render_block(col_names, cell_rows)
    print(block)

    if args.append is not None:
        section = "## Sole blockers\n\n" + block
        target = args.append
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(_replace_or_append(existing, section, args.replace),
                           encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
