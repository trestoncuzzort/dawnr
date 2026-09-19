"""Strict report for the registered 1,000-step source-pretraining comparison.

Run on the lab; checkpoint tensors are memory-mapped on CPU, never sent to a GPU.
Example: python locallm/summarize_pretraining.py \
  --run modern:1337=RUN_DIRECTORY --run gpt:1337=CONTROL_DIRECTORY \
  --json summary.json --markdown summary.md

Missing and failed planned arms remain visible. A failed prediction is a result,
not an input error; mismatched or unverifiable comparisons return exit status 2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

SEEDS = (1337, 7, 42)
ARCHITECTURES = ("modern", "gpt")
STEPS = 1000
TOKENS_PER_STEP = 65536
SOURCE_FILES = ("train_distributed.py", "model.py", "data.py", "train.py")
LOSSES = ("train_nats_per_token", "val_nats_per_token")
HEX = re.compile(r"[0-9a-f]{64}\Z")


class InvalidRun(ValueError):
    """A constant, path-free explanation safe to include in a public report."""


def require(condition, explanation):
    if not condition:
        raise InvalidRun(explanation)


def integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum, f"invalid {name}")
    return value


def number(value, name, minimum=0):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= minimum
    except OverflowError:
        valid = False
    require(valid, f"invalid or nonfinite {name}")
    return value


def sha(value, name):
    require(isinstance(value, str) and HEX.fullmatch(value) is not None, f"invalid {name}")
    return value


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise InvalidRun("unreadable JSON metadata") from None
    require(isinstance(value, dict), "JSON metadata is not an object")
    return value


def checkpoint_metadata(path):
    """Load only the needed metadata; mmap leaves tensor storage on disk/CPU."""
    try:
        import torch
        saved = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
        return {key: saved[key] for key in (
            "distributed_schema", "config", "tokenizer_fingerprint", "step", "identity",
            "losses", "initial_losses")}
    except Exception:
        raise InvalidRun("checkpoint metadata missing or unreadable") from None


def metrics(path, completed):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise InvalidRun("metrics missing or unreadable") from None
    rows, last, uncommitted = {}, -1, 0
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            raise InvalidRun("malformed metrics row") from None
        require(isinstance(row, dict), "metrics row is not an object")
        step = integer(row.get("step"), "metrics step")
        require(step > last, "duplicate or unordered metrics steps")
        last = step
        if step > completed:
            uncommitted += 1
            continue
        for key in LOSSES:
            number(row.get(key), key)
        for key, value in row.items():
            if key.endswith("nats_per_token"):
                number(value, "recorded loss")
        rows[step] = {key: row[key] for key in LOSSES}
    return rows, uncommitted


def validate_identity(record, architecture, seed):
    identity = record["identity"]
    model, training, evaluation = (identity[key] for key in ("model", "training", "evaluation"))
    data, sources = identity["data"], identity["source"]
    require(identity["world_size"] == 4, "pilot requires four ranks")
    require(model["architecture"] == architecture and training["seed"] == seed,
            "run does not match its declared architecture/seed slot")
    for key, expected in {"n_layer": 12, "n_head": 12, "n_embd": 768,
                          "block_size": 2048, "vocab_size": 8192, "dropout": 0.0,
                          "bias": architecture == "gpt"}.items():
        require(model[key] == expected, f"pilot model setting differs: {key}")
    for key, expected in {"steps": STEPS, "batch_size": 8, "grad_accum": 1,
                          "lr": 0.0003, "warmup_steps": 50, "bf16": True,
                          "device": "cuda", "deterministic": True}.items():
        require(training[key] == expected, f"pilot training setting differs: {key}")
    integer(training["cpu_threads"], "CPU threads", 1)
    require(identity["tokenizer"] == {"kind": "bpe", "requested_vocab_size": 8192},
            "pilot requires the frozen 8192-entry BPE tokenizer")
    require(record["loss_units"] == evaluation["loss_units"] == "nats/token",
            "loss units must be nats per BPE token")
    require(evaluation["seed"] == 12345, "evaluation RNG seed differs from registered windows")
    integer(evaluation["iters"], "evaluation iterations", 1)
    require(record["evaluation_interval"] == 100, "pilot evaluation interval must be 100")
    require(data["split_mode"] == "explicit" and data["split_seed"] is None and data["val_frac"] is None,
            "pilot requires the frozen explicit training/validation partitions")
    for key in ("corpus_sha256", "train_sha256", "val_sha256"):
        sha(data[key], "partition hash")
    require(data["corpus_sha256"] == data["train_sha256"], "explicit training partition hash disagrees")
    require(data["train_sha256"] != data["val_sha256"], "training and validation partitions are identical")
    sha(identity["tokenizer_fingerprint"], "tokenizer fingerprint")
    sha(record["tokenizer_file_sha256"], "tokenizer file hash")
    for name in SOURCE_FILES:
        sha(sources[name], "source hash")
    require(sha(record["source_sha256"], "entrypoint source hash") == sources["train_distributed.py"],
            "entrypoint source hashes disagree")
    require(isinstance(identity["runtime"], dict) and all(
        key in identity["runtime"] for key in ("python", "torch", "cuda", "cudnn", "device_name")),
        "runtime identity is incomplete")
    require(identity["reproducibility"]["ddp_buckets"] == "registration_order",
            "deterministic DDP bucket policy is missing")
    batch = identity["world_size"] * training["batch_size"] * training["grad_accum"]
    require(record["effective_batch_size"] == batch and record["tokens_per_step"] == batch * model["block_size"]
            == TOKENS_PER_STEP, "token budget or effective batch is inconsistent")
    require(integer(record["train_tokens"], "training token count", 1) > model["block_size"]
            and integer(record["val_tokens"], "validation token count", 1) > model["block_size"],
            "partition is shorter than a training context")
    integer(record["parameters"], "parameter count", 1)
    require(record["schema"] == 2, "unsupported distributed metadata schema")
    # Exclude only intentional architecture differences and model-init seed.
    # Matching train.py + train_distributed.py hashes pins AdamW/clip/schedule
    # implementation, whose constants are not duplicated into run.json.
    return {
        "model": {k: v for k, v in model.items() if k not in ("architecture", "bias")},
        "training": {k: v for k, v in training.items() if k != "seed"},
        "evaluation": evaluation, "data": data, "source": sources,
        "runtime": identity["runtime"], "reproducibility": identity["reproducibility"],
        "tokenizer_fingerprint": identity["tokenizer_fingerprint"],
        "tokenizer_file_sha256": record["tokenizer_file_sha256"],
        "world_size": identity["world_size"],
        "train_tokens": record["train_tokens"], "val_tokens": record["val_tokens"],
        "tokens_per_step": record["tokens_per_step"],
    }


def read_arm(directory, architecture, seed):
    public = {"architecture": architecture, "seed": seed, "status": "not_provided"}
    if directory is None:
        return public, None
    record = read_json(directory / "run.json")
    signature = validate_identity(record, architecture, seed)
    try:
        token_bytes = (directory / "tokenizer.json").read_bytes()
    except OSError:
        raise InvalidRun("saved tokenizer file is missing or unreadable") from None
    require(hashlib.sha256(token_bytes).hexdigest() == signature["tokenizer_file_sha256"],
            "saved tokenizer file differs from recorded hash")
    status = record["status"]
    require(status in ("running", "stopped", "failed", "complete"), "unknown run status")
    completed = integer(record["completed_steps"], "completed steps")
    require(completed <= STEPS, "run exceeds the registered endpoint")
    public.update(status=status, completed_steps=completed, parameters=record["parameters"],
                  trained_tokens=completed * TOKENS_PER_STEP,
                  token_budget=STEPS * TOKENS_PER_STEP,
                  tokenizer_fingerprint=signature["tokenizer_fingerprint"],
                  train_sha256=signature["data"]["train_sha256"],
                  val_sha256=signature["data"]["val_sha256"])
    rows, uncommitted = metrics(directory / "metrics.jsonl", completed)
    require(0 in rows, "initial evaluation is missing")
    require(rows[0] == {k: record["initial_losses"][k] for k in LOSSES},
            "step-zero metrics differ from the saved baseline")
    require(rows[0]["val_nats_per_token"] > 0, "initial validation loss must be positive")
    public.update(initial_losses=rows[0], recorded_losses_finite=True,
                  evaluations=[{"step": step, **row} for step, row in rows.items()],
                  uncommitted_metric_rows=uncommitted)
    if status != "complete":
        return public, signature
    require(completed == STEPS, "complete run has not reached the 1000-step endpoint")
    require(all(step in rows for step in range(0, STEPS + 1, 100)),
            "one or more registered evaluation windows are missing")
    require(uncommitted == 0, "complete run has metrics beyond its committed endpoint")
    require(rows[STEPS] == {k: record["losses"][k] for k in LOSSES},
            "final metrics differ from run metadata")
    checkpoint = checkpoint_metadata(directory / "ckpt.pt")
    for key, expected in (("distributed_schema", record["schema"]), ("step", STEPS),
                          ("identity", record["identity"]), ("config", record["identity"]["model"]),
                          ("tokenizer_fingerprint", signature["tokenizer_fingerprint"]),
                          ("initial_losses", record["initial_losses"]), ("losses", record["losses"])):
        require(checkpoint[key] == expected, f"checkpoint metadata disagrees: {key}")
    public["checkpoint_endpoint_verified"] = True
    # run.json briefly says complete at final checkpoint publication, before
    # the trainer writes timing/memory data. Keep that snapshot pending.
    if not all(key in record for key in ("wall_seconds", "optimizer_seconds", "peak_allocated_bytes_by_rank",
                                         "peak_reserved_bytes_by_rank")):
        public["status"] = "publishing"
        return public, signature
    resumed = integer(record["resumed_from_step"], "resume step")
    require(resumed <= completed, "resume step exceeds endpoint")
    public.update(wall_seconds=number(record["wall_seconds"], "wall seconds"),
                  optimizer_seconds=number(record["optimizer_seconds"], "optimizer seconds"),
                  measurement_scope="whole_run" if resumed == 0 else "last_process_segment",
                  measured_steps=completed - resumed)
    for key in ("peak_allocated_bytes_by_rank", "peak_reserved_bytes_by_rank"):
        require(isinstance(record[key], list) and len(record[key]) == 4, "memory data must cover four ranks")
        public[key] = [integer(value, "rank peak memory") for value in record[key]]
    initial, final = rows[0]["val_nats_per_token"], rows[STEPS]["val_nats_per_token"]
    drop = (initial - final) / initial
    require(math.isfinite(drop), "validation loss ratio is not representable")
    public.update(final_losses=rows[STEPS], validation_loss_drop_fraction=drop,
                  learning_prediction_met=final <= 0.8 * initial)
    return public, signature


def summarize(directories):
    arms, signatures, errors = [], {}, []
    for seed in SEEDS:
        for architecture in ARCHITECTURES:
            slot = (architecture, seed)
            try:
                arm, signature = read_arm(directories.get(slot), *slot)
                if signature is not None:
                    signatures[slot] = signature
            except (InvalidRun, KeyError, TypeError, AttributeError) as error:
                reason = str(error) if isinstance(error, InvalidRun) else "metadata schema is incomplete or invalid"
                arm = {"architecture": architecture, "seed": seed, "status": "invalid", "reason": reason}
                errors.append({"architecture": architecture, "seed": seed, "reason": reason})
            arms.append(arm)
    by_slot = {(arm["architecture"], arm["seed"]): arm for arm in arms}
    mismatches = []
    if signatures:
        reference_slot, reference = next(iter(signatures.items()))
        for slot, candidate in signatures.items():
            differences = sorted(key for key in reference if reference[key] != candidate.get(key))
            if differences:
                mismatches.append({"architecture": slot[0], "seed": slot[1], "fields": differences,
                                   "reference_architecture": reference_slot[0], "reference_seed": reference_slot[1]})
    pairs = []
    for seed in SEEDS:
        modern, gpt = (by_slot[(architecture, seed)] for architecture in ARCHITECTURES)
        pair = {"seed": seed, "status": "pending"}
        if mismatches:
            pair["status"] = "refused_mismatched_inputs"
        elif any(arm["status"] in ("invalid", "failed") for arm in (modern, gpt)):
            pair["status"] = "failed_or_invalid_arm"
        elif all(arm["status"] == "complete" for arm in (modern, gpt)):
            m, g = modern["final_losses"]["val_nats_per_token"], gpt["final_losses"]["val_nats_per_token"]
            if g == 0:
                pair.update(status="complete", modern_relative_improvement=None,
                            architecture_prediction_met=False, reason="zero control loss has no relative improvement")
            else:
                gain = (g - m) / g
                if not math.isfinite(gain):
                    pair.update(status="invalid_ratio")
                    errors.append({"architecture": "modern", "seed": seed,
                                   "reason": "paired validation loss ratio is not representable"})
                else:
                    pair.update(status="complete", modern_relative_improvement=gain,
                                architecture_prediction_met=m <= 0.97 * g)
        pairs.append(pair)
    all_complete = all(pair["status"] == "complete" for pair in pairs)
    completed_pairs = [pair for pair in pairs if pair["status"] == "complete"]
    report = {
        "schema": 1, "preregistration": "PREREG-source-pretrain-2026-09-19.md",
        "planned_seeds": list(SEEDS), "endpoint_steps": STEPS, "tokens_per_arm": STEPS * TOKENS_PER_STEP,
        "arms": arms, "paired_results": pairs, "replications_complete": all_complete,
        "input_errors": errors, "comparison_mismatches": mismatches,
        "overall_status": "invalid_comparison" if errors or mismatches else
                          ("complete" if all_complete else "replications_pending"),
        "all_learning_predictions_met": all(arm["learning_prediction_met"] for arm in arms) if all_complete else None,
        "all_architecture_predictions_met": all(pair["architecture_prediction_met"] for pair in pairs) if all_complete else None,
        "limitations": [
            "This measures BPE token loss, not executable correctness, proof quality, or a Phi win.",
            "Fixed validation windows are identified by partition/tokenizer hashes, evaluation seed/iterations, rank count, microbatch and context.",
            "Matching trainer and optimizer source hashes pins unrecorded AdamW and gradient-clipping constants; their values are not independently stored in metadata.",
            "Finite-loss evidence covers recorded evaluations; completed training relies on the trainer's per-update nonfinite guards.",
            "Timing and peak memory cover only the final process segment after resume; run order is modern then GPT.",
            "All planned seeds are displayed; missing, failed and invalid arms are not replaced by a best-seed result.",
        ],
    }
    improvements = [pair["modern_relative_improvement"] for pair in completed_pairs
                    if pair["modern_relative_improvement"] is not None]
    report["completed_pairs"] = len(completed_pairs)
    report["mean_completed_pair_improvement"] = statistics.mean(improvements) if improvements else None
    return report


def markdown(report):
    lines = ["# Source-pretraining comparison", "", f"Status: **{report['overall_status']}**. "
             f"Completed matched seeds: {report['completed_pairs']}/3. "
             f"Endpoint: {STEPS} steps, {STEPS * TOKENS_PER_STEP:,} tokens per arm.", "",
             "| seed | core | status | initial val | final val | loss drop | parameters | wall seconds | max allocated GiB |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    timing_notes = []
    for arm in report["arms"]:
        initial = arm.get("initial_losses", {}).get("val_nats_per_token")
        final = arm.get("final_losses", {}).get("val_nats_per_token")
        fmt = lambda value: "—" if value is None else f"{value:.4f}"
        drop = arm.get("validation_loss_drop_fraction")
        memory = max(arm.get("peak_allocated_bytes_by_rank", [0])) / 2**30 if "peak_allocated_bytes_by_rank" in arm else None
        lines.append(f"| {arm['seed']} | {arm['architecture']} | {arm['status']} | {fmt(initial)} | {fmt(final)} | "
                     f"{'—' if drop is None else f'{drop:.2%}'} | {arm.get('parameters', '—')} | "
                     f"{fmt(arm.get('wall_seconds'))} | {fmt(memory)} |")
        if arm.get("measurement_scope") == "last_process_segment":
            timing_notes.append(f"Seed {arm['seed']} {arm['architecture']}: time/memory cover only its last "
                                f"{arm['measured_steps']} optimizer steps.")
    lines += ["", *timing_notes, "", "| seed | paired status | modern relative gain | ≥3% prediction |",
              "|---|---|---:|---|"]
    for pair in report["paired_results"]:
        gain = pair.get("modern_relative_improvement")
        verdict = "pending" if "architecture_prediction_met" not in pair else ("met" if pair["architecture_prediction_met"] else "falsified")
        lines.append(f"| {pair['seed']} | {pair['status']} | {'—' if gain is None else f'{gain:.2%}'} | {verdict} |")
    lines += ["", "The ≥20% learning and ≥3% architecture thresholds apply to every planned seed; "
              "no repeated result is declared while any pair is missing or invalid.", ""]
    for error in report["input_errors"]:
        lines.append(f"- Invalid {error['architecture']} seed {error['seed']}: {error['reason']}.")
    for mismatch in report["comparison_mismatches"]:
        lines.append(f"- Comparison refused for {mismatch['architecture']} seed {mismatch['seed']}: "
                     + ", ".join(mismatch["fields"]) + ".")
    lines += ["", *["- " + text for text in report["limitations"]], ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="append", default=[], metavar="ARCH:SEED=DIRECTORY")
    parser.add_argument("--json", type=Path, dest="json_path")
    parser.add_argument("--markdown", type=Path, dest="markdown_path")
    args = parser.parse_args(argv)
    directories = {}
    for value in args.run:
        try:
            label, directory = value.split("=", 1)
            architecture, raw_seed = label.split(":", 1)
            slot = (architecture, int(raw_seed))
            if architecture not in ARCHITECTURES or slot[1] not in SEEDS or not directory or slot in directories:
                raise ValueError
        except ValueError:
            parser.error("each --run must name a unique planned slot ARCH:SEED=DIRECTORY")
        directories[slot] = Path(directory)
    report = summarize(directories)
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.json_path:
        args.json_path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    if args.markdown_path:
        args.markdown_path.write_text(markdown(report), encoding="utf-8")
    return 2 if report["overall_status"] == "invalid_comparison" else 0


if __name__ == "__main__":
    raise SystemExit(main())
