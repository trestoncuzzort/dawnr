"""measure_spec_repair.py: how many of the repair run's "passed, not proved"
drafts t_tool.spec_changed now catches as having rewritten the specification.

    python3 locallm/measure_spec_repair.py [--repair-dir ~/scratch/dawnr-repair] [--json out.json]

FINDINGS-repair-2026-09-26.md: of 1,300 fold-model drafts, 285 passed every
example without being (norm()-equal to) the proved program -- exactly
repair_data.build()'s own "passed_not_proved" count -- and by hand, 101 of
those 285 had rewritten the declaration, requires or ensures. This script
does the same count the automated way: for every draft in that same 285
(read from the repair run's own saved conversations.jsonl and
work/drafts.jsonl, untouched), it calls t_tool.call(draft, user) again --
through today's t_tool.py, the only thing that is new -- and counts how many
now read "specification: spec changed" instead of passing outright. Nothing
is re-generated or re-graded; every number here is read from files the
registered run already wrote.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "t"))

import chat  # noqa: E402
import repair_data  # noqa: E402
import t_tool  # noqa: E402


def measure(repair_dir: Path) -> dict:
    convs = repair_data.load(repair_dir / "conversations.jsonl")
    drafts = repair_data.load(repair_dir / "work" / "drafts.jsonl")
    by_index: dict[int, list[dict]] = {}
    for d in drafts:
        by_index.setdefault(d["index"], []).append(d)

    passed_not_proved = Counter()          # by conversation kind -- repair_data.build()'s own population
    now_spec_changed: list[dict] = []
    checked = 0
    for i, rows in sorted(by_index.items()):
        conv = convs[i]
        user = conv["messages"][0]["content"]
        bad = [d for d in rows if d["user_sha256"] != repair_data.sha256_text(user)]
        if bad:
            raise SystemExit(f"conversation {i} ({conv.get('source')}): {len(bad)} draft(s) do not match "
                             f"this conversations.jsonl's user turn; wrong pair of files?")
        proved = chat.final_program(conv["messages"][1]["content"])
        proved = (proved or "").strip("\n") + "\n"
        for d in rows:
            checked += 1
            if not d["draft"] or not repair_data.verdict_ok(d["verdict"]):
                continue                                     # not "passed" by the ORIGINAL checker
            if repair_data.norm(d["draft"]) == repair_data.norm(proved):
                continue                                     # is the proved program: not what 285 counted
            passed_not_proved[conv["kind"]] += 1
            new_verdict = t_tool.call(d["draft"], user)
            if "specification: spec changed" in new_verdict:
                now_spec_changed.append({"index": i, "source": conv.get("source"), "fold": d["fold"],
                                         "sample": d["sample"], "kind": conv["kind"],
                                         "reason": new_verdict.splitlines()[-1]})
    return {"repair_dir": str(repair_dir), "drafts_checked": checked,
            "passed_not_proved_by_kind": dict(passed_not_proved),
            "passed_not_proved_total": sum(passed_not_proved.values()),
            "now_spec_changed_total": len(now_spec_changed),
            "now_spec_changed_by_kind": dict(Counter(r["kind"] for r in now_spec_changed)),
            "now_spec_changed": now_spec_changed}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repair-dir", type=Path, default=Path("~/scratch/dawnr-repair").expanduser())
    ap.add_argument("--json", type=Path, help="also write the full result, with every flagged draft, here")
    a = ap.parse_args(argv)
    result = measure(a.repair_dir)
    print(f"drafts checked: {result['drafts_checked']}")
    print(f"passed every example, not the proved program: {result['passed_not_proved_total']} "
          f"(by kind: {result['passed_not_proved_by_kind']})")
    print(f"of those, now \"specification: spec changed\": {result['now_spec_changed_total']} "
          f"(by kind: {result['now_spec_changed_by_kind']})")
    if a.json:
        a.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"full result written to {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
