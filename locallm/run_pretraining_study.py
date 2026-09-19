"""Run the preregistered six-arm source-pretraining study, serially on four GPUs.

Run with the training environment's Python. Corpus/tokenizer audit and explicit
window-inspection acceptance are mandatory. An interruption never advances to
the next arm; use --resume to continue after examining the recorded failure.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
SOURCE_FILES = ("model.py", "data.py", "train.py", "train_distributed.py", "run_pretraining_study.py")
LOCK_FILE = Path.home() / ".local/state/locallm/pretraining-study.lock"
SCHEMA = 1
WORLD_SIZE = 4
MIN_FREE_MIB = 13 * 1024  # Measured modern reservation 11.90 GiB, plus >1 GiB headroom.
SEEDS = (1337, 7, 42)
CONFIG = {"preset": "core-medium", "tokenizer": "bpe", "vocab_size": 8192,
          "block_size": 2048, "n_layer": 12, "n_head": 12, "n_embd": 768,
          "batch_size": 8, "grad_accum": 1, "dropout": 0.0, "lr": 0.0003,
          "warmup_steps": 50, "steps": 1000, "eval_every": 100, "eval_iters": 10,
          "save_every": 100, "log_every": 100, "cpu_threads": 4,
          "gradient_checkpointing": False, "deterministic": True, "bf16": True}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_bytes().decode("utf-8"))


def atomic_json(path: Path, value: dict):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@contextlib.contextmanager
def study_lock():
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another pretraining study already holds the process lock") from None
        stream.seek(0)
        stream.truncate()
        stream.write(str(os.getpid()) + "\n")
        stream.flush()
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def tokenizer_identity(path: Path):
    from data import BPETokenizer, load_tokenizer, tokenizer_fingerprint
    tokenizer = load_tokenizer(path)
    if not isinstance(tokenizer, BPETokenizer) or tokenizer.vocab_size != CONFIG["vocab_size"]:
        raise ValueError("Study requires the audited 8192-entry BPE tokenizer")
    return tokenizer_fingerprint(tokenizer)


def validate_inputs(corpus: Path, tokenizer_dir: Path) -> dict:
    audit_path, inspection_path = tokenizer_dir / "audit.json", tokenizer_dir / "inspection.json"
    audit, inspection = read_json(audit_path), read_json(inspection_path)
    audit_hash, tokenizer_hash = sha256(audit_path), sha256(tokenizer_dir / "tokenizer.json")
    if inspection.get("status") != "passed":
        raise ValueError("Manual window inspection is missing acceptance or was rejected")
    if inspection.get("audit_sha256") != audit_hash or inspection.get("tokenizer_file_sha256") != tokenizer_hash:
        raise ValueError("Inspection acceptance does not identify this exact audit and tokenizer")
    inspected = inspection.get("inspected_windows")
    if isinstance(inspected, list):
        if any(not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < audit.get("training_windows", 0) for index in inspected):
            raise ValueError("Inspection window indices do not identify audited windows")
        count = len(set(inspected))
    else:
        count = inspected
    if not isinstance(count, int) or isinstance(count, bool) or count < 10:
        raise ValueError("At least ten distinct training windows must be inspected")
    if audit.get("tokenizer_file_sha256") != tokenizer_hash:
        raise ValueError("Frozen tokenizer file changed after audit")
    if audit.get("context") != CONFIG["block_size"] or audit.get("vocab_size") != CONFIG["vocab_size"]:
        raise ValueError("Audit context/vocabulary differs from the preregistered configuration")
    if audit.get("training_windows", 0) < 10:
        raise ValueError("Audit did not provide ten training windows")
    for name in ("family", "exact", "normalized"):
        if audit.get(f"cross_split_{name}_overlap") != 0:
            raise ValueError(f"Audit does not certify zero cross-split {name} overlap")
    quality = read_json(corpus / "quality.json")
    artifacts = {}
    for name in ("train.txt", "validation.txt", "provenance.jsonl", "sources-lock.json"):
        actual = sha256(corpus / name)
        if actual != audit.get("corpus_artifacts", {}).get(name) or actual != quality.get("artifacts", {}).get(name):
            raise ValueError(f"Corpus artifact changed after audit: {name}")
        artifacts[name] = actual
    for name, filename in (("train", "train.txt"), ("validation", "validation.txt")):
        split = audit.get("splits", {}).get(name, {})
        if split.get("roundtrip") is not True or split.get("sha256") != artifacts[filename]:
            raise ValueError(f"Missing exact tokenizer round trip for {name}")
        if split.get("tokens", 0) <= CONFIG["block_size"]:
            raise ValueError(f"Insufficient audited {name} tokens")
    fingerprint = tokenizer_identity(tokenizer_dir / "tokenizer.json")
    if fingerprint != audit.get("tokenizer_fingerprint"):
        raise ValueError("Tokenizer semantic fingerprint changed after audit")
    return {"corpus_artifacts": artifacts, "quality_sha256": sha256(corpus / "quality.json"),
            "audit_sha256": audit_hash, "inspection_sha256": sha256(inspection_path),
            "tokenizer_file_sha256": tokenizer_hash, "tokenizer_fingerprint": fingerprint}


def source_hashes() -> dict:
    return {name: sha256(HERE / name) for name in SOURCE_FILES}


def query_gpus() -> list[dict]:
    result = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.free,name", "--format=csv,noheader,nounits"],
                            capture_output=True, text=True, check=True, timeout=15)
    rows = []
    for line in result.stdout.splitlines():
        index, free, name = line.split(",", 2)
        rows.append({"index": int(index), "free_mib": int(free), "name": name.strip()})
    return rows


def select_gpus(rows: list[dict], selected: list[int] | None = None) -> list[dict]:
    if selected is None:
        available = sorted((row for row in rows if row["free_mib"] >= MIN_FREE_MIB),
                           key=lambda row: (-row["free_mib"], row["index"]))
        if len(available) < WORLD_SIZE:
            raise ValueError("Fewer than four GPUs have the measured 13 GiB free-memory requirement")
        return available[:WORLD_SIZE]
    by_index = {row["index"]: row for row in rows}
    if len(selected) != WORLD_SIZE or len(set(selected)) != WORLD_SIZE:
        raise ValueError("Saved study has an invalid GPU rank order")
    if any(index not in by_index or by_index[index]["free_mib"] < MIN_FREE_MIB for index in selected):
        raise ValueError("A selected GPU no longer has the measured 13 GiB free-memory requirement")
    return [by_index[index] for index in selected]


def arms():
    return [{"id": f"{architecture}-seed{seed}", "architecture": architecture, "seed": seed,
             "out": f"{architecture}-seed{seed}", "status": "pending", "attempts": []}
            for seed in SEEDS for architecture in ("modern", "gpt")]


def command_for(args, arm: dict, resume: bool) -> list[str]:
    command = [sys.executable, "-m", "torch.distributed.run", "--standalone", "--nproc-per-node=4",
               str(HERE / "train_distributed.py"), "--data", str(args.corpus / "train.txt"),
               "--validation-data", str(args.corpus / "validation.txt"),
               "--tokenizer-file", str(args.tokenizer_dir / "tokenizer.json"),
               "--out", str(args.out / arm["out"]), "--architecture", arm["architecture"],
               "--seed", str(arm["seed"])]
    for key, value in CONFIG.items():
        option = "--" + key.replace("_", "-")
        if isinstance(value, bool):
            command.append(option if value else "--no-" + key.replace("_", "-"))
        else:
            command.extend((option, str(value)))
    if resume:
        command.append("--resume")
    return command


def read_checkpoint(path: Path) -> dict:
    import torch
    return torch.load(path, map_location="cpu", weights_only=True)


def finite_losses(losses: dict) -> bool:
    return all(isinstance(losses.get(key), (int, float)) and not isinstance(losses[key], bool)
               and math.isfinite(losses[key]) for key in ("train_nats_per_token", "val_nats_per_token"))


def completed_run(args, arm: dict, ledger: dict) -> dict:
    output = args.out / arm["out"]
    record = read_json(output / "run.json")
    identity = record.get("identity", {})
    if record.get("status") != "complete" or record.get("completed_steps") != CONFIG["steps"]:
        raise ValueError(f"Arm {arm['id']} did not reach the preregistered endpoint")
    if record.get("loss_units") != "nats/token" or not finite_losses(record.get("initial_losses", {})) or not finite_losses(record.get("losses", {})):
        raise ValueError(f"Arm {arm['id']} has invalid baseline or endpoint losses")
    tokens_per_step = WORLD_SIZE * CONFIG["batch_size"] * CONFIG["grad_accum"] * CONFIG["block_size"]
    if record.get("tokens_per_step") != tokens_per_step or len(record.get("peak_allocated_bytes_by_rank", [])) != WORLD_SIZE or not all(value > 0 for value in record["peak_allocated_bytes_by_rank"]):
        raise ValueError(f"Arm {arm['id']} did not use the fixed four-GPU token budget")
    expected_training = {key: CONFIG[key] for key in ("steps", "batch_size", "grad_accum", "lr", "warmup_steps",
                                                     "bf16", "deterministic", "cpu_threads")}
    expected_training.update(seed=arm["seed"], device="cuda")
    if identity.get("training") != expected_training or identity.get("world_size") != WORLD_SIZE:
        raise ValueError(f"Arm {arm['id']} training configuration changed")
    model = identity.get("model", {})
    expected_model = {key: CONFIG[key] for key in ("vocab_size", "block_size", "n_layer", "n_head", "n_embd", "dropout", "gradient_checkpointing")}
    expected_model.update(architecture=arm["architecture"], bias=arm["architecture"] == "gpt")
    if any(model.get(key) != value for key, value in expected_model.items()):
        raise ValueError(f"Arm {arm['id']} model configuration changed")
    data = identity.get("data", {})
    if data.get("split_mode") != "explicit" or data.get("train_sha256") != ledger["inputs"]["corpus_artifacts"]["train.txt"] or data.get("val_sha256") != ledger["inputs"]["corpus_artifacts"]["validation.txt"]:
        raise ValueError(f"Arm {arm['id']} data partitions changed")
    if identity.get("tokenizer_fingerprint") != ledger["inputs"]["tokenizer_fingerprint"] or sha256(output / "tokenizer.json") != ledger["inputs"]["tokenizer_file_sha256"]:
        raise ValueError(f"Arm {arm['id']} tokenizer changed")
    if identity.get("evaluation") != {"iters": CONFIG["eval_iters"], "seed": 12345, "loss_units": "nats/token"}:
        raise ValueError(f"Arm {arm['id']} evaluation windows changed")
    expected_sources = {name: ledger["source_sha256"][name] for name in SOURCE_FILES if name != "run_pretraining_study.py"}
    if identity.get("source") != expected_sources:
        raise ValueError(f"Arm {arm['id']} core source changed")
    metrics = [json.loads(line) for line in (output / "metrics.jsonl").read_text().splitlines()]
    if [row.get("step") for row in metrics] != list(range(0, CONFIG["steps"] + 1, CONFIG["eval_every"])):
        raise ValueError(f"Arm {arm['id']} has incomplete evaluation history")
    if any(metrics[0].get(key) != value for key, value in record["initial_losses"].items()):
        raise ValueError(f"Arm {arm['id']} initial evaluation was not preserved")
    checkpoint = read_checkpoint(output / "ckpt.pt")
    if checkpoint.get("step") != CONFIG["steps"] or checkpoint.get("identity") != identity or checkpoint.get("initial_losses") != record["initial_losses"] or checkpoint.get("losses") != record["losses"] or len(checkpoint.get("rank_rng", [])) != WORLD_SIZE:
        raise ValueError(f"Arm {arm['id']} checkpoint and endpoint metadata disagree")
    if checkpoint.get("distributed_schema") != 2 or not checkpoint.get("model") or not checkpoint.get("optimizer", {}).get("state") or not checkpoint.get("optimizer", {}).get("param_groups"):
        raise ValueError(f"Arm {arm['id']} checkpoint is missing model or optimizer state")
    del checkpoint
    hashes = {name: sha256(output / name) for name in ("run.json", "ckpt.pt", "tokenizer.json", "metrics.jsonl")}
    if arm.get("artifact_sha256") is not None and arm["artifact_sha256"] != hashes:
        raise ValueError(f"Completed arm {arm['id']} artifacts changed")
    return {"artifact_sha256": hashes, "initial_losses": record["initial_losses"], "losses": record["losses"],
            "parameters": record["parameters"], "tokens_per_step": record["tokens_per_step"],
            "completed_steps": record["completed_steps"], "wall_seconds_last_attempt": record["wall_seconds"],
            "peak_allocated_bytes_by_rank": record["peak_allocated_bytes_by_rank"],
            "peak_reserved_bytes_by_rank": record["peak_reserved_bytes_by_rank"]}


class StopRequest:
    def __init__(self):
        self.requested = False
        self.signal = None

    def handler(self, signum, _frame):
        self.requested, self.signal = True, signum


def terminate_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    # A launcher may exit before every descendant; finish the entire owned group.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=10)


def run_arm(command: list[str], log: Path, selected: list[int], stop: StopRequest, on_started) -> int:
    if stop.requested:
        return -signal.SIGTERM
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES=",".join(map(str, selected)),
                       OMP_NUM_THREADS=str(CONFIG["cpu_threads"]), TOKENIZERS_PARALLELISM="false",
                       CUBLAS_WORKSPACE_CONFIG=":4096:8")
    with log.open("x", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=HERE, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            on_started(process.pid)
            while process.poll() is None:
                if stop.requested:
                    terminate_group(process)
                    return process.returncode if process.returncode else -signal.SIGTERM
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode:
                terminate_group(process)
            return process.returncode
        except BaseException:
            terminate_group(process)
            raise


def save_ledger(args, ledger):
    ledger["updated"] = utc_now()
    atomic_json(args.out / "study.json", ledger)


def run_study(args, stop: StopRequest) -> dict:
    inputs, sources = validate_inputs(args.corpus, args.tokenizer_dir), source_hashes()
    if args.check_only:
        return {"status": "ready", "inputs": inputs, "source_sha256": sources,
                "configuration": CONFIG, "arms": arms(), "gpus": select_gpus(query_gpus())}
    args.out.mkdir(parents=True, exist_ok=True)
    ledger_path = args.out / "study.json"
    if ledger_path.exists():
        if not args.resume:
            raise ValueError("Study output already exists; continuing requires --resume")
        ledger = read_json(ledger_path)
        if ledger.get("schema") != SCHEMA or ledger.get("configuration") != CONFIG or ledger.get("inputs") != inputs or ledger.get("source_sha256") != sources:
            raise ValueError("Study inputs, core source, or fixed configuration changed")
        expected = [(arm["id"], arm["architecture"], arm["seed"], arm["out"]) for arm in arms()]
        if [(arm["id"], arm["architecture"], arm["seed"], arm["out"]) for arm in ledger.get("arms", [])] != expected:
            raise ValueError("Saved study arm order or seeds changed")
        for arm in ledger["arms"]:
            if arm["status"] == "complete":
                completed_run(args, arm, ledger)
    else:
        if args.resume:
            raise ValueError("Cannot resume without the original study ledger")
        if any(args.out.iterdir()):
            raise ValueError("New study output must be empty; existing artifacts cannot be overwritten")
        selected = select_gpus(query_gpus())
        ledger = {"schema": SCHEMA, "created": utc_now(), "status": "ready", "configuration": CONFIG,
                  "inputs": inputs, "source_sha256": sources, "gpu_indices": [row["index"] for row in selected],
                  "initial_gpu_measurement": selected, "minimum_free_mib": MIN_FREE_MIB,
                  "arm_order": "modern then GPT for each seed; all three seeds retained",
                  "selection_rule": "all six runs reported; no best-seed selection", "arms": arms()}
        save_ledger(args, ledger)
    (args.out / "logs").mkdir(exist_ok=True)
    try:
        for arm in ledger["arms"]:
            if arm["status"] == "complete":
                continue
            if stop.requested:
                raise InterruptedError("Study interrupted before the next arm")
            if validate_inputs(args.corpus, args.tokenizer_dir) != inputs or source_hashes() != sources:
                raise ValueError("Audited inputs or frozen core source changed between arms")
            selected = select_gpus(query_gpus(), ledger["gpu_indices"])
            output = args.out / arm["out"]
            if output.exists() and any(output.iterdir()) and not args.resume:
                raise ValueError("Existing arm output requires explicit --resume")
            if (output / "run.json").exists() and read_json(output / "run.json").get("status") == "complete":
                if not args.resume:
                    raise ValueError("Existing completed output requires explicit --resume")
                arm.update(completed_run(args, arm, ledger), status="complete")
                save_ledger(args, ledger)
                continue
            resume_arm = (output / "ckpt.pt").exists()
            if resume_arm and not args.resume:
                raise ValueError("Existing checkpoint requires explicit --resume")
            attempt = {"started": utc_now(), "status": "running", "resume_checkpoint": resume_arm,
                       "gpu_measurement": selected,
                       "log": f"logs/{arm['id']}.attempt-{len(arm['attempts']) + 1}.log"}
            arm["attempts"].append(attempt)
            arm["status"], ledger["status"], ledger["active_arm"] = "running", "running", arm["id"]
            ledger.pop("error", None)
            save_ledger(args, ledger)

            def on_started(pid):
                attempt["launcher_pid"] = pid
                save_ledger(args, ledger)

            attempt_started = time.monotonic()
            returncode = run_arm(command_for(args, arm, resume_arm), args.out / attempt["log"],
                                 ledger["gpu_indices"], stop, on_started)
            attempt.update(ended=utc_now(), returncode=returncode, wall_seconds=time.monotonic() - attempt_started)
            if stop.requested or returncode:
                status = "interrupted" if stop.requested or returncode < 0 else "failed"
                attempt["status"] = arm["status"] = ledger["status"] = status
                raise InterruptedError("Active training process stopped") if status == "interrupted" else RuntimeError("Active training process failed; inspect its attempt log")
            arm.update(completed_run(args, arm, ledger), status="complete")
            arm["total_attempt_wall_seconds"] = sum(item.get("wall_seconds", 0) for item in arm["attempts"])
            attempt["status"] = "complete"
            ledger.pop("active_arm", None)
            save_ledger(args, ledger)
        ledger["status"] = "complete"
        ledger["completed"] = utc_now()
        save_ledger(args, ledger)
        return ledger
    except BaseException as error:
        ledger["status"] = "interrupted" if isinstance(error, (InterruptedError, KeyboardInterrupt)) else "failed"
        ledger["error"] = str(error).replace(str(Path.home()), "~")
        if ledger.get("active_arm"):
            for arm in ledger["arms"]:
                if arm["id"] == ledger["active_arm"] and arm["status"] == "running":
                    arm["status"] = ledger["status"]
                    arm["attempts"][-1].update(status=ledger["status"], ended=utc_now())
        save_ledger(args, ledger)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--tokenizer-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--resume", action="store_true", help="explicitly continue the recorded study after checking its artifacts")
    parser.add_argument("--check-only", action="store_true", help="validate inputs and measured fit without creating a study or launching training")
    args = parser.parse_args(argv)
    args.corpus, args.tokenizer_dir, args.out = (path.resolve() for path in (args.corpus, args.tokenizer_dir, args.out))
    stop = StopRequest()
    old_handlers = {sig: signal.signal(sig, stop.handler) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        with study_lock():
            result = run_study(args, stop)
        print(json.dumps({"status": result["status"], "arms": len(result["arms"]),
                          "gpu_measurement": result.get("gpus", result.get("initial_gpu_measurement")),
                          "seeds": list(SEEDS), "tokens_per_arm": CONFIG["steps"] * WORLD_SIZE * CONFIG["batch_size"] * CONFIG["grad_accum"] * CONFIG["block_size"]}), flush=True)
        return 0
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error).replace(str(Path.home()), "~"), file=sys.stderr, flush=True)
        return 130 if stop.requested or isinstance(error, InterruptedError) else 1
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
