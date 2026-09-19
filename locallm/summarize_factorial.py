"""Read the factorial ledger and report the two predictions it was run to test.

Additive improvement and interaction are separate claims and are reported
separately, per seed and pooled. Every non-answer counts as a failure, so the
headline rate is correct programs over held-out tasks, not over parsed ones.
"""
import argparse
import json
from pathlib import Path

ARMS = ("baseline", "latent", "execution", "combined")
THRESHOLD = 5.0       # percentage points, registered before the run


def rate(score, splits):
    tasks = sum(bucket["tasks"] for split, bucket in score["by_split"].items()
                if split in splits)
    correct = sum(bucket["correct"] for split, bucket in score["by_split"].items()
                  if split in splits)
    return correct, tasks, (100.0 * correct / tasks if tasks else float("nan"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--splits", nargs="+", default=["eval_pattern", "eval_depth"])
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    ledger = json.loads((args.study / "study.json").read_text())
    blocks, incomplete = [], []
    for block in ledger["blocks"]:
        cells = {}
        for entry in block["arms"]:
            path = args.study / entry["id"] / "score.json"
            if entry["status"] != "complete" or not path.exists():
                incomplete.append(entry["id"])
                continue
            score = json.loads(path.read_text())
            run = json.loads((args.study / entry["id"] / "run.json").read_text())
            correct, tasks, percent = rate(score, set(args.splits))
            cells[entry["arm"]] = {
                "correct": correct, "tasks": tasks, "percent": percent,
                "verdicts": score["verdicts"], "tests_by_stratum": score["tests_by_stratum"],
                "train_seconds": run["accounting"]["train_seconds"],
                "answer_tokens": run["accounting"]["answer_tokens"],
                "execution_tokens_supervised": run["accounting"]["execution_tokens_supervised"],
                "peak_allocated_bytes": run.get("peak_allocated_bytes")}
        summary = {"seed": block["seed"], "order": block["order"], "cells": cells}
        if all(arm in cells for arm in ARMS):
            base = cells["baseline"]["percent"]
            summary["differences"] = {arm: cells[arm]["percent"] - base
                                      for arm in ("latent", "execution", "combined")}
            summary["interaction"] = (cells["combined"]["percent"] - cells["latent"]["percent"]
                                      - cells["execution"]["percent"] + base)
        blocks.append(summary)
    complete = [block for block in blocks if "differences" in block]
    planned = len(ledger["blocks"])

    def verdict(violates):
        """An unfinished study decides nothing; one bad finished seed decides it."""
        broken = [block["seed"] for block in complete if violates(block)]
        if broken:
            return {"status": "falsified", "violating_seeds": broken}
        if len(complete) < planned:
            return {"status": "pending", "seeds_complete": len(complete),
                    "seeds_planned": planned}
        return {"status": "held", "violating_seeds": []}

    predictions = {
        "combined_beats_baseline_by_5_points_in_every_seed": verdict(
            lambda block: block["differences"]["combined"] < THRESHOLD),
        "combined_positive_in_every_seed": verdict(
            lambda block: block["differences"]["combined"] <= 0),
        "interaction_positive_in_every_seed": verdict(
            lambda block: block["interaction"] <= 0),
        "seeds_complete": len(complete), "seeds_planned": planned}
    report = {"study": str(args.study), "splits": args.splits, "blocks": blocks,
              "predictions": predictions, "incomplete_arms": incomplete}
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    lines = ["# Latent and execution supervision: factorial result", "",
             f"Held-out splits scored: {', '.join(args.splits)}. "
             f"Seeds complete: {predictions['seeds_complete']}/{predictions['seeds_planned']}.",
             "", "| seed | arm | correct | tasks | percent | malformed | wrong | other |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for block in blocks:
        for arm in ARMS:
            cell = block["cells"].get(arm)
            if not cell:
                lines.append(f"| {block['seed']} | {arm} | — | — | — | — | — | — |")
                continue
            verdicts = cell["verdicts"]
            other = sum(count for name, count in verdicts.items()
                        if name not in ("correct", "wrong_output", "malformed"))
            lines.append(f"| {block['seed']} | {arm} | {cell['correct']} | {cell['tasks']} | "
                         f"{cell['percent']:.1f}% | {verdicts.get('malformed', 0)} | "
                         f"{verdicts.get('wrong_output', 0)} | {other} |")
    lines += ["", "| seed | latent − baseline | execution − baseline | combined − baseline | interaction |",
              "|---|---:|---:|---:|---:|"]
    for block in complete:
        d = block["differences"]
        lines.append(f"| {block['seed']} | {d['latent']:+.1f} | {d['execution']:+.1f} | "
                     f"{d['combined']:+.1f} | {block['interaction']:+.1f} |")
    def phrase(key):
        result = predictions[key]
        if result["status"] == "pending":
            return f"**undecided**, {result['seeds_complete']} of {result['seeds_planned']} seeds finished"
        if result["status"] == "falsified":
            return f"**falsified** at seed(s) {', '.join(str(s) for s in result['violating_seeds'])}"
        return "**held**"

    lines += ["", "Registered predictions:", "",
              f"- combined beats baseline by at least {THRESHOLD:.0f} points in every seed: "
              f"{phrase('combined_beats_baseline_by_5_points_in_every_seed')}",
              f"- the paired combined difference is positive in every seed: "
              f"{phrase('combined_positive_in_every_seed')}",
              f"- the interaction is positive in every seed: "
              f"{phrase('interaction_positive_in_every_seed')}",
              "", "Malformed, timed-out, over-budget and contract-altering answers are counted "
              "as failures in every cell. These are generated-task scores: no seven-verifier, "
              "twin or specification-agreement evidence is claimed here."]
    if incomplete:
        lines += ["", f"Unfinished arms: {', '.join(incomplete)}."]
    text = "\n".join(lines) + "\n"
    if args.markdown:
        args.markdown.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
