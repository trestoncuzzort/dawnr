"""Launcher for the latent/execution factorial: twelve arms, one ledger.

Four treatments from one frozen initialization per seed, in an order randomized
before launch and recorded, on whichever card measures enough free memory at
the moment the arm starts. Every arm trains, then generates one greedy program
per held-out task, then is scored by the independent scorer. A crashed arm is
resumed from its own state, never restarted from a different one, and a failed
attempt is kept.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ARMS = ("baseline", "latent", "execution", "combined")
SCHEMA = 1


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def free_cards():
    result = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.free",
                             "--format=csv,noheader,nounits"],
                            capture_output=True, text=True, check=True, timeout=30)
    rows = []
    for line in result.stdout.splitlines():
        index, free = line.split(",")
        rows.append({"index": int(index), "free_mib": int(free)})
    return sorted(rows, key=lambda row: (-row["free_mib"], row["index"]))


def pick_card(min_free_mib, wait_seconds, poll=60):
    """Measure, never remember: the cards are shared with another user."""
    deadline = time.monotonic() + wait_seconds
    while True:
        cards = free_cards()
        if cards and cards[0]["free_mib"] >= min_free_mib:
            return cards[0]
        if time.monotonic() >= deadline:
            raise RuntimeError(f"no card reached {min_free_mib} MiB free: {cards}")
        time.sleep(poll)


def run(command, card, log):
    with Path(log).open("a") as stream:
        stream.write(f"\n$ {' '.join(command)}\n")
        stream.flush()
        return subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                              env={**os.environ, "CUDA_VISIBLE_DEVICES": str(card)})


def train_command(args, arm, seed, out, resume):
    command = [sys.executable, str(HERE / "train_factorial.py"),
               "--dataset", str(args.dataset), "--init", str(args.init_root / f"modern-seed{seed}"),
               "--out", str(out), "--arm", arm, "--seed", str(seed),
               "--updates", str(args.updates), "--batch-size", str(args.batch_size),
               "--block-size", str(args.block_size), "--lr", str(args.lr),
               "--warmup", str(args.warmup), "--device", "cuda:0"]
    return command + (["--resume"] if resume else [])


def score_commands(args, out):
    candidates = out / "candidates.jsonl"
    return ([sys.executable, str(HERE / "sample_candidates.py"), "--checkpoint", str(out),
             "--manifest", str(args.dataset / "eval_synthesis.jsonl"),
             "--out", str(candidates), "--max-new-tokens", str(args.max_new_tokens),
             "--device", "cuda:0"],
            [sys.executable, str(HERE.parent / "t" / "score_synthesis.py"),
             "--manifest", str(args.dataset / "eval_synthesis.jsonl"),
             "--candidates", str(candidates), "--out", str(out / "score.json")])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--init-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1337, 7, 42])
    parser.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS),
                        help="a subset runs a diagnostic, not the registered factorial")
    parser.add_argument("--order-seed", type=int, default=20260919)
    parser.add_argument("--updates", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--block-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--max-new-tokens", type=int, default=200)
    parser.add_argument("--min-free-mib", type=int, default=14 * 1024)
    parser.add_argument("--wait-seconds", type=int, default=3600)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "logs").mkdir(exist_ok=True)
    ledger_path = args.out / "study.json"
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text())
    else:
        rng = random.Random(args.order_seed)
        blocks = []
        for seed in args.seeds:
            order = [arm for arm in ARMS if arm in args.arms]
            rng.shuffle(order)
            blocks.append({"seed": seed, "order": order,
                           "arms": [{"id": f"{arm}-seed{seed}", "arm": arm, "seed": seed,
                                     "status": "pending", "attempts": []} for arm in order]})
        ledger = {"schema": SCHEMA, "created": utc_now(), "order_seed": args.order_seed,
                  "dataset": str(args.dataset), "init_root": str(args.init_root),
                  "config": {"updates": args.updates, "batch_size": args.batch_size,
                             "block_size": args.block_size, "lr": args.lr,
                             "warmup": args.warmup, "max_new_tokens": args.max_new_tokens},
                  "blocks": blocks}
        ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")

    def save():
        ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")

    for block in ledger["blocks"]:
        for entry in block["arms"]:
            if entry["status"] == "complete":
                continue
            out = args.out / entry["id"]
            log = args.out / "logs" / f"{entry['id']}.log"
            resume = bool(entry["attempts"]) and (out / "state.pt").exists()
            card = pick_card(args.min_free_mib, args.wait_seconds)
            attempt = {"started": utc_now(), "card": card, "resume": resume}
            entry["status"], entry["attempts"] = "running", entry["attempts"] + [attempt]
            save()
            started = time.monotonic()
            result = run(train_command(args, entry["arm"], entry["seed"], out, resume),
                         card["index"], log)
            attempt["train_returncode"] = result.returncode
            if result.returncode:
                attempt["ended"], entry["status"] = utc_now(), "failed"
                save()
                continue
            sample, scorer = score_commands(args, out)
            attempt["sample_returncode"] = run(sample, card["index"], log).returncode
            attempt["score_returncode"] = run(scorer, card["index"], log).returncode
            attempt["wall_seconds"] = time.monotonic() - started
            attempt["ended"] = utc_now()
            failed = attempt["sample_returncode"] or attempt["score_returncode"]
            entry["status"] = "failed" if failed else "complete"
            if not failed:
                report = json.loads((out / "score.json").read_text())
                entry["score"] = {"verdicts": report["verdicts"], "by_split": report["by_split"],
                                  "tests_by_stratum": report["tests_by_stratum"]}
            save()
    pending = [entry["id"] for block in ledger["blocks"] for entry in block["arms"]
               if entry["status"] != "complete"]
    print(json.dumps({"out": str(args.out), "complete": not pending, "unfinished": pending}))
    return 1 if pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
