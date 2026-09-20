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
  pre-completeness   the requires REJECTS inputs the problem does not define
                     `check_task.pre_completeness`
                     The corpus ships no negative inputs, which is why this read
                     NOT MEASURED until 2026-09-20. It does not need them: the
                     problem's own reference solution is the oracle for the
                     problem's domain exactly as it is already the oracle for
                     its outputs, so an input the reference refuses to compute
                     is an input the problem does not define. The signal was
                     already being drawn in check_task and discarded. This is
                     the admissibility leg of the admissibility / soundness /
                     uniqueness triad that property-based spec validation uses
                     (VERINA arXiv:2505.23135, CLEVER arXiv:2505.13938).

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
            # None when the reference never refused a draw, which is not the
            # same as scoring zero: a total problem has no domain boundary to
            # find, and averaging it in as a pass or a fail would both lie.
            "pre_complete": (None if "pre_completeness" not in tight
                             else tight["pre_completeness"]),
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
            "pre_completeness": (round(sum(scored) / len(scored), 3) if (
                scored := [i["pre_complete"] for i in items
                           if i["pre_complete"] is not None]) else None),
            "pre_completeness_n": len([i for i in items if i["pre_complete"] is not None]),
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
          f"{'pre-corr':>9} {'pre-comp/n':>9} {'exploited':>10}")
    for r in results:
        if "error" in r:
            print(f"{r['tag']:28} {r['error']}")
            continue
        for population, q in sorted(r["populations"].items()):
            # The rate is printed with the count it rests on, because these
            # counts are tiny: a bare 0.000 over one answer reads like a
            # population result and is not one.
            pc = ("      n/a" if q["pre_completeness"] is None
                  else f"{q['pre_completeness']:.3f}/{q['pre_completeness_n']}")
            print(f"{r['tag']:28} {population:18} {q['answers']:4} "
                  f"{q['post_correctness']:10.3f} {q['post_completeness']:10.3f} "
                  f"{q['pre_correctness']:9.3f} {pc:>9} {q['exploited']:10}")
    print("\npre-completeness: of the inputs the problem's own solution refuses to "
          "compute, the fraction\nthe specification's requires also refuses. n/a means "
          "the reference never refused a draw,\nso the problem showed no domain boundary "
          "to find. Counted over "
          f"{sum(q.get('pre_completeness_n', 0) for r in results if 'populations' in r for q in r['populations'].values())}"
          " answer(s) that had one.")
    if args.out:
        args.out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
