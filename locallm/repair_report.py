"""repair_report.py: the repair experiment's table and its pre-registered decisions, from the runs' own files.

    python3 locallm/repair_report.py --runs <dir holding A-s<seed>/ and B-s<seed>/> [--json out.json]

Reads, for each arm and seed, the pipeline's eval stage (`7-eval/stage.json`,
which ran with the chat-token grammar, then the engine's default) and
`eval-nogrammar.json` (the same checkpoint through the unmasked engine), and
applies the rules FINDINGS-repair-2026-09-26.md registered before the runs:

* repair data (B against A, grammar on): the primary is "pass all examples"
  over the 133 prompts (100 dev + 33 validation) per seed; the verdict is
  t/compare_arms.py's (exact one-sided permutation p over seeds, P(B > A) with
  ties 1/2 and its percentile bootstrap interval, Bouthillier et al.,
  arXiv:2103.03098), guarded by dev well formed and validation exact;
* the grammar (on against off, arm A, paired by checkpoint): no answer ends
  inside a call by <|assistant_end|>, and neither the primary nor dev well
  formed drops by more than 1 on the mean.

The note's second look (post hoc, predictions written before it was
computed) reads three more files per run when present: `rescore-grammar.json`
and `rescore-nogrammar.json` (the same rows under chat_eval.py --rescore
--answer best-verdict) and `eval-budget2.json` (grammar on, --max-calls 2,
--answer best-verdict), and applies the same two rules to them.

Nothing here generates or grades; every number is read from the eval files.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "t"))

ARMS = ("A", "B")
DEV_KEYS = ("at_least_typed", "examples_all_pass", "used_tool", "closed_every_call",
            "ended_in_call", "budget_in_call", "got_failing_verdict", "acted_on_failure",
            "repeated_after_failure", "repaired", "answers_overridden", "budget_refusals", "answer_not_last",
            "tool_calls_total", "ended")
VAL_KEYS = ("well_formed", "examples_all_pass", "exact_program", "used_tool", "closed_every_call",
            "ended_in_call", "budget_in_call", "got_failing_verdict", "acted_on_failure",
            "repeated_after_failure", "repaired", "answers_overridden", "budget_refusals", "answer_not_last",
            "tool_calls_total", "ended")


def read_eval(path: Path) -> dict:
    ev = json.loads(path.read_text(encoding="utf-8"))
    if "result" in ev:                       # a stage.json
        ev = ev["result"]
    return ev


VARIANTS = {  # name: (file in the run directory, grammar on)
    "grammar": ("7-eval/stage.json", True),
    "nogrammar": ("eval-nogrammar.json", False),
    "best-grammar": ("rescore-grammar.json", True),
    "best-nogrammar": ("rescore-nogrammar.json", False),
    "budget2": ("eval-budget2.json", True),
}


def collect(runs: Path) -> dict:
    """{(arm, variant): {seed: eval}} for every arm directory and variant file found."""
    out: dict = {}
    for arm in ARMS:
        for d in sorted(runs.glob(f"{arm}-s*")):
            seed = int(d.name.split("-s")[1])
            for variant, (name, grammar) in VARIANTS.items():
                path = d / name
                if path.is_file():
                    ev = read_eval(path)
                    if ev.get("grammar", True) != grammar:
                        raise SystemExit(f"{path} says grammar={ev.get('grammar')}, expected {grammar}")
                    out.setdefault((arm, variant), {})[seed] = ev
    return out


def primary(ev: dict) -> int:
    return ev["dev"]["examples_all_pass"] + ev["val"]["examples_all_pass"]


def mean(xs):
    return statistics.mean(xs) if xs else float("nan")


def table(evs: dict, label: str) -> list[str]:
    seeds = sorted(evs)
    lines = [f"### {label}", "", "| metric | " + " | ".join(f"s{s}" for s in seeds) + " | mean |",
             "|---|" + "---|" * (len(seeds) + 1)]

    def row(name, values):
        lines.append(f"| {name} | " + " | ".join(str(v) for v in values) + f" | {mean(values):.2f} |")
    row("**pass all examples, 133 prompts**", [primary(evs[s]) for s in seeds])
    row("dev tests passed", [evs[s]["dev"].get("tests_passed", 0) for s in seeds])
    for key in DEV_KEYS:
        row(f"dev {key}", [evs[s]["dev"].get(key, 0) for s in seeds])
    for key in VAL_KEYS:
        row(f"val {key}", [evs[s]["val"].get(key, 0) for s in seeds])
    return lines + [""]


def repair_rule(a: dict, b: dict) -> dict:
    """B against A on the primary, compare_arms' verdict, and the registered guards."""
    import compare_arms
    seeds = sorted(set(a) & set(b))
    pa, pb = [primary(a[s]) for s in seeds], [primary(b[s]) for s in seeds]
    p, midp = compare_arms.permutation_test(pa, pb)
    prob = compare_arms.prob_outperform(pa, pb)
    lo, hi = compare_arms.bootstrap_ci(pa, pb, paired=False)
    wf = mean([b[s]["dev"]["at_least_typed"] for s in seeds]) - mean([a[s]["dev"]["at_least_typed"] for s in seeds])
    ex = mean([b[s]["val"]["exact_program"] for s in seeds]) - mean([a[s]["val"]["exact_program"] for s in seeds])
    verdict = compare_arms.verdict(p, hi)
    passed = verdict == "ADOPT" and wf >= -2 and ex >= -2
    acted_b = sum(b[s]["dev"]["acted_on_failure"] + b[s]["val"]["acted_on_failure"] for s in seeds)
    failed_b = sum(b[s]["dev"]["got_failing_verdict"] + b[s]["val"]["got_failing_verdict"] for s in seeds)
    acted_rate = acted_b / failed_b if failed_b else 0.0
    return {"seeds": seeds, "A": pa, "B": pb, "mean_difference": mean(pb) - mean(pa),
            "permutation_p": str(p), "mid_p": str(midp), "p_B_beats_A": str(prob),
            "bootstrap_95": [lo, hi], "compare_arms_verdict": verdict,
            "dev_well_formed_change": wf, "val_exact_change": ex, "passes_rule": passed,
            "B_acted_on_failed_check_rate": acted_rate, "form_not_substance": (not passed) and acted_rate >= 0.25}


def grammar_rule(on: dict, off: dict) -> dict:
    """The grammar against no grammar on the same checkpoints, the registered rule."""
    seeds = sorted(set(on) & set(off))
    ended_on = sum(on[s]["dev"]["ended_in_call"] + on[s]["val"]["ended_in_call"] for s in seeds)
    d_primary = mean([primary(on[s]) - primary(off[s]) for s in seeds])
    d_wf = mean([on[s]["dev"]["at_least_typed"] - off[s]["dev"]["at_least_typed"] for s in seeds])
    return {"seeds": seeds, "ended_in_call_with_grammar": ended_on,
            "ended_in_call_without": [off[s]["dev"]["ended_in_call"] + off[s]["val"]["ended_in_call"] for s in seeds],
            "primary_change_mean": d_primary, "dev_well_formed_change_mean": d_wf,
            "passes_rule": ended_on == 0 and d_primary >= -1 and d_wf >= -1}


def decide(data: dict) -> dict:
    """The registered decisions (first look), then the same rules on the second look's variants."""
    out = {}
    if ("A", "grammar") in data and ("B", "grammar") in data:
        out["repair"] = repair_rule(data[("A", "grammar")], data[("B", "grammar")])
        out["repair"]["adopted"] = out["repair"]["passes_rule"]
    if ("A", "grammar") in data and ("A", "nogrammar") in data:
        out["grammar"] = grammar_rule(data[("A", "grammar")], data[("A", "nogrammar")])
        out["grammar"]["adopted"] = out["grammar"]["passes_rule"]
    second = {}
    for variant in ("best-grammar", "budget2"):
        if ("A", variant) in data and ("B", variant) in data:
            second[f"repair under {variant}"] = repair_rule(data[("A", variant)], data[("B", variant)])
    if ("A", "best-grammar") in data and ("A", "best-nogrammar") in data:
        second["grammar under best verdict"] = grammar_rule(data[("A", "best-grammar")], data[("A", "best-nogrammar")])
    if second:
        out["second look (post hoc: a pass is a hypothesis for fresh seeds, not an adoption)"] = second
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)
    data = collect(a.runs)
    lines = []
    for variant in VARIANTS:
        for arm in ARMS:
            if (arm, variant) in data:
                lines += table(data[(arm, variant)], f"arm {arm}, {variant} ({VARIANTS[variant][0]})")
    decisions = decide(data)
    lines += ["### decisions", "", "```", json.dumps(decisions, indent=2), "```"]
    print("\n".join(lines))
    if a.json:
        a.json.write_text(json.dumps({"decisions": decisions,
                                      "evals": {f"{k[0]}-{k[1]}": v for k, v in data.items()}}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
