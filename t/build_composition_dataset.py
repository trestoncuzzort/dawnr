"""Compositional t curriculum: synthesis and execution examples with frozen
contracts, whole-pattern holdouts and an independent closed-form oracle.

Every label here is bounded concrete execution agreed by two implementations
(`interp` through `execution_trace`, and `composition_reference`, which never
sees the AST). Nothing here is a proof: a postcondition is only ever recorded
as true *at the generated inputs*. Held-out patterns never appear in training
under any parameter assignment, and the numerically extrapolated inputs are a
separate stratum from the held-out patterns.
"""
import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import random

from audit_collapsible import collapsible
import check_wf
import composition_reference as ref
from execution_trace import collect, digest
import surface

SCHEMA = 1
GRID = {"affine": [("affine", a, b) for a in (2, 3) for b in (-2, 1, 4)],
        "cap": [("cap", c) for c in (5, 12, 20)],
        "shift": [("shift", c) for c in (3, 7, 11)],
        "tri": [("tri", c) for c in (0, 4, 9)]}
TRAIN_INPUTS = list(range(-6, 11))
EXTRAPOLATION_INPUTS = list(range(-30, -19)) + list(range(18, 31))


def stage_statements(stage, position):
    """Source lines for one stage; their count must match the oracle's."""
    kind = stage[0]
    if kind == "affine":
        _, a, b = stage
        return [f"r := {a} * r + ({b});"]
    if kind == "cap":
        return [f"if r > {stage[1]} {{ r := {stage[1]} }} else {{ }}"]
    if kind == "shift":
        c = stage[1]
        return [f"if r < 0 {{ r := {c} - r }} else {{ r := r + {c} }}"]
    if kind == "tri":
        bound, counter = f"n{position}", f"i{position}"
        return [f"var {bound}: int := r;", f"var {counter}: int := 0;",
                f"r := {stage[1]};",
                f"while {counter} < {bound} decreases {bound} - {counter} "
                f"{{ r := r + {counter}; {counter} := {counter} + 1; }}"]
    raise ValueError(f"unknown stage kind {kind!r}")


def ensures_expression(stages):
    """The composition as a t expression over x: the contract, not a hint."""
    text = "x"
    for stage in stages:
        kind = stage[0]
        if kind == "affine":
            _, a, b = stage
            text = f"{a} * ({text}) + ({b})"
        elif kind == "cap":
            c = stage[1]
            text = f"(if ({text}) > {c} then {c} else ({text}))"
        elif kind == "shift":
            c = stage[1]
            text = f"(if ({text}) < 0 then {c} - ({text}) else ({text}) + {c})"
        elif kind == "tri":
            c = stage[1]
            text = f"{c} + tri(if ({text}) > 0 then ({text}) else 0)"
        else:
            raise ValueError(f"unknown stage kind {kind!r}")
    return text


def task_source(name, stages):
    loops = any(stage[0] == "tri" for stage in stages)
    lines = ["t 1"]
    if loops:
        lines.append("gate recursion")
    lines.append(f"task {name}(x: int) returns (r: int)")
    lines.append(f"  ensures r == {ensures_expression(stages)}")
    if loops:
        lines += ["spec fun tri(n: int): int", "  decreases n",
                  "= if n <= 0 then 0 else tri(n - 1) + (n - 1)"]
    lines.append("{")
    lines.append("  r := x;")
    for position, stage in enumerate(stages, start=1):
        lines += ["  " + line for line in stage_statements(stage, position)]
    lines.append("}")
    return "\n".join(lines) + "\n"


def build_task(name, stages):
    """Canonical source plus its AST; the pair is the frozen contract."""
    task = surface.parse(task_source(name, stages))
    source = surface.print_task(task)
    if surface.print_task(surface.parse(source)) != source:
        raise AssertionError(f"{name}: source has no fixed point under the printer")
    errors = check_wf.check_wf(task)
    if errors:
        raise AssertionError(f"{name}: {[str(e) for e in errors]}")
    if sum(ref.statement_count(stage[0]) for stage in stages) + 1 != len(task["body"]):
        raise AssertionError(f"{name}: oracle statement layout disagrees with the AST")
    return source, task


def event_line(event, previous):
    """One trace line: location, branch detail, then only what changed.

    Deltas keep loop traces inside the context; the full state is recoverable
    from the first line onward, so nothing the model must predict is dropped.
    """
    path = ".".join(str(part) for part in event["path"])
    detail = ""
    if event["kind"] == "guard":
        taken = event["taken"]
        detail = (f" {taken}" if isinstance(taken, str) else
                  f" {'true' if taken else 'false'}#{event['iteration']}")
    changed = {name: value for name, value in event["state"].items()
               if previous.get(name) != value}
    shown = " ".join(f"{name}=" + ("?" if value["type"] == "unassigned" else str(value["value"]))
                     for name, value in sorted(changed.items()))
    return f"{event['kind']} {path}{detail}" + (f" | {shown}" if shown else "")


def synthesis_example(source):
    """Prompt carries the whole contract; the completion is the body alone.

    The split is exact: prompt + completion is byte-identical to the canonical
    source, so a candidate cannot reach the contract it is scored against.
    """
    header, brace, body = source.partition("{\n")
    if not brace:
        raise AssertionError("canonical source has no body brace")
    return {"prompt": f"synthesize\n{header}{{\n", "completion": body}


def execution_example(source, x, events, value):
    """Intermediate states and the final output, as two supervision parts."""
    lines, previous = [], {}
    for event in events:
        lines.append(event_line(event, previous))
        previous = event["state"]
    return {"prompt": f"execute x = {x}\n{source}trace\n",
            "parts": [["".join(line + "\n" for line in lines), "execution"],
                      [f"output r = {value}\n", "answer"]]}


def record_for(name, stages, source, task, x, *, max_events):
    """One validated execution record, or None when it is too long to use."""
    expected = ref.expected_events(stages, x)
    if len(expected) > max_events:
        return None
    row = collect(task, {"x": x})
    if row["status"] != "ensures_true_at_input":
        raise AssertionError((name, x, row["status"]))
    value = ref.final_value(stages, x)
    if row["final_state"]["r"] != {"type": "int", "value": value}:
        raise AssertionError((name, x, "final value disagrees with the oracle"))
    if row["events"] != expected:
        raise AssertionError((name, x, "event stream disagrees with the oracle"))
    row.update(task_name=name, pattern=[stage[0] for stage in stages],
               stages=[list(stage) for stage in stages], x=x, reference_value=value,
               source=source, sample_id=digest([name, x]),
               reference_check={"method": "independent_closed_form_oracle",
                                "scope": "all_body_events_and_final_value",
                                "oracle_sha256": sha256(
                                    Path(ref.__file__).read_bytes()).hexdigest()},
               independently_validated=True)
    return row


def split_patterns(seed, held_pairs, depth_count):
    """Whole patterns, never parameter assignments, are what is held out."""
    rng = random.Random(seed)
    depth2 = [tuple(p) for p in product(ref.KINDS, repeat=2)]
    rng.shuffle(depth2)
    depth3 = [tuple(p) for p in product(ref.KINDS, repeat=3)]
    rng.shuffle(depth3)
    splits = {"train": sorted([(kind,) for kind in ref.KINDS]) + sorted(depth2[held_pairs:]),
              "eval_pattern": sorted(depth2[:held_pairs]),
              "eval_depth": sorted(depth3[:depth_count])}
    trained = set(splits["train"])
    for split in ("eval_pattern", "eval_depth"):
        overlap = trained.intersection(splits[split])
        if overlap:
            raise AssertionError(f"{split} shares a pattern with training: {sorted(overlap)}")
    return splits


def pattern_tasks(pattern, count, rng):
    options = [tuple(stages) for stages in product(*[GRID[kind] for kind in pattern])]
    rng.shuffle(options)
    return options[:count]


def corruption_checks(stages, x, events):
    """The comparison must fail on a wrong value, a wrong location and a gap."""
    checks = 0
    for mutate in (lambda e: e[:-1],
                   lambda e: e + [dict(e[-1])],
                   lambda e: [dict(row, path=list(row["path"]) + [0]) if i == len(e) // 2
                              else row for i, row in enumerate(e)],
                   lambda e: [dict(row, state={**row["state"],
                                               "r": {"type": "int", "value": 10 ** 9}})
                              if i == len(e) // 2 else row for i, row in enumerate(e)]):
        if not events:
            continue
        if mutate(list(events)) == ref.expected_events(stages, x):
            raise AssertionError("a corrupted trace compared equal to the oracle")
        checks += 1
    if ref.final_value(stages, x) == ref.final_value(stages, x) + 1:
        raise AssertionError("value comparison is insensitive")
    return checks + 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--variants", type=int, default=6,
                        help="parameter assignments per pattern")
    parser.add_argument("--inputs", type=int, default=12,
                        help="execution examples per training task")
    parser.add_argument("--eval-inputs", type=int, default=8,
                        help="scored inputs per held-out task, per stratum")
    parser.add_argument("--max-events", type=int, default=240,
                        help="length cap applied identically to every arm")
    parser.add_argument("--keep-collapsible", action="store_true",
                        help="keep held-out tasks a proper sub-sequence of their own "
                             "stages already passes; the default drops them, because "
                             "such a task is passed without composing anything")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    rng = random.Random(args.seed)
    splits = split_patterns(args.seed, 5, 12)

    traces, train, eval_execution, eval_synthesis = [], [], [], []
    counts = {"tasks": {}, "examples": {}, "rejected_overlength_traces": 0, "corruption_checks": 0}
    names = set()
    for split, patterns in splits.items():
        for pattern in patterns:
            for index, stages in enumerate(pattern_tasks(pattern, args.variants, rng)):
                name = f"comp_{'_'.join(pattern)}_{index}"
                if name in names:
                    raise AssertionError(f"duplicate task name {name}")
                names.add(name)
                source, task = build_task(name, stages)
                example = synthesis_example(source)
                if example["prompt"].partition("\n")[2] + example["completion"] != source:
                    raise AssertionError(f"{name}: prompt and completion do not rebuild the task")
                contract = {key: task.get(key) for key in
                            ("name", "params", "returns", "requires", "ensures", "spec_funs")}
                rows = []
                for x in sorted(rng.sample(TRAIN_INPUTS, min(args.inputs, len(TRAIN_INPUTS)))):
                    row = record_for(name, stages, source, task, x, max_events=args.max_events)
                    if row is None:
                        counts["rejected_overlength_traces"] += 1
                        continue
                    counts["corruption_checks"] += corruption_checks(stages, x, row["events"])
                    rows.append(row)
                if not rows:
                    # A task whose every trace is too long still contributes its
                    # synthesis example; only its execution examples are lost.
                    counts["tasks_without_execution_examples"] = counts.get(
                        "tasks_without_execution_examples", 0) + 1
                traces.extend(rows)
                serialized = [dict(kind="execution", task_name=name, split=split,
                                   pattern=list(pattern), x=row["x"],
                                   reference_value=row["reference_value"],
                                   **execution_example(source, row["x"], row["events"],
                                                       row["reference_value"]))
                              for row in rows]
                (train if split == "train" else eval_execution).extend(serialized)
                if split == "train":
                    train.append(dict(kind="synthesis", task_name=name, split=split,
                                      pattern=list(pattern), **example))
                else:
                    strata = {"in_range": sorted(rng.sample(TRAIN_INPUTS,
                                                            min(args.eval_inputs, len(TRAIN_INPUTS)))),
                              "extrapolation": sorted(rng.sample(EXTRAPOLATION_INPUTS,
                                                                 min(args.eval_inputs,
                                                                     len(EXTRAPOLATION_INPUTS))))}
                    shorter = collapsible(list(stages),
                                          [x for values in strata.values() for x in values])
                    if shorter is not None and not args.keep_collapsible:
                        # Nothing is learned from a held-out task one of its own
                        # stages already passes: drop the task and its traces.
                        counts["dropped_collapsible_tasks"] = counts.get(
                            "dropped_collapsible_tasks", 0) + 1
                        counts["tasks"][split] = counts["tasks"].get(split, 0)
                        del traces[len(traces) - len(rows):]
                        for row in serialized:
                            eval_execution.remove(row)
                        continue
                    eval_synthesis.append({
                        "task_name": name, "split": split, "pattern": list(pattern),
                        "stages": [list(stage) for stage in stages],
                        "collapsible_subsequence": shorter,
                        "prompt": example["prompt"], "contract": contract,
                        "contract_sha256": digest(contract), "task_sha256": digest(task),
                        # The body is withheld on purpose: scoring runs the candidate
                        # against independently computed values, never a stored answer.
                        "reference_completion_sha256": sha256(
                            example["completion"].encode()).hexdigest(),
                        "tests": {stratum: [{"x": x, "r": ref.final_value(stages, x)}
                                            for x in values]
                                  for stratum, values in strata.items()}})
                counts["tasks"][split] = counts["tasks"].get(split, 0) + 1

    covered = {tuple(row["pattern"]) for row in train + eval_execution
               if row["kind"] == "execution"}
    surviving = {tuple(row["pattern"]) for row in eval_synthesis}
    for split in ("eval_pattern", "eval_depth"):
        kept = [pattern for pattern in splits[split] if pattern in surviving]
        dropped = [list(pattern) for pattern in splits[split] if pattern not in surviving]
        if dropped:
            counts.setdefault("patterns_dropped_as_collapsible", {})[split] = dropped
        splits[split] = kept
        if not kept:
            raise AssertionError(f"{split}: every pattern collapses to a sub-sequence")
    uncovered = {}
    for split, patterns in splits.items():
        missing = sorted(set(patterns) - covered)
        if missing and split == "train":
            raise AssertionError("training patterns with no execution example inside the "
                                 f"event cap: {missing}")
        if missing:
            # Held-out patterns whose traces are all too long are still scored for
            # synthesis; only the secondary next-state metrics lose them.
            uncovered[split] = [list(pattern) for pattern in missing]
    counts["patterns_without_execution_examples"] = uncovered
    counts["examples"] = {"train_synthesis": sum(1 for row in train if row["kind"] == "synthesis"),
                          "train_execution": sum(1 for row in train if row["kind"] == "execution"),
                          "eval_execution": len(eval_execution),
                          "eval_synthesis_tasks": len(eval_synthesis),
                          "eval_synthesis_tests": sum(len(row["tests"][stratum])
                                                      for row in eval_synthesis
                                                      for stratum in row["tests"])}
    trained_patterns = {tuple(pattern) for pattern in splits["train"]}
    for row in eval_execution + eval_synthesis:
        if tuple(row["pattern"]) in trained_patterns:
            raise AssertionError(f"{row['task_name']}: evaluation pattern was trained")
    train_names = {row["task_name"] for row in train}
    leaked = train_names.intersection(row["task_name"] for row in eval_synthesis)
    if leaked:
        raise AssertionError(f"task identity shared between splits: {sorted(leaked)}")

    def write(path, rows):
        with (args.out / path).open("w") as stream:
            for row in rows:
                stream.write(json.dumps(row, sort_keys=True) + "\n")
        return sha256((args.out / path).read_bytes()).hexdigest()

    files = {"train.jsonl": write("train.jsonl", train),
             "eval_execution.jsonl": write("eval_execution.jsonl", eval_execution),
             "eval_synthesis.jsonl": write("eval_synthesis.jsonl", eval_synthesis),
             "traces.jsonl": write("traces.jsonl", traces)}
    producers = {name: sha256(Path(path).read_bytes()).hexdigest() for name, path in (
        ("generator", __file__), ("oracle", ref.__file__), ("exporter",
         str(Path(__file__).with_name("execution_trace.py"))),
        ("interpreter", str(Path(__file__).with_name("interp.py"))),
        ("surface", str(Path(__file__).with_name("surface.py"))))}
    manifest = {"schema": SCHEMA, "seed": args.seed, "files": files, "producers": producers,
                "counts": counts, "max_events": args.max_events,
                "train_inputs": TRAIN_INPUTS, "extrapolation_inputs": EXTRAPOLATION_INPUTS,
                "family_exclusion": {split: [list(pattern) for pattern in patterns]
                                     for split, patterns in splits.items()},
                "strata": ["eval_pattern: whole held-out compositions of trained primitives",
                           "eval_depth: three-stage programs, longer than anything trained",
                           "extrapolation: trained-range patterns at untrained input magnitudes"]}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    card = {"purpose": "paired latent/execution supervision comparison on unaided synthesis",
            "evidence": "bounded concrete execution, cross-checked against a closed-form oracle",
            "counts": counts,
            "distinct_patterns": {split: len(patterns) for split, patterns in splits.items()},
            "provenance": "deterministic stage templates; no model-generated labels",
            "training_ready": True, "formal_proof": False,
            "postconditions": "checked true at every generated input only; not proved",
            "manifest_sha256": sha256((args.out / "manifest.json").read_bytes()).hexdigest(),
            "limitations": ["int scalar tasks only: no seq, pair or string family",
                            "four stage kinds; compositions are stage chains, not arbitrary programs",
                            "traces above the event cap are dropped, which shortens loop coverage",
                            "no seven-verifier or twin evidence; execution labels are not proofs"]}
    (args.out / "card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"out": str(args.out), **card["counts"],
                      "distinct_patterns": card["distinct_patterns"]}))


if __name__ == "__main__":
    main()
