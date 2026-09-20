#!/usr/bin/env python3
"""Seven provers as each other's reference: where do they contradict?

Differential testing of verifiers (arXiv:2606.01066) fuzzes several tools on the
same input and treats any disagreement as a bug in one of them. This project is
unusually well placed for it: every program is lowered to **seven independent
proof systems**, so a task where one says `verified` and another says `refuted`
is a contradiction, and at least one of them is wrong. The evidence is already
on disk in every `kernels.md`; nobody had counted it.

What counts as what:

  CONTRADICTION  on the same side of the same program, one kernel reads
                 `verified` and another reads `refuted`. These cannot both be
                 true: either the program meets its specification or there is a
                 counterexample. One of the two lowerings is wrong, or one of
                 the provers is.
  gap            one kernel reads `verified` and another reads `unproved`,
                 `timeout`, `abstain` or `malformed`. Not a contradiction: a
                 prover that cannot decide is not a prover that disagrees.
                 Counted separately because it measures capability, not
                 soundness, and conflating the two is how a lowering bug hides.

The twin side has its own contradiction. A twin carries a measured witness at
which it breaks the specification the real program keeps, so a **sound kernel
must refute it**. A twin that reads `verified` while others refute it is the
`verified / unsound` cell `AGREEMENT.md` already names, counted here across
every graded answer set rather than one table at a time.

    python3 t/kernel_disagreement.py                 # every graded set
    python3 t/kernel_disagreement.py --tag locallm-r8 --out t/out/DISAGREE.md

Read the per-kernel table as: when the seven contradict each other, which one is
standing alone? A kernel that is repeatedly the minority voice is the one to
audit first. That is the whole value of seven independent implementations, and
it costs nothing to compute because the proofs already ran.
"""
from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SE = HERE / "out" / "spec-experiment"
# A FLAKED suffix means the cell was re-run alone and is recorded as such; the
# verdict word in front of it is still the verdict (t/RECHECK-lean-2026-09-19.md).
FLAKE = re.compile(r"\s*\(FLAKED\)\s*$")
DECIDED = {"verified", "refuted"}


def split_cell(cell: str) -> tuple[str, str] | None:
    if "/" not in cell:
        return None
    real, twin = cell.split("/", 1)
    return FLAKE.sub("", real.strip()), FLAKE.sub("", twin.strip())


def read_table(path: Path) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """(kernel names, [(task, [cell, ...]), ...]) from a kernels.md."""
    names: list[str] = []
    rows: list[tuple[str, list[str]]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        if cells[0] == "task" and not names:
            names = cells[1:]
            continue
        if set(cells[0]) <= set("-: ") or not cells[0]:
            continue
        if names and len(cells) == len(names) + 1:
            rows.append((cells[0], cells[1:]))
    return names, rows


def scan(tables: list[Path]) -> dict:
    out = {
        "tables": 0, "rows": 0,
        "real_contradictions": [], "twin_unsound": [],
        "minority": Counter(), "gap_majority": Counter(),
        "pairs": Counter(),
    }
    for path in tables:
        names, rows = read_table(path)
        if not names:
            continue
        out["tables"] += 1
        tag = path.parent.name
        for task, cells in rows:
            out["rows"] += 1
            parsed = {n: split_cell(c) for n, c in zip(names, cells)}
            real = {n: v[0] for n, v in parsed.items() if v}
            twin = {n: v[1] for n, v in parsed.items() if v}

            # --- the real side: verified against refuted is a contradiction
            says = defaultdict(list)
            for kernel, verdict in real.items():
                if verdict in DECIDED:
                    says[verdict].append(kernel)
            if len(says) == 2:
                v, r = sorted(says["verified"]), sorted(says["refuted"])
                out["real_contradictions"].append(
                    {"tag": tag, "task": task, "verified": v, "refuted": r})
                minority = v if len(v) <= len(r) else r
                for kernel in minority:
                    out["minority"][kernel] += 1
                for a in v:
                    for b in r:
                        out["pairs"][tuple(sorted((a, b)))] += 1

            # --- the twin side: a twin that verifies where others refute
            tv = sorted(k for k, s in twin.items() if s == "verified")
            tr = sorted(k for k, s in twin.items() if s == "refuted")
            if tv and tr:
                out["twin_unsound"].append(
                    {"tag": tag, "task": task, "twin_verified": tv, "twin_refuted": tr})
                for kernel in tv:
                    out["minority"][kernel] += 1

            # --- gaps, counted apart: decided against could-not-decide
            decided = [k for k, s in real.items() if s in DECIDED]
            undecided = [k for k, s in real.items() if s not in DECIDED and s != "no-twin"]
            if decided and undecided:
                for kernel in undecided:
                    out["gap_majority"][kernel] += 1
    return out


def render(res: dict, kernels: list[str]) -> str:
    n_contra = len(res["real_contradictions"])
    n_twin = len(res["twin_unsound"])
    lines = [
        "# Seven provers as each other's reference",
        "",
        f"{res['rows']:,} graded programs over {res['tables']} answer sets, each lowered to "
        "seven independent proof systems.",
        "",
        "A **contradiction** is one kernel reading `verified` and another reading `refuted` "
        "about the same program: they cannot both be right. A **gap** is one kernel deciding "
        "where another could not, which measures capability rather than soundness and is "
        "counted apart.",
        "",
        "| finding | count |",
        "|---|---:|",
        f"| real-side contradictions (`verified` vs `refuted`) | **{n_contra}** |",
        f"| twin-side unsound (a twin that verifies where others refute) | **{n_twin}** |",
        "",
    ]
    if not n_contra and not n_twin:
        lines += [
            "**No contradictions anywhere.** Across every graded answer set, no two kernels "
            "ever reached opposite decided verdicts on the same program, and no twin verified "
            "in one kernel while being refuted in another.",
            "",
            "That is the strongest integrity statement this project can make about its own "
            "evaluator, and it is worth saying what it does *not* mean: seven kernels agreeing "
            "does not make a specification right (see `locallm/FINDINGS-completeness-2026-09-20.md`, "
            "where they agree on specifications that are flatly false at the problem's own "
            "solution). It means the instrument is self-consistent, not that the measurement "
            "is meaningful.",
            "",
            "It is also a property of a search: these programs come from one lowering pipeline "
            "and one problem corpus. A zero found by a search is a property of the search.",
            "",
        ]
    else:
        lines.append("## Contradictions, each one a bug in something\n")
        for row in res["real_contradictions"][:40]:
            lines.append(f"- `{row['tag']}/{row['task']}`: verified by "
                         f"{', '.join(row['verified'])}; refuted by {', '.join(row['refuted'])}")
        if n_contra > 40:
            lines.append(f"- ... and {n_contra - 40} more")
        lines.append("")
        for row in res["twin_unsound"][:40]:
            lines.append(f"- `{row['tag']}/{row['task']}`: TWIN verified by "
                         f"{', '.join(row['twin_verified'])}; refuted by {', '.join(row['twin_refuted'])}")
        lines.append("")
        if res["minority"]:
            lines += ["## Which kernel stands alone when they disagree",
                      "", "| kernel | times in the minority |", "|---|---:|"]
            for kernel, count in res["minority"].most_common():
                lines.append(f"| {kernel} | {count} |")
            lines += ["", "Audit the top row first: seven independent implementations exist "
                      "precisely so the outlier is identifiable.", ""]
    lines += ["## Gaps, which are not disagreements", "",
              "How often each kernel could not decide while at least one other did. This is a "
              "capability ranking, not a soundness one; `t/BUDGETS-2026-09-19.md` is the "
              "matching cost side.", "", "| kernel | undecided while another decided |", "|---|---:|"]
    for kernel in kernels or sorted(res["gap_majority"]):
        lines.append(f"| {kernel} | {res['gap_majority'].get(kernel, 0):,} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tag", action="append", default=[],
                    help="only these answer sets (default: every graded one)")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    tables = ([SE / t / "kernels.md" for t in a.tag] if a.tag
              else sorted(SE.glob("*/kernels.md")))
    tables = [t for t in tables if t.exists()]
    if not tables:
        print("no graded answer sets found")
        return 1
    res = scan(tables)
    names, _ = read_table(tables[0])
    text = render(res, names)
    print(text)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text + "\n", encoding="utf-8")
        print(f"written to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
