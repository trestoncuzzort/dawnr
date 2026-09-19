"""Which held-out tasks can be passed without composing them?

A composition task is only evidence of composition if no proper sub-sequence of
its stages reproduces its outputs on its own tests. `cap 12` twice behaves like
`cap 12` once, and a model that writes one stage and stops passes that task
while composing nothing. This audit names those tasks, and cross-tabulates them
against a scored run so a reported score cannot be read as more than it is.
"""
import argparse
from itertools import combinations
import json
from pathlib import Path

import composition_reference as ref


def stages_by_task(dataset):
    """From the evaluation manifest when it carries stages, else from traces."""
    stages = {}
    traces = dataset / "traces.jsonl"
    if traces.exists():
        for line in traces.read_text().splitlines():
            row = json.loads(line)
            stages.setdefault(row["task_name"], [tuple(stage) for stage in row["stages"]])
    for line in (dataset / "eval_synthesis.jsonl").read_text().splitlines():
        row = json.loads(line)
        if "stages" in row:
            stages[row["task_name"]] = [tuple(stage) for stage in row["stages"]]
    return stages


def collapsible(stages, inputs):
    """The shortest proper sub-sequence that matches on every input, or None."""
    expected = [ref.final_value(stages, x) for x in inputs]
    for size in range(1, len(stages)):
        for chosen in combinations(range(len(stages)), size):
            candidate = [stages[index] for index in chosen]
            if [ref.final_value(candidate, x) for x in inputs] == expected:
                return list(chosen)
    return None


def audit(dataset, scores=None):
    stages = stages_by_task(dataset)
    entries = [json.loads(line) for line in
               (dataset / "eval_synthesis.jsonl").read_text().splitlines() if line]
    rows, unknown = [], []
    for entry in entries:
        if entry["task_name"] not in stages:
            unknown.append(entry["task_name"])
            continue
        inputs = [test["x"] for tests in entry["tests"].values() for test in tests]
        shorter = collapsible(stages[entry["task_name"]], inputs)
        rows.append({"task_name": entry["task_name"], "split": entry["split"],
                     "pattern": entry["pattern"], "collapsible": shorter is not None,
                     "passing_subsequence": shorter})
    report = {"tasks_checked": len(rows), "tasks_unknown_stages": len(unknown),
              "collapsible": sum(1 for row in rows if row["collapsible"]),
              "unknown": unknown, "rows": rows}
    if scores:
        names = {row["task_name"] for row in rows if row["collapsible"]}
        tally = {"correct": 0, "correct_collapsible": 0, "correct_composed": 0, "arms": 0}
        for path in sorted(scores):
            tally["arms"] += 1
            for row in json.loads(Path(path).read_text())["rows"]:
                if row["verdict"] != "correct":
                    continue
                tally["correct"] += 1
                key = "correct_collapsible" if row["task_name"] in names else "correct_composed"
                tally[key] += 1
        report["scored"] = tally
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--score", action="append", default=[],
                        help="score.json files to cross-tabulate")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = audit(args.dataset, args.score)
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("tasks_checked", "tasks_unknown_stages", "collapsible")
                      } | ({"scored": report["scored"]} if "scored" in report else {})))


if __name__ == "__main__":
    main()
