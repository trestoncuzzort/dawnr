#!/usr/bin/env python3
"""t/larger_inputs.py -- add the check on inputs larger than the examples to verdicts written before it existed
(2026-10-05).

    python3 t/larger_inputs.py --verdicts verdicts.json --out verdicts-larger.json [--pool v5] [--jobs 8] [TAG ...]

t/spec_check.py's draws are no larger than a problem's examples allow (a sequence two longer than the longest
example, an integer twice the example), so a specification that spells out the answers up to that size and says
nothing after them read as complete; t/LARGER-INPUTS-2026-10-05.md is the record, t/spec_check.draw_beyond the
remedy (QuickCheck's growing sizes; EvalPlus, arXiv:2305.01210; research receipt 5deec846ed0c). A verdict written
from that day on carries the larger-input check under "larger". This gives the same to an older verdict file, for
every answer whose verdict is "agrees" and whose task file is still in its answer set, so that t/score_levels.py
reads old and new answer sets with one rule. Each task draws from its own generator (the run's seed and the
task's sha256), as spec_check does, so the result does not depend on the order or on --jobs.

Nothing else in a verdict changes, and the file given is not written to.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness                                                  # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402

_POOL: dict = {}


def _one(job: tuple[str, str, int, int, str]) -> tuple[str, dict | None]:
    key, path, tid, seed, pool = job
    if pool not in _POOL:
        _POOL[pool] = se.pool(pool)
    entry = _POOL[pool].get(tid)
    if entry is None:
        return key, None
    try:
        task = harness.load(Path(path))
        return key, spec_check.larger_inputs(task, entry, f"{seed}:{spec_check.task_sha256(task)}")
    except Exception as error:                                  # noqa: BLE001 -- recorded, never counted for or against
        return key, {"status": f"not measured ({type(error).__name__})"}


def add(verdicts: dict, tags: list[str] | None, pool: str, jobs: int = 4, root: Path | None = None) -> tuple[dict, dict]:
    """(the verdicts with "larger" added where it could be measured, counts)."""
    root = root or HERE / "out" / "spec-experiment"
    todo = []
    for key, v in verdicts.items():
        tag, _, name = key.partition("/")
        if not isinstance(v, dict) or v.get("status") != "agrees" or "larger" in v or (tags and tag not in tags):
            continue
        path = root / se.model_tag(tag) / "tasks" / f"{name}.json"
        if path.exists() and v.get("task_id") is not None:
            todo.append((key, str(path), int(v["task_id"]), v.get("seed", 1), v.get("pool") or pool))
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in verdicts.items()}
    counts = {"agreeing verdicts": sum(1 for v in verdicts.values() if isinstance(v, dict) and v.get("status") == "agrees"),
              "measured": 0, "do not stand on larger inputs": 0, "not measured": 0}
    with ProcessPoolExecutor(max_workers=max(1, jobs)) as ex:
        for key, larger in ex.map(_one, todo, chunksize=4):
            if larger is None:
                counts["not measured"] += 1
                continue
            out[key]["larger"] = larger
            counts["measured"] += 1
            counts["do not stand on larger inputs"] += spec_check.larger_reason(larger, ordinary=verdicts[key]) is not None
    return out, counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tags", nargs="*", help="only these answer sets (default: every one in the file)")
    ap.add_argument("--verdicts", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pool", default="v5", help="the pool for verdicts that do not name theirs")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args(argv)
    if a.out.resolve() == a.verdicts.resolve():
        raise SystemExit("larger_inputs: --out must be another file; the verdicts given are not written to")
    data = json.loads(a.verdicts.read_text(encoding="utf-8"))
    data["results"], counts = add(data.get("results", {}), a.tags or None, a.pool, a.jobs)
    data["larger_inputs"] = {"added": "2026-10-05", "draws": spec_check.LARGER_DRAWS, **counts}
    a.out.write_text(json.dumps(data, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"{counts['measured']} of {counts['agreeing verdicts']} agreeing verdicts measured on larger inputs; "
          f"{counts['do not stand on larger inputs']} do not stand there; {counts['not measured']} could not be measured -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
