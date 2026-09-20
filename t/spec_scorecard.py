"""How good are an answer set's specifications, in the vocabulary everyone uses.

Verifying a program against its specification says nothing about whether the
specification describes the problem. Seven groups converged on the same answer
to "is this spec any good": execute it as a predicate over positives and
negatives and score it as a two-sided classifier. Spec-Harness / vACT
(arXiv:2604.00280, github.com/Mondego/vACT) lays that out as four quadrants, and
reports Houdini verifying 93% of its benchmark while scoring 24%
post-completeness and 0% pre-correctness.

This prints those quadrants for any graded answer set, from instruments that
already exist here:

  post-correctness   the ensures holds at the problem's own examples and at its
                     reference solution              `check_points`, `check_task`
  post-completeness  the ensures rejects wrong answers and lazy programs
                     `mutations` (arXiv:2608.13077) and `exploit` (arXiv:2412.06176)
  pre-correctness    the requires admits the problem's own examples rather than
                     narrowing the problem          `check_points.points_excluded`
  pre-completeness   NOT MEASURED. It needs inputs the problem should reject,
                     which this corpus does not ship. Reported as a gap rather
                     than quietly omitted.

    python3 t/spec_scorecard.py --tag locallm-r8 --tag phi4-mini-eval2-2026-09-19
"""
import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness                                                  # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402

KERNELS = {"dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"}


def score(tag: str, pool, draws: int, root: Path) -> dict:
    d = root / tag
    if not (d / "kernels.md").exists():
        return {"tag": tag, "error": "not graded"}
    cols, cells = se.parse_kernel_table(d / "kernels.md")
    tests = {v.get("name"): v.get("overall")
             for v in json.loads((d / "tests.json").read_text()).values()}
    extracted = json.loads((d / "extract.json").read_text())
    rows = {"clean": [], "proven_but_wrong": []}
    for name, row in cells.items():
        proven = len(cols) == 7 and all(
            str(row.get(k, "")).startswith("verified / refuted") for k in KERNELS)
        if not proven:
            continue
        try:
            task = harness.load(d / "tasks" / f"{name}.json")
            entry = pool.get(spec_check.problem_id(name, extracted))
            if entry is None:
                continue
            points = spec_check.check_points(task, entry)
            tight = spec_check.check_task(task, entry, draws, random.Random(1))
            lazy = spec_check.exploit(task, entry)
        except Exception:                                       # noqa: BLE001
            continue
        rows["clean" if tests.get(name) == "pass" else "proven_but_wrong"].append({
            "post_correct": points["points_failed"] == 0 and points["points_held"] > 0,
            "post_complete": not tight.get("weak", False) and lazy["exploited_by"] is None,
            "pre_correct": points["points_excluded"] == 0,
            "exploited_by": lazy["exploited_by"]})
    out = {"tag": tag, "populations": {}}
    for population, items in rows.items():
        if not items:
            continue
        n = len(items)
        out["populations"][population] = {
            "answers": n,
            "post_correctness": round(sum(i["post_correct"] for i in items) / n, 3),
            "post_completeness": round(sum(i["post_complete"] for i in items) / n, 3),
            "pre_correctness": round(sum(i["pre_correct"] for i in items) / n, 3),
            "pre_completeness": None,
            "exploited": sum(i["exploited_by"] is not None for i in items)}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", action="append", required=True)
    parser.add_argument("--pool", default="v5")
    parser.add_argument("--draws", type=int, default=25)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    pool = se.pool(args.pool)
    root = HERE / "out" / "spec-experiment"
    results = [score(tag, pool, args.draws, root) for tag in args.tag]
    print(f"{'tag':28} {'population':18} {'n':>4} {'post-corr':>10} {'post-comp':>10} "
          f"{'pre-corr':>9} {'exploited':>10}")
    for r in results:
        if "error" in r:
            print(f"{r['tag']:28} {r['error']}")
            continue
        for population, q in sorted(r["populations"].items()):
            print(f"{r['tag']:28} {population:18} {q['answers']:4} "
                  f"{q['post_correctness']:10.3f} {q['post_completeness']:10.3f} "
                  f"{q['pre_correctness']:9.3f} {q['exploited']:10}")
    print("\npre-completeness is not measured: it needs inputs the problem should "
          "reject, which this corpus does not ship.")
    if args.out:
        args.out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
