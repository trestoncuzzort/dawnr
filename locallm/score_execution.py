"""Secondary responses: predicted execution states and final outputs.

Greedy continuation from the same prompt the trainer used, compared line for
line against the frozen reference trace. Nothing is teacher-forced: a model
that derails on its second event keeps generating from its own mistake, which
is what "predicting the next state" has to mean at inference. Final-output
accuracy is read from the model's own output line, not from a reference.

This is descriptive. It is not the factorial's primary response, and a gain
here is not a synthesis gain: that is the whole point of scoring both.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch

from checkpoint import load_checkpoint

SCHEMA = 1
OUTPUT_PREFIX = "output r = "


def split_reference(row):
    trace, answer = row["parts"][0][0], row["parts"][1][0]
    return [line for line in trace.split("\n") if line], answer


def parse_generated(text):
    """Trace lines before the output line, and the output line if it arrived."""
    lines, output = [], None
    for line in text.split("\n"):
        if line.startswith(OUTPUT_PREFIX):
            output = line
            break
        if line:
            lines.append(line)
    return lines, output


def prefix_match(generated, reference):
    matched = 0
    for left, right in zip(generated, reference):
        if left != right:
            break
        matched += 1
    return matched


def score_row(model, tokenizer, row, *, device, slack):
    reference_lines, answer = split_reference(row)
    budget = len(tokenizer.encode("".join(line + "\n" for line in reference_lines) + answer))
    prompt = torch.tensor([tokenizer.encode(row["prompt"])], dtype=torch.long, device=device)
    room = model.config.block_size - prompt.size(1)
    with torch.no_grad():
        out = model.generate(prompt, min(budget + slack, room), temperature=0.0, use_cache=True)
    text = tokenizer.decode(out[0, prompt.size(1):].tolist())
    lines, output = parse_generated(text)
    matched = prefix_match(lines, reference_lines)
    return {"task_name": row["task_name"], "split": row["split"], "pattern": row["pattern"],
            "x": row["x"], "reference_lines": len(reference_lines),
            "matched_prefix_lines": matched,
            "trace_exact": lines == reference_lines,
            "produced_output": output is not None,
            "output_correct": output == answer.rstrip("\n")}


def summarize(rows):
    def fraction(predicate, subset):
        return (sum(1 for row in subset if predicate(row)) / len(subset)) if subset else None
    by_split = {}
    for row in rows:
        by_split.setdefault(row["split"], []).append(row)
    summary = {}
    for split, subset in sorted(by_split.items()):
        lines = sum(row["reference_lines"] for row in subset)
        summary[split] = {
            "examples": len(subset),
            "trace_exact": fraction(lambda row: row["trace_exact"], subset),
            "output_correct": fraction(lambda row: row["output_correct"], subset),
            "produced_output": fraction(lambda row: row["produced_output"], subset),
            "line_prefix_accuracy": (sum(row["matched_prefix_lines"] for row in subset) / lines)
            if lines else None}
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--examples", type=Path, required=True,
                        help="eval_execution.jsonl from the dataset")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--limit", type=int, default=0, help="first N examples, 0 for all")
    parser.add_argument("--slack", type=int, default=16,
                        help="tokens allowed beyond the reference length")
    parser.add_argument("--device", default=None)
    args = parser.parse_args()
    model, tokenizer, _ = load_checkpoint(args.checkpoint, device=args.device)
    device = next(model.parameters()).device
    rows = [json.loads(line) for line in args.examples.read_text().splitlines() if line]
    if args.limit:
        rows = rows[:args.limit]
    started = time.monotonic()
    scored = [score_row(model, tokenizer, row, device=device, slack=args.slack) for row in rows]
    report = {"schema": SCHEMA, "checkpoint": str(args.checkpoint),
              "examples_sha256": sha256(args.examples.read_bytes()).hexdigest(),
              "summary": summarize(scored), "seconds": round(time.monotonic() - started, 1),
              "rows": scored}
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"summary": report["summary"], "seconds": report["seconds"]}))


if __name__ == "__main__":
    main()
