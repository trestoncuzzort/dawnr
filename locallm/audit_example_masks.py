"""Tokenized mask audit for the factorial dataset, before any arm is trained.

Proves on real tokens what the design asserts on paper: every arm sees the
same input IDs in the same order, the synthesis and final-output targets are
identical across arms, and the only difference is which intermediate execution
tokens carry loss. Overlength examples are counted here and dropped for every
arm together, so no arm silently trains on a different corpus.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from completion_batch import IGNORE_INDEX, encode_example, encode_segments
from data import load_tokenizer, tokenizer_fingerprint

SCHEMA = 1


def supervised_text(tokenizer, encoded):
    """Exactly the tokens that carry loss, decoded, in order."""
    return tokenizer.decode([target for target in encoded["targets"]
                             if target != IGNORE_INDEX])


def audit_example(tokenizer, row, *, block_size):
    """Both treatments of one row, with the comparison that must hold."""
    if row["kind"] == "synthesis":
        encoded = encode_example(tokenizer, row["prompt"], row["completion"],
                                 block_size=block_size)
        return {"baseline": encoded, "treated": encoded, "identical_inputs": True,
                "identical_answer_targets": True,
                "supervised_baseline": supervised_text(tokenizer, encoded),
                "added_by_execution_arm": ""}
    parts = [(text, role) for text, role in row["parts"]]
    baseline = encode_segments(tokenizer, row["prompt"], parts,
                               block_size=block_size, supervise_execution=False)
    treated = encode_segments(tokenizer, row["prompt"], parts,
                              block_size=block_size, supervise_execution=True)
    answer_positions = [index for index, target in enumerate(baseline["targets"])
                        if target != IGNORE_INDEX]
    return {"baseline": baseline, "treated": treated,
            "identical_inputs": baseline["inputs"] == treated["inputs"],
            "identical_answer_targets": all(
                treated["targets"][index] == baseline["targets"][index]
                for index in answer_positions),
            "supervised_baseline": supervised_text(tokenizer, baseline),
            "added_by_execution_arm": tokenizer.decode(
                [treated["targets"][index] for index in range(len(treated["targets"]))
                 if treated["targets"][index] != IGNORE_INDEX
                 and baseline["targets"][index] == IGNORE_INDEX])}


def audit(tokenizer, rows, *, block_size, inspect):
    report = {"schema": SCHEMA, "block_size": block_size,
              "examples": {}, "overlength": {}, "tokens": {"input": 0, "supervised_baseline": 0,
                                                           "supervised_execution": 0},
              "identical_input_ids": True, "identical_answer_targets": True, "inspected": []}
    kept = []
    for row in rows:
        kind = row["kind"]
        report["examples"][kind] = report["examples"].get(kind, 0) + 1
        try:
            checked = audit_example(tokenizer, row, block_size=block_size)
        except ValueError as error:
            if "exceeds context" not in str(error):
                raise
            report["overlength"][kind] = report["overlength"].get(kind, 0) + 1
            continue
        kept.append(row["task_name"])
        report["identical_input_ids"] &= checked["identical_inputs"]
        report["identical_answer_targets"] &= checked["identical_answer_targets"]
        report["tokens"]["input"] += len(checked["baseline"]["inputs"])
        report["tokens"]["supervised_baseline"] += sum(
            target != IGNORE_INDEX for target in checked["baseline"]["targets"])
        report["tokens"]["supervised_execution"] += sum(
            target != IGNORE_INDEX for target in checked["treated"]["targets"])
        if len(report["inspected"]) < inspect:
            report["inspected"].append({
                "task_name": row["task_name"], "kind": kind, "split": row.get("split"),
                "prompt_tokens": checked["baseline"]["prompt_tokens"],
                "input_tokens": len(checked["baseline"]["inputs"]),
                "supervised_in_every_arm": checked["supervised_baseline"],
                "supervised_only_with_execution": checked["added_by_execution_arm"]})
    report["kept_examples"] = len(kept)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--block-size", type=int, default=512)
    parser.add_argument("--inspect", type=int, default=5)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.inspect < 5:
        raise SystemExit("the design requires at least five inspected examples")
    tokenizer = load_tokenizer(args.tokenizer)
    rows = [json.loads(line) for line in
            (args.dataset / "train.jsonl").read_text().splitlines() if line]
    report = audit(tokenizer, rows, block_size=args.block_size, inspect=args.inspect)
    report["tokenizer"] = {"file_sha256": sha256(args.tokenizer.read_bytes()).hexdigest(),
                           "fingerprint": tokenizer_fingerprint(tokenizer)}
    report["dataset"] = json.loads((args.dataset / "manifest.json").read_text())["files"]
    if not (report["identical_input_ids"] and report["identical_answer_targets"]):
        report["verdict"] = "FAILED: arms do not share inputs or answer targets"
    else:
        report["verdict"] = "arms share every input ID and every answer target"
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("examples", "overlength", "kept_examples", "tokens", "verdict")}))


if __name__ == "__main__":
    main()
