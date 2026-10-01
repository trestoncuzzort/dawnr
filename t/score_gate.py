#!/usr/bin/env python3
"""t/score_gate.py -- what the gate SHOWS without a reference, and how much of it is right (2026-10-01).

    python3 t/score_gate.py --ids-file IDS --verdicts REFERENCE.json --gate GATE.json TAG [TAG ...]

t/score_levels.py counts an answer when the problem's reference solution says its specification
is right. A person asking a question has no reference: what they are shown is whatever passes
the question's tests, a proof, and the gate's own specification stage (t/spec_gate.py, the
model's tested Python standing where the reference stands; Clover's consistency check,
arXiv:2310.17807). This reports both sides of that, per answer set and pooled over the sets:

  shown            a problem with some answer that passes its tests, is proved by at least k
                   kernels with none refuting, and passes the gate's stage (no reference used)
  shown and right  ... where such an answer's specification also agrees with the reference and
                   rejects at least 60% of the mutated outputs (score_levels.MIN_COMPLETENESS,
                   SAFE's floor, arXiv:2410.15756 3.2)

The ratio is the gate's precision on those problems. A problem shown on a wrong or weak
specification is the failure the stage exists to prevent; it is listed by id.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import score_heldout                                            # noqa: E402
import score_levels                                             # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402

KS = (1, 7)


def tag_answers(tag: str, ids: set[int], verdicts: dict, gate: dict) -> dict[int, dict]:
    """problem -> {"proved": kernels (0 when it does not pass tests and a proof), "shown": bool,
    "right": bool} for the set's answer to it."""
    d = se.OUT_ROOT / se.model_tag(tag)
    tests = json.loads((d / "tests.json").read_text(encoding="utf-8")) if (d / "tests.json").exists() else {}
    _cols, cells = (se.parse_kernel_table(d / "kernels.md") if (d / "kernels.md").exists() else ([], {}))
    out = {}
    for tid in ids:
        t = tests.get(str(tid), {})
        name = t.get("name") or ""
        _lvl, proved = score_levels.answer_level(t.get("overall"), cells.get(name), None)
        shown = right = False
        if proved:
            path = d / "tasks" / f"{name}.json"
            g = gate.get(f"{tag}/{name}") or {}
            try:
                bound = g.get("task_sha256") == spec_check.task_sha256(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, KeyError, TypeError):
                bound = False
            shown = bool(g.get("passes")) and bound             # a verdict for other task contents shows nothing
            raw = verdicts.get(f"{tag}/{name}") or {}
            status = score_heldout.checked_spec(raw, path)
            complete = not isinstance(raw.get("completeness"), (int, float)) or raw["completeness"] >= score_levels.MIN_COMPLETENESS
            right = status == "agrees" and complete
        out[tid] = {"proved": proved, "shown": shown, "right": right}
    return out


def table(tags: list[str], ids: set[int], verdicts: dict, gate: dict) -> tuple[list[dict], dict]:
    rows = []
    best = {tid: {k: {"proved": False, "shown": False, "shown_right": False, "right": False} for k in KS} for tid in ids}
    for tag in tags:
        ans = tag_answers(tag, ids, verdicts, gate)
        row = {"tag": tag}
        for k in KS:
            row[f"proved>={k}"] = sum(1 for a in ans.values() if a["proved"] >= k)
            row[f"shown>={k}"] = sum(1 for a in ans.values() if a["proved"] >= k and a["shown"])
            row[f"shown and right>={k}"] = sum(1 for a in ans.values() if a["proved"] >= k and a["shown"] and a["right"])
        rows.append(row)
        for tid, a in ans.items():
            for k in KS:
                if a["proved"] >= k:
                    b = best[tid][k]
                    b["proved"] = True
                    b["right"] |= a["right"]
                    b["shown"] |= a["shown"]
                    b["shown_right"] |= a["shown"] and a["right"]
    pooled = {"problems": len(ids)}
    for k in KS:
        pooled[f"proved>={k}"] = sum(1 for b in best.values() if b[k]["proved"])
        pooled[f"right by the reference>={k}"] = sum(1 for b in best.values() if b[k]["right"])
        pooled[f"shown>={k}"] = sum(1 for b in best.values() if b[k]["shown"])
        pooled[f"shown and right>={k}"] = sum(1 for b in best.values() if b[k]["shown_right"])
        pooled[f"shown, none right>={k}"] = sorted(tid for tid, b in best.items() if b[k]["shown"] and not b[k]["shown_right"])
    return rows, pooled


def render(rows: list[dict], pooled: dict) -> str:
    head = ["answer set", "proved by at least 1", "shown by the gate", "shown and right",
            "proved by all seven", "shown", "shown and right"]
    lines = ["| " + " | ".join(head) + " |", "|---|" + "---:|" * (len(head) - 1)]
    for r in rows:
        lines.append("| " + " | ".join([r["tag"]] + [str(r[f"{c}>={k}"]) for k in KS
                                                      for c in ("proved", "shown", "shown and right")]) + " |")
    lines.append("| **pooled** | " + " | ".join(str(pooled[f"{c}>={k}"]) for k in KS
                                                for c in ("proved", "shown", "shown and right")) + " |")
    for k in KS:
        shown, right = pooled[f"shown>={k}"], pooled[f"shown and right>={k}"]
        label = "one kernel or more" if k == 1 else "all seven"
        lines.append(f"at {label}: {shown} problems shown, {right} right"
                     + (f" ({100 * right / shown:.0f}%)" if shown else "")
                     + f"; {pooled[f'right by the reference>={k}']} had a right answer the gate could have shown"
                     + (f"; shown with no right answer: {pooled[f'shown, none right>={k}']}" if pooled[f"shown, none right>={k}"] else ""))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tags", nargs="+")
    ap.add_argument("--ids-file", type=Path, required=True)
    ap.add_argument("--verdicts", type=Path, required=True, help="the reference check's verdict file (spec_check --only all)")
    ap.add_argument("--gate", type=Path, required=True, help="t/spec_gate.py --json output")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    ids = {int(x) for x in a.ids_file.read_text(encoding="utf-8").split()}
    verdicts = json.loads(a.verdicts.read_text(encoding="utf-8")).get("results", {})
    gate = json.loads(a.gate.read_text(encoding="utf-8")).get("results", {})
    rows, pooled = table(a.tags, ids, verdicts, gate)
    print(render(rows, pooled))
    if a.json:
        a.json.write_text(json.dumps({"rows": rows, "pooled": pooled}, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
