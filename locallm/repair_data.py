"""repair_data.py: conversations where the t tool rejects the model's own draft and the proved program follows.

    # 1. K mid models, each trained without one fold of the training conversations
    python3 locallm/repair_data.py folds  --conversations conv.jsonl --core <core dir> --out <dir>
    # 2. each fold's training problems drafted by the model that never saw them
    python3 locallm/repair_data.py drafts --conversations conv.jsonl --out <dir>
    # 3. repair and pass conversations from the drafts
    python3 locallm/repair_data.py build  --conversations conv.jsonl --out <dir> --core <core dir>

The first chat pipeline run (DAWNR-PIPELINE.md) showed the model calling the t
tool on its draft, the tool finding real faults, and the model ending there.
This builds the data that shows what to do next, from TRAINING problems only.

Taken from SAFE (Chen et al., arXiv:2410.15756): a verifier's rejected
attempts are not thrown away; the triple (incorrect attempt, the verifier's
error on it, the correct attempt) is self-debugging training data, with the
wrong attempt and the error as input and the fix as the target. Here: the
draft inside a tool call, its text unsupervised (chat.py's "train": false);
the t tool's real verdict (tool output, never supervised); the proved corpus
program in a second call (supervised) with the tool's real verdict on it; the
end. Taken from STaR (Zelikman et al., arXiv:2203.14465): an answer that went
wrong is trained toward the correct answer rather than dropped; ours needs no
generated rationale, since the correct program is the proved document.

Where the drafts come from, and why. SCoRe (Kumar et al., arXiv:2409.12917)
found SFT on offline correction traces fails when the mistakes in the data are
not the ones the model makes itself. The mid model trained on every training
conversation has memorised them (train loss 0.015 in the first run), so its
drafts on its own training problems are recitations. So the drafts are
cross-fitted (K-fold sample splitting, Chernozhukov et al., arXiv:1608.00060):
the training conversations are put in K folds by a salted hash of the user
turn, a mid model is trained with the same recipe on the other K-1 folds, and
it drafts its own fold, whose problems it never saw. SCoRe's other failure,
collapse onto one correction behaviour, is why drafts that pass and ARE the
proved program become pass conversations (call, verdict, end) beside the
repairs. A draft that passes the examples but is not the proved program is not
trained on (two examples passed; nothing proved it) and is counted.

Only training-side conversations are drafted; validation conversations and
dev problems are never asked. Every built conversation passes the trainers'
gates (chat_data.gate: held-out ids under any alias, same-task sources, dev
ids); one that is refused is dropped and named in the summary, and one longer
than the model's context is dropped and counted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "t"))

_FOLD_SALT = b"dawnr-repair-fold"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fold_of(conv: dict, folds: int) -> int:
    user = conv["messages"][0]["content"]
    return int.from_bytes(hashlib.sha256(_FOLD_SALT + b"\x00" + user.encode("utf-8")).digest()[:8], "big") % folds


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def training_rows(convs: list[dict]) -> list[tuple[int, dict]]:
    """(index in the file, conversation) for every training-side conversation."""
    return [(i, c) for i, c in enumerate(convs) if c.get("split", "train") == "train"]


def norm(program: str | None) -> str:
    return " ".join((program or "").split())


def first_program(parts: list[dict]) -> str | None:
    """The first program a reply writes: its first tool call, else its text."""
    calls = [p["text"] for p in parts if p.get("type") == "t"]
    if calls:
        return calls[0].strip("\n") + "\n" if calls[0].strip() else None
    text = "".join(p["text"] for p in parts if p.get("type") == "text").strip()
    return text + "\n" if text else None


def verdict_ok(verdict: str) -> bool:
    """Nothing wrong in a t-tool verdict: parses, well formed, every example passes."""
    lines = [ln for ln in verdict.split("\n") if ln.strip()]
    return bool(lines) and all(ln in ("parses: yes", "well formed: yes") or
                               (ln.startswith("example ") and ln.endswith(": pass")) for ln in lines)


def verdict_kind(verdict: str) -> str:
    if verdict.startswith("parses: no"):
        return "does not parse"
    if "well formed: no" in verdict:
        return "not well formed"
    if verdict_ok(verdict):
        return "passes"
    if any(": fail:" in ln for ln in verdict.split("\n")):
        return "wrong output"
    return "other (undefined, budget, crash, cannot run)"


# ---------------------------------------------------------------- folds --

def cmd_folds(a) -> int:
    convs = load(a.conversations)
    rows = training_rows(convs)
    a.out.mkdir(parents=True, exist_ok=True)
    for k in range(a.folds):
        fold_dir = a.out / f"fold-{k}"
        fold_dir.mkdir(parents=True, exist_ok=True)
        train = [c for _, c in rows if fold_of(c, a.folds) != k]
        path = fold_dir / "train.jsonl"
        path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in train), encoding="utf-8")
        model = fold_dir / "model"
        run = model / "run.json"
        if run.is_file():
            rec = json.loads(run.read_text())
            if rec.get("status") == "complete" and rec["identities"]["conversations_sha256"] == \
                    hashlib.sha256(path.read_bytes()).hexdigest() and rec["identities"]["steps"] == a.steps:
                print(f"[fold {k}] trained already on these conversations; skipped", flush=True)
                continue
        cmd = [sys.executable, "chat_train.py", "--init", str(a.core), "--conversations", str(path),
               "--out", str(model), "--steps", str(a.steps), "--lr", str(a.lr), "--batch-size", str(a.batch_size),
               "--block-size", "0", "--seed", str(a.seed), "--eval-every", str(a.eval_every)]
        print(f"[fold {k}] {len(train)} training conversations, {len(rows) - len(train)} held out", flush=True)
        with (fold_dir / "log.txt").open("a") as log:
            r = subprocess.run(cmd, cwd=str(HERE), stdout=log, stderr=subprocess.STDOUT)
        if r.returncode:
            raise SystemExit(f"fold {k}: chat_train.py failed; see {fold_dir / 'log.txt'}")
        (model / "state.pt").unlink(missing_ok=True)            # 1.1 GB each; a finished fold is not resumed
    return 0


# --------------------------------------------------------------- drafts --

def cmd_drafts(a) -> int:
    import chat
    import t_tool
    from checkpoint import load_checkpoint
    from engine import Engine, reply_parts
    convs = load(a.conversations)
    rows = training_rows(convs)
    out = a.out / "drafts.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for k in range(a.folds):
            model, tok, _ = load_checkpoint(a.out / f"fold-{k}" / "model", a.device)
            engine = Engine(model, tok, grammar=True)
            mine = [(i, c) for i, c in rows if fold_of(c, a.folds) == k]
            print(f"[fold {k}] drafting {len(mine)} conversations", flush=True)
            for i, c in mine:
                user = c["messages"][0]["content"]
                prompt = chat.render_for_completion(tok, {"messages": [{"role": "user", "content": user}]})
                greedy, _ = engine.generate_batch(prompt, 1, max_tokens=a.max_tokens, temperature=0.0, seed=0)
                sampled = []
                if a.samples:
                    sampled, _ = engine.generate_batch(prompt, a.samples, max_tokens=a.max_tokens,
                                                       temperature=a.temperature, top_k=a.top_k,
                                                       seed=a.seed * 100_003 + i)
                for s, tokens in enumerate(greedy + sampled):
                    draft = first_program(reply_parts(tok, tokens))
                    verdict = t_tool.call(draft, user) if draft else None
                    f.write(json.dumps({"index": i, "user_sha256": sha256_text(user), "source": c.get("source"),
                                        "fold": k, "sample": s, "draft": draft, "verdict": verdict}) + "\n")
            del engine, model
    print(json.dumps({"drafts": str(out)}))
    return 0


# ---------------------------------------------------------------- build --

def repair_conversation(conv: dict, draft: str, verdict: str, proved: str, proved_verdict: str) -> dict:
    user = conv["messages"][0]["content"]
    return {"messages": [{"role": "user", "content": user},
                         {"role": "assistant", "content": [
                             {"type": "t", "text": draft, "train": False},
                             {"type": "t_output", "text": verdict},
                             {"type": "t", "text": proved},
                             {"type": "t_output", "text": proved_verdict}]}],
            "source": conv.get("source"), "kind": conv.get("kind"), "tool": True,
            "examples": conv.get("examples"), "split": "train", "built": "repair"}


def pass_conversation(conv: dict, proved: str, proved_verdict: str) -> dict:
    user = conv["messages"][0]["content"]
    return {"messages": [{"role": "user", "content": user},
                         {"role": "assistant", "content": [{"type": "t", "text": proved},
                                                           {"type": "t_output", "text": proved_verdict}]}],
            "source": conv.get("source"), "kind": conv.get("kind"), "tool": True,
            "examples": conv.get("examples"), "split": "train", "built": "pass"}


def build(convs: list[dict], drafts: list[dict], *, max_repairs: int = 2, max_passes: int = 1,
          fits=None, gate=None) -> tuple[list[dict], dict]:
    """Repair and pass conversations from drafts of training conversations; and a summary.

    fits(conv) -> bool drops a conversation too long for the model; gate(conv)
    raises ValueError for one the trainers would refuse (it is dropped by name).
    """
    import chat
    import t_tool
    from collections import Counter, defaultdict
    by_index = defaultdict(list)
    for d in drafts:
        by_index[d["index"]].append(d)
    out, counts, kinds = [], Counter(), Counter()
    refused, per_sample = [], defaultdict(Counter)
    for i, rows in sorted(by_index.items()):
        conv = convs[i]
        if conv.get("split", "train") != "train":
            raise ValueError(f"draft {i} ({conv.get('source')}) is of a {conv.get('split')} conversation; "
                             f"only training conversations are drafted")
        user = conv["messages"][0]["content"]
        if any(d["user_sha256"] != sha256_text(user) for d in rows):
            raise ValueError(f"drafts for conversation {i} were made from another prompt; rebuild the drafts")
        proved = chat.final_program(conv["messages"][1]["content"])
        proved = proved.strip("\n") + "\n"
        proved_verdict = t_tool.call(proved, user)
        if not verdict_ok(proved_verdict):
            counts["proved_program_fails_its_examples"] += 1
            continue
        counts["problems"] += 1
        seen, repairs, passes = set(), 0, 0
        for d in sorted(rows, key=lambda r: r["sample"]):
            counts["drafts"] += 1
            tag = "greedy" if d["sample"] == 0 else "sampled"
            if not d["draft"]:
                counts["no_program"] += 1
                per_sample[tag]["no program"] += 1
                continue
            kind = verdict_kind(d["verdict"])
            kinds[kind] += 1
            is_proved = norm(d["draft"]) == norm(proved)
            per_sample[tag][kind] += 1
            per_sample[tag]["is the proved program"] += is_proved
            if verdict_ok(d["verdict"]):
                if not is_proved:
                    counts["passed_not_proved"] += 1
                    continue
                if passes >= max_passes:
                    counts["pass_over_cap"] += 1
                    continue
                built = pass_conversation(conv, proved, proved_verdict)
            else:
                if norm(d["draft"]) in seen:
                    counts["repeated_failing_draft"] += 1
                    continue
                if repairs >= max_repairs:
                    counts["repair_over_cap"] += 1
                    continue
                built = repair_conversation(conv, d["draft"], d["verdict"], proved, proved_verdict)
            if fits is not None and not fits(built):
                counts["over_context"] += 1
                continue
            if gate is not None:
                try:
                    gate(built)
                except ValueError as e:
                    refused.append({"index": i, "source": conv.get("source"), "why": str(e)[:300]})
                    continue
            if built["built"] == "repair":
                seen.add(norm(d["draft"]))
                repairs += 1
            else:
                passes += 1
            out.append(dict(built, draft_fold=d["fold"], draft_sample=d["sample"]))
        counts["problems_with_repair"] += repairs > 0
        counts["problems_with_pass"] += passes > 0
    summary = {**dict(counts), "repair_conversations": sum(r["built"] == "repair" for r in out),
               "pass_conversations": sum(r["built"] == "pass" for r in out), "draft_verdicts": dict(kinds),
               "by_draft": {k: dict(v) for k, v in per_sample.items()}, "refused_by_gate": refused,
               "max_repairs": max_repairs, "max_passes": max_passes}
    return out, summary


def cmd_build(a) -> int:
    import chat
    import chat_data
    from data import load_tokenizer
    convs = load(a.conversations)
    drafts = load(a.out / "drafts.jsonl")
    tok = chat.with_chat_tokens(load_tokenizer(a.core / "tokenizer.json"))
    import torch
    context = torch.load(a.core / "ckpt.pt", map_location="cpu", weights_only=True)["config"]["block_size"]

    def fits(conv):
        return len(chat.render_conversation(tok, conv)[0]) - 1 <= context

    def gate(conv):
        chat_data.gate(json.dumps(conv, ensure_ascii=False), f"repair conversation {conv.get('source')}", a.split)

    rows, summary = build(convs, drafts, max_repairs=a.max_repairs, max_passes=a.max_passes, fits=fits, gate=gate)
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    gate_all = "\n\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    chat_data.gate(gate_all, "repair conversations", a.split)            # the whole file, as the trainers see it
    path = a.out / "repairs.jsonl"
    path.write_text(text, encoding="utf-8")
    greedy = [d for d in drafts if d["sample"] == 0]
    summary.update({"conversations": str(a.conversations),
                    "conversations_sha256": hashlib.sha256(a.conversations.read_bytes()).hexdigest(),
                    "context": context, "file": str(path),
                    "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    summary["greedy_drafts_on_unseen_training_problems"] = {
        "asked": len(greedy),
        "well_formed": sum(bool(d["verdict"]) and "well formed: yes" in d["verdict"] for d in greedy),
        "every_example_passes": sum(bool(d["verdict"]) and verdict_ok(d["verdict"]) and "example 1" in d["verdict"]
                                    for d in greedy),
        "proved_program_exactly": sum(norm(d["draft"]) == norm(chat.final_program(convs[d["index"]]["messages"][1]
                                                                                  ["content"])) for d in greedy)}
    (a.out / "repairs.summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "refused_by_gate"}
                     | {"refused_by_gate": len(summary["refused_by_gate"])}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("folds", "drafts", "build"):
        p = sub.add_parser(name)
        p.add_argument("--conversations", type=Path, required=True, help="chat_data.py JSONL")
        p.add_argument("--out", type=Path, required=True, help="working directory: fold models, drafts, repairs")
        p.add_argument("--folds", type=int, default=5)
        p.add_argument("--seed", type=int, default=1337)
        if name in ("folds", "build"):
            p.add_argument("--core", type=Path, required=True, help="the core checkpoint the mid stage starts from")
        if name == "folds":
            p.add_argument("--steps", type=int, default=400)
            p.add_argument("--lr", type=float, default=1e-4)
            p.add_argument("--batch-size", type=int, default=8)
            p.add_argument("--eval-every", type=int, default=50)
        if name == "drafts":
            p.add_argument("--samples", type=int, default=3, help="sampled drafts per problem, beside the greedy one")
            p.add_argument("--temperature", type=float, default=1.0)
            p.add_argument("--top-k", type=int, default=50)
            p.add_argument("--max-tokens", type=int, default=400)
            p.add_argument("--device", default=None)
        if name == "build":
            p.add_argument("--split", type=Path, default=ROOT / "t" / "out" / "loop" / "split-v5.json")
            p.add_argument("--max-repairs", type=int, default=2)
            p.add_argument("--max-passes", type=int, default=1)
    a = ap.parse_args(argv)
    a.conversations, a.out = a.conversations.resolve(), a.out.resolve()
    if getattr(a, "core", None):
        a.core = a.core.resolve()
    return {"folds": cmd_folds, "drafts": cmd_drafts, "build": cmd_build}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
