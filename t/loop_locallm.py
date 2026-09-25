#!/usr/bin/env python3
"""t/loop_locallm.py -- locallm inside the loop (2026-09-16).

locallm builds a model from nothing on this machine; t decides what it may
learn from. Three steps, each writing files the next one reads:

  corpus    the clean water only: every task that reads verified / refuted in
            all seven kernels, from
              - the SFT sets loop_dataset.py wrote (a model's answer that also
                passes the problem's own tests; train split only), written as
                "Problem: <English>" and "Signature: <fn>(<kinds>) -> <ret>"
                lines followed by the t task, so the model learns to answer;
              - the lifted DafnyBench tasks whose row in the sweep table reads
                all seven, and the committed t/tasks whose row in
                AGREEMENT.md does, written as the t task alone.
  train     locallm/train.py on that corpus, from random numbers.
  generate  one answer per held-out problem (the split's eval ids, never in
            the corpus), written as out/spec-experiment/<tag>/raw/<id>.json in
            spec_experiment.py's record shape, so its extract, tests and
            run_par.py grade locallm exactly as they grade every other model.

Run the python that has torch (~/.venv-train/bin/python) for train and
generate; corpus is standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCALLM = HERE.parent / "locallm"
sys.path.insert(0, str(HERE))

import spec_experiment as se                                    # noqa: E402
import loop_filter                                               # noqa: E402
import surface                                                  # noqa: E402

OUT = HERE / "out" / "loop-locallm"
CLEAN = "verified / refuted"


def signature(entry: dict) -> str:
    kinds = ", ".join(a[0] for a in entry["points"][0]["args"])
    return f"{entry['fn']}({kinds}) -> {entry['points'][0]['expected'][0]}"


def discriminative(points: list, n: int) -> list:
    """The examples that rule out the most obvious wrong functions, not the first ones.

    TiCoder (arXiv:2208.05950) selects the test that best *separates* candidate
    implementations, because an example every candidate agrees on teaches
    nothing; it reports about 46% relative pass@1 improvement within five
    interactions. We have the ground-truth examples already, so the interaction
    is free: rank a problem's own assertions by how many degenerate hypotheses
    each one refutes, and show those.

    The degenerate set is drawn from the failures actually measured here on
    2026-09-20, where a model asked whether a number is a sum of non-zero powers
    of two specified `r == x + 1`. An example whose answer happens to equal
    `x + 1` cannot rule that out; one whose answer does not, rules it out at a
    glance.

    Ties keep the problem's own order, so the choice is deterministic.
    """
    def refuted(point) -> int:
        try:
            args = [v for _k, v in point["args"]]
            out = point["expected"][1]
        except (KeyError, IndexError, TypeError):
            return 0
        first = args[0] if args else None
        guesses = [first, 0, False, True, []]
        if isinstance(first, bool):
            guesses.append(not first)
        elif isinstance(first, int):
            guesses += [first + 1, first - 1, -first, first * 2]
        elif isinstance(first, (list, tuple)):
            guesses += [len(first), list(first), list(reversed(list(first)))]
        return sum(1 for g in guesses if g != out)

    ranked = sorted(enumerate(points), key=lambda pair: (-refuted(pair[1]), pair[0]))
    return [point for _index, point in ranked[:n]]


def examples(entry: dict, n: int = 2) -> str:
    """The problem's own assertions, in the head, as `fn(args) == value` lines.

    The measured reason this exists: the signature line took signature failures
    from 40.8 percent to 12.1 and turned 2 clean answers into 3 (round 8,
    2026-09-19), because it pinned the types the model had been inventing. The
    population that remains is proven-but-wrong: 59 to 204 answers a round where
    all seven verifiers agree the program meets the specification the model
    wrote and the problem's tests still fail. An example pins the semantics the
    way the signature pinned the types.

    Anything a model is given here, every model must be given: a held-out
    comparison run with examples has to regrade its baselines with examples.
    """
    lines = []
    for point in discriminative(entry.get("points", []), n):
        try:
            args = ", ".join(json.dumps(value) for _kind, value in point["args"])
            lines.append(f"Example: {entry['fn']}({args}) == {json.dumps(point['expected'][1])}\n")
        except (KeyError, IndexError, TypeError, ValueError):
            continue          # a point this shape cannot be printed is simply not shown
    return "".join(lines)


def problem_head(entry: dict, with_examples: bool = False) -> str:
    text = " ".join(entry["rec"]["text"].split())
    head = f"Problem: {text}\nSignature: {signature(entry)}\n"
    return head + examples(entry) if with_examples else head


def held_out(split_path: str) -> set[int]:
    """The ids no corpus may contain, read from the split that defines them.

    Issue #30: the builder applied no split filter at all. `--sft` trusted its
    input file and `--lifted` added MBPP-DFY-derived tasks with no check, and
    MBPP-DFY is derived from the same MBPP the held-out split is drawn from, so
    nothing but luck kept an evaluation problem out of training. Measured
    2026-09-20, luck held: four current corpora and both historical ones contain
    0 of 232 held-out ids. `t/preflight.py` checks this after the fact; this
    stops it at the point the corpus is built, which is the only place it can be
    stopped before a model has already seen the problem.

    """
    if not split_path:
        raise SystemExit("corpus construction requires --split; no unscoped training corpus is permitted")
    try:
        return {int(i) for i in json.loads(Path(split_path).read_text(encoding="utf-8"))["eval_ids"]}
    except (OSError, KeyError, ValueError) as e:
        raise SystemExit(f"cannot read held-out ids from {split_path}: {e}")


def mbpp_id(name: str) -> int | None:
    """The MBPP number a task name stands for, or None."""
    task_id = loop_filter.problem_id(name)
    return task_id if task_id is not None and task_id < se.HUMANEVAL_BASE else None


def clean_rows(table: Path) -> set[str]:
    rows = set()
    for line in table.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 8 and cells[0] != "task" and all(c == CLEAN for c in cells[1:]):
            rows.add(cells[0])
    return rows


# The corpus builder drops unsafe documents; preflight and continuation use the
# same validator to refuse unsafe files. Keep the old local name for callers.
Gate = loop_filter.TrainingDataGate


def cmd_corpus(a) -> int:
    pool = se.pool(a.pool)
    docs, n_sft, n_lift, n_committed = [], 0, 0, 0
    evil = held_out(a.split)      # ids that must not appear anywhere below
    gate = Gate(evil)
    if a.base:
        # an existing corpus (e.g. t/runs/2026-09-16/loop-data/corpus.txt, which
        # already holds the lifted and committed tasks) under the new answers
        text = Path(a.base).read_text(encoding="utf-8")
        # Signature: belongs here for the same reason it belongs in the answer
        # splitter below: a corpus whose documents start with a head must be
        # split at every head this project writes, or two documents become one.
        for d in re.split(r"\n\s*\n(?=Problem: |Signature: |t \d)", text):
            if not d.strip():
                continue
            # the base corpus was built by an older run that may not have filtered
            if gate.admit(d, loop_filter.task_names(d)):
                docs.append(d.strip() + "\n")
    for sft in a.sft:
        for line in Path(sft).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            m = re.search(r"```t\n(.*?)```", r["chosen"], re.S)
            entry = pool.get(r["task_id"]) or pool.get(int(r["task_id"]))
            try:
                task_id = int(r["task_id"])
            except (TypeError, ValueError):
                task_id = None
            body = m.group(1) if m else ""
            if not gate.admit(body, [r.get("task")] + loop_filter.task_names(body),
                              {task_id} if task_id is not None else set()):
                continue
            if m and entry:
                docs.append(problem_head(entry, a.examples) + m.group(1).strip() + "\n")
                n_sft += 1
    if a.lifted:
        keep = clean_rows(HERE / "COVERAGE-lifted-785.md")
        for f in sorted((HERE / "out" / "lifted-tasks").glob("*.json")):
            task = json.loads(f.read_text(encoding="utf-8"))
            if task.get("name") in keep:
                doc = surface.print_task(task).strip() + "\n"
                if gate.admit(doc, [task.get("name")]):
                    docs.append(doc)
                    n_lift += 1
        keep = clean_rows(HERE / "AGREEMENT.md")
        for f in sorted((HERE / "tasks").glob("*.t")):
            task = surface.parse_file(str(f))
            if task.get("name") in keep:
                doc = surface.print_task(task).strip() + "\n"
                if gate.admit(doc, [task.get("name")]):
                    docs.append(doc)
                    n_committed += 1
    seen, unique = set(), []
    for d in docs:               # the base corpus may already hold the same answers
        if d not in seen:
            seen.add(d)
            unique.append(d)
    docs = unique
    corpus_text = "\n\n".join(docs)
    final = loop_filter.validate_training_data(corpus_text, evil)
    if not final.ok:
        detail = (loop_filter.held_out_detail(final.held_out) if final.held_out
                  else loop_filter.same_task_detail(final))
        raise SystemExit(f"refusing to write an unsafe training corpus: {detail}")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(corpus_text + "\n", encoding="utf-8")
    print(f"corpus {out}: {len(docs)} documents (base {a.base or 'none'}, {n_sft} problem answers, {n_lift} lifted, "
          f"{n_committed} committed), {out.stat().st_size} bytes")
    if evil:
        print(f"held-out filter: {len(evil)} ids from {a.split}, {len(gate.held)} document(s) excluded"
              + (f": {', '.join(gate.held)}" if gate.held else ""))
    print(f"decontamination filter: {len(gate.decontaminated)} document(s) excluded"
          + (f": {', '.join(gate.decontaminated)}" if gate.decontaminated else ""))
    return 0


def cmd_train(a) -> int:
    if a.width % a.heads:
        # locallm/model.py asserts this several frames down, where the message is the word AssertionError and
        # nothing else; a width of 512 with the default 6 heads spent a step of t lab saying that (2026-09-18)
        ok = [h for h in (2, 4, 8, 16) if a.width % h == 0]
        raise SystemExit(f"a width of {a.width} does not divide into {a.heads} heads; "
                         f"pass --heads {max(ok) if ok else 1} or another divisor of {a.width}")
    cmd = [sys.executable, "train.py", "--data", str(Path(a.corpus).resolve()), "--out", str(Path(a.model).resolve()),
           "--steps", str(a.steps), "--block-size", str(a.block), "--n-layer", str(a.layers),
           "--n-head", str(a.heads), "--n-embd", str(a.width), "--batch-size", str(a.batch), "--seed", str(a.seed),
           "--architecture", a.architecture, "--tokenizer", a.tokenizer, "--vocab-size", str(a.vocab_size)]
    if a.gradient_checkpointing:
        cmd.append("--gradient-checkpointing")
    env = dict(os.environ, LOCALLM_RUN_LOG=str(Path(a.model).resolve() / "runs.jsonl"))
    r = subprocess.run(cmd, cwd=LOCALLM, env=env)
    return r.returncode


def cmd_generate(a) -> int:
    import torch
    sys.path.insert(0, str(LOCALLM))
    import checkpoint
    split = json.loads(Path(a.split).read_text(encoding="utf-8"))
    pool = se.pool(split.get("pool", "v1"))
    # which problems to answer: the split's held-out ids by default, or the ones named in --ids-file, so the
    # model can answer TRAINING problems and have its own failures graded and fed back (2026-09-17)
    which = "train_ids" if getattr(a, "train", False) else "eval_ids"
    ids = sorted(int(i) for i in split[which])
    if getattr(a, "ids_file", ""):
        ids = sorted(int(x) for x in Path(a.ids_file).read_text().split())
    d = se.outdir(a.tag)
    model, tok, _ = checkpoint.load_checkpoint(a.model)
    params = sum(p.numel() for p in model.parameters())
    torch.manual_seed(a.seed)
    for i, tid in enumerate(ids):
        entry = pool.get(tid) or pool.get(str(tid))
        path = d / "raw" / f"{tid}.json"
        if entry is None or path.exists():
            continue
        head = problem_head(entry, a.examples)
        text = checkpoint.sample(model, tok, head, a.tokens, temperature=a.temperature,
                                 top_k=a.top_k, use_cache=a.use_cache)
        body = text[len(head):] if text.startswith(head) else text
        # A corpus whose documents begin with a head teaches the model to emit that
        # head between documents, so the boundary the answer ends at must know
        # about every head this project writes -- 2026-09-19, when a Signature:
        # corpus left two programs in one reply and 216 of 232 answers unparseable.
        body = re.split(r"\n\s*\n(?=Problem: |Signature: |t \d)", body, maxsplit=1)[0]
        # A corpus whose documents START with a head teaches the model to start
        # its answer with one. Measured 2026-09-20: trained on the examples
        # corpus, every one of 24 replies opened with `Example:` lines before
        # `t 1`, and all 24 failed to extract. The splitter above cuts at the
        # next document; this removes a head in front of this one. Third time
        # this family has bitten: the answer splitter, then the copy check's
        # stripper, now the extractor's input.
        body = loop_filter.strip_head(body)
        record = {"task_id": tid, "fn": entry["fn"], "model": f"locallm:{a.model}", "digest": f"{params} params",
                  "pool_version": split.get("pool", "v1"), "prompt_version": "locallm-head",
                  "options": {"temperature": a.temperature, "top_k": a.top_k, "max_new_tokens": a.tokens,
                              "tokenizer": type(tok).__name__, "seed": a.seed},
                  "messages": [{"role": "user", "content": head}],
                  "reply": "```t\n" + body.strip() + "\n```", "done_reason": "length"}
        path.write_text(json.dumps(record, indent=1), encoding="utf-8")
        if (i + 1) % 25 == 0:
            print(f"generate: {i + 1} of {len(ids)}", flush=True)
    print(f"generate: {len(ids)} held-out problems answered into {d}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("corpus")
    p.add_argument("--sft", nargs="*", default=[])
    p.add_argument("--pool", default="v3")
    p.add_argument("--lifted", action="store_true", help="add the lifted and committed tasks that read all seven")
    p.add_argument("--base", default="", help="start from this corpus file (documents split at blank lines)")
    p.add_argument("--out", default=str(OUT / "corpus.txt"))
    p.add_argument("--examples", action="store_true",
                   help="put the problem's own assertions in the head; every model "
                        "compared against a model trained this way must get them too")
    p.add_argument("--split", type=Path, required=True,
                   help="the evaluation split whose eval_ids are excluded from every source; "
                        "a corpus build without this boundary is refused")
    p = sub.add_parser("train")
    p.add_argument("--corpus", default=str(OUT / "corpus.txt"))
    p.add_argument("--model", default=str(OUT / "model"))
    p.add_argument("--steps", type=int, default=3000)
    p.add_argument("--block", type=int, default=512)
    p.add_argument("--layers", type=int, default=6)
    p.add_argument("--heads", type=int, default=6)
    p.add_argument("--width", type=int, default=384)
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--architecture", choices=("gpt", "modern"), default="gpt")
    p.add_argument("--tokenizer", choices=("char", "bpe"), default="char")
    p.add_argument("--vocab-size", type=int, default=8192)
    p.add_argument("--gradient-checkpointing", action="store_true")
    p = sub.add_parser("generate")
    p.add_argument("--model", default=str(OUT / "model"))
    p.add_argument("--tag", required=True)
    p.add_argument("--ids-file", default="", help="answer only these task ids, one per line")
    p.add_argument("--train", action="store_true", help="answer the split's training problems, not its held-out ones")
    p.add_argument("--split", default=str(HERE / "out" / "loop" / "split-v3.json"))
    p.add_argument("--tokens", "--chars", dest="tokens", type=int, default=1200,
                   help="maximum new tokens; --chars is the historical character-tokenizer alias")
    p.add_argument("--temperature", type=float, default=0.5)
    p.add_argument("--top-k", type=int, default=20)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--examples", action="store_true",
                   help="ask with the problem's own assertions in the prompt")
    p.add_argument("--use-cache", action="store_true",
                   help="cached decoding, off by default. locallm/FINDINGS-kv-cache-2026-09-19.md "
                        "verified it produces identical output and its registered speed prediction "
                        "failed on a different benchmark; it has never been measured on this path, "
                        "so register a prediction before quoting a speedup")
    a = ap.parse_args()
    return {"corpus": cmd_corpus, "train": cmd_train, "generate": cmd_generate}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
