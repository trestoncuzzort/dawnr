#!/usr/bin/env python3
"""t/score_levels.py -- how many problems are answered at each trust level (2026-10-01).

    python3 t/score_levels.py --split t/out/loop/split-v5.json --panel clean-200 \\
        --verdicts PATH TAG [TAG ...]
    python3 t/score_levels.py --ids-file dev-ids.txt --verdicts PATH TAG [TAG ...]

t/score_heldout.py counts an answer only when all seven kernels prove it. This reads the same
answer sets and reports every level: an answer counts at level k when it passes its problem's own
tests, at least k of the seven named kernels read `verified / refuted` (the program proved, its
sabotaged twin refuted), NO kernel refutes the program, and its specification agrees with the
problem's reference on drawn inputs under a verdict bound to the exact task (t/spec_check.py,
run with --only all so answers below seven are checked too).

Why the lower levels are reported and not dropped: one sound verifier is the published filter
(SAFE, arXiv:2410.15756; AlphaVerus), and in this project's own record no kernel has verified a
program another refuted (t/kernel_disagreement.py: 0 contradictions over 4,700 programs), so a
kernel that could not decide has never been evidence against a proof. The level is stated with
the answer; nothing is rounded up.

Per answer set, and pooled (a problem counts at the best level any listed set reaches: the gate
makes pooling safe, because a wrong answer does not pass it however many are tried).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import score_heldout                                            # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402

VERIFIED = "verified / refuted"
LEVELS = (1, 3, 5, 6, 7)


def answer_level(tests_overall: str | None, row: dict | None, spec_status: str | None) -> tuple[int, int]:
    """(level with the specification check, level without it); 0 when the answer does not count."""
    if tests_overall != "pass" or not row:
        return 0, 0
    if set(row) != set(spec_check.KERNELS):
        return 0, 0
    if any(str(cell).split(" / ")[0] == "refuted" for cell in row.values()):
        return 0, 0
    proved = sum(1 for cell in row.values() if cell == VERIFIED)
    return (proved if spec_status == "agrees" else 0), proved


# 2026-10-01: "agrees" says the specification is true of the reference's answer on every drawn
# input; it does not say the specification pins the answer down. The check has always also
# measured that (`completeness`: the share of mutated outputs the ensures rejects) and only
# reported it. SAFE keeps a specification as usable at 60% (arXiv:2410.15756, 3.2). With
# --min-completeness an answer whose specification agrees and rejects fewer mutants than that is
# not counted: five of the eight dev problems the 4B on v4 "proved" rest on such a specification.
MIN_COMPLETENESS = 0.6


def tag_levels(tag: str, ids: set[int], verdicts: dict, min_completeness: float | None = None
               ) -> dict[int, tuple[int, int, bool, bool]]:
    """problem -> (level, level without the spec check, reached a task, tests passed)."""
    d = se.OUT_ROOT / se.model_tag(tag)
    ext = json.loads((d / "extract.json").read_text(encoding="utf-8")) if (d / "extract.json").exists() else {}
    tests = json.loads((d / "tests.json").read_text(encoding="utf-8")) if (d / "tests.json").exists() else {}
    _cols, cells = (se.parse_kernel_table(d / "kernels.md") if (d / "kernels.md").exists() else ([], {}))
    out = {}
    for tid in ids:
        e, t = ext.get(str(tid), {}), tests.get(str(tid), {})
        name = t.get("name") or e.get("name") or ""
        raw = verdicts.get(f"{tag}/{name}") or {}
        status = score_heldout.checked_spec(raw, d / "tasks" / f"{name}.json")
        if status == "agrees" and min_completeness is not None and spec_check.complete(raw, min_completeness) is False:
            status = "weak"                                     # true of the right answer and of most wrong ones
        level, bare = answer_level(t.get("overall"), cells.get(name), status)
        out[tid] = (level, bare, e.get("stage") == "task", t.get("overall") == "pass")
    return out


def table(tags: list[str], ids: set[int], verdicts: dict, min_completeness: float | None = None
          ) -> tuple[list[dict], dict]:
    rows, best, best_bare = [], {tid: 0 for tid in ids}, {tid: 0 for tid in ids}
    any_task, any_pass = set(), set()
    for tag in tags:
        lv = tag_levels(tag, ids, verdicts, min_completeness)
        row = {"tag": tag, "problems": len(ids), "task": sum(1 for v in lv.values() if v[2]),
               "tests pass": sum(1 for v in lv.values() if v[3])}
        for k in LEVELS:
            row[f">={k}"] = sum(1 for v in lv.values() if v[0] >= k)
        rows.append(row)
        for tid, v in lv.items():
            best[tid] = max(best[tid], v[0])
            best_bare[tid] = max(best_bare[tid], v[1])
            if v[2]:
                any_task.add(tid)
            if v[3]:
                any_pass.add(tid)
    pooled = {"problems": len(ids), "task": len(any_task), "tests pass": len(any_pass)}
    for k in LEVELS:
        pooled[f">={k}"] = sum(1 for v in best.values() if v >= k)
        pooled[f">={k} before the specification check"] = sum(1 for v in best_bare.values() if v >= k)
    return rows, pooled


def render(rows: list[dict], pooled: dict) -> str:
    head = ["answer set", "problems", "reach a task", "tests pass"] + [
        ("all seven" if k == 7 else f"at least {k}") for k in LEVELS]
    lines = ["| " + " | ".join(head) + " |", "|---|" + "---:|" * (len(head) - 1)]
    for r in rows:
        lines.append("| " + " | ".join([r["tag"], str(r["problems"]), str(r["task"]), str(r["tests pass"])]
                                       + [str(r[f">={k}"]) for k in LEVELS]) + " |")
    if len(rows) > 1:
        lines.append("| **pooled** | " + " | ".join([str(pooled["problems"]), str(pooled["task"]), str(pooled["tests pass"])]
                                                    + [str(pooled[f">={k}"]) for k in LEVELS]) + " |")
    return "\n".join(lines)


def panel_ids(split_path: Path | None, panel: str, ids_file: Path | None) -> set[int]:
    if ids_file is not None:
        return {int(x) for x in ids_file.read_text(encoding="utf-8").split()}
    if split_path is None:
        raise SystemExit("score_levels: give --split with --panel, or --ids-file")
    eval_ids = {int(i) for i in json.loads(split_path.read_text(encoding="utf-8"))["eval_ids"]}
    return score_heldout.clean_eval_ids(eval_ids) if panel == "clean-200" else eval_ids


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tags", nargs="+")
    ap.add_argument("--split", type=Path)
    ap.add_argument("--panel", choices=("clean-200", "all-232"), default="clean-200")
    ap.add_argument("--ids-file", type=Path, help="score these problem ids instead of a held-out panel")
    ap.add_argument("--verdicts", type=Path, default=HERE / "out" / "spec-disagree.json",
                    help="a spec_check verdict file covering every answer (--only all)")
    ap.add_argument("--json", type=Path, help="also write the rows and the pooled counts here")
    ap.add_argument("--min-completeness", type=float, default=None, metavar="F",
                    help=f"count an answer only if its specification also rejects at least this share of mutated "
                         f"outputs on the check's drawn inputs (SAFE's rule is {MIN_COMPLETENESS})")
    a = ap.parse_args(argv)
    ids = panel_ids(a.split, a.panel, a.ids_file)
    verdicts = json.loads(a.verdicts.read_text(encoding="utf-8")).get("results", {})
    rows, pooled = table(a.tags, ids, verdicts, a.min_completeness)
    print(render(rows, pooled))
    if a.json:
        a.json.write_text(json.dumps({"rows": rows, "pooled": pooled, "ids": len(ids)}, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
