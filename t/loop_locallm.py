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
import hashlib
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
# The boundary an answer ends at: the next head this project writes. A corpus
# whose documents begin with a head teaches the model to emit that head between
# documents (2026-09-19, when a Signature: corpus left two programs in one reply
# and 216 of 232 answers unparseable). One constant, because the stop rule in
# locallm/model.py has to stop at exactly the boundary this file cuts at.
REPLY_BOUNDARY = re.compile(r"\n\s*\n(?=Problem: |Signature: |t \d)")


def reply_cut(head: str, text: str) -> int | None:
    """Where the extraction ends the reply: the start of the first boundary
    match in the body, as an index into ``text``, or None while no boundary
    has appeared. Generation can stop there because the pattern has no end
    anchor and a literal lookahead, so a match in a prefix is the match in the
    full text (locallm/test_r12_decode.py proves the cut byte-identical)."""
    body_start = len(head) if text.startswith(head) else 0
    match = REPLY_BOUNDARY.search(text, body_start)
    return match.start() if match else None


def reply_stop(head: str):
    """The text-level stop that locallm.checkpoint.sample and sample_batch take."""
    return lambda text: reply_cut(head, text)


def per_problem_seed(seed: int, task_id: int) -> int:
    """torch.manual_seed input from (seed, task_id): the sha256 scheme of
    t/loop_generate.py derive_seed, so a resume or another sharding draws the
    same sample for a problem instead of one that depends on what the process
    answered before it."""
    return int(hashlib.sha256(f"{seed}:{task_id}".encode("utf-8")).hexdigest()[:16], 16) % (2 ** 31 - 1)
AGREEMENT = HERE / "AGREEMENT.md"
COMMITTED_DIR = HERE / "tasks"
LIFTED_DIR = HERE / "out" / "lifted-tasks"
LIFTED_TABLE = HERE / "COVERAGE-lifted-785.md"
# What a resumed raw record must agree with this invocation on: the decoding
# options below, plus the model, its checkpoint hash, the pool and the prompt.
RESUME_OPTIONS = ("temperature", "top_k", "max_new_tokens", "seed", "tokenizer")


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


def table_rows(table: Path) -> dict[str, list[str]]:
    """Every task row of a seven-kernel table: name -> its seven cells."""
    rows = {}
    for line in table.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 8 and cells[0] != "task" and not set(cells[0]) <= set("-: "):
            rows[cells[0]] = cells[1:]
    return rows


def clean_rows(table: Path) -> set[str]:
    return {name for name, cells in table_rows(table).items() if all(c == CLEAN for c in cells)}


def committed_task_names(directory: Path | None = None) -> list[str]:
    """The name each committed task declares, read the way the builder reads it.

    A file that does not parse is a refusal by name, not a task that silently
    contributes nothing.
    """
    names = []
    for f in sorted((COMMITTED_DIR if directory is None else directory).glob("*.t")):
        try:
            names.append(surface.parse_file(str(f))["name"])
        except Exception as e:                                   # noqa: BLE001 -- name the file, whatever broke
            raise SystemExit(f"cannot read committed task {f.name}: {e}")
    return names


def agreement_gap(table: Path | None = None, directory: Path | None = None) -> tuple[dict[str, list[str]], list[str]]:
    """The table's task rows, and the committed tasks that have no row.

    A derived table has to cover every row of its source before anything reads
    it (Deequ's hasSize/isComplete, github.com/awslabs/deequ). On 2026-09-20 a
    one-task run_par.py sweep overwrote t/AGREEMENT.md, and the corpus builder
    then kept 1 of 35 committed tasks without a word.
    """
    table = AGREEMENT if table is None else table
    rows = table_rows(table) if table.exists() else {}
    missing = [name for name in committed_task_names(directory) if name not in rows]
    return rows, missing


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
        for d in REPLY_BOUNDARY.split(text):
            if not d.strip():
                continue
            # the base corpus was built by an older run that may not have filtered
            if gate.admit(d, loop_filter.task_names(d)):
                docs.append(d.strip() + "\n")
    # An SFT row that reaches no document is an incomplete input, named rather
    # than dropped: under --pool v5, 27 of 87 sft-r6 rows used to vanish with
    # exit 0 (review of 2026-09-21). Deequ's isComplete, github.com/awslabs/deequ.
    unusable = []
    for sft in a.sft:
        for number, line in enumerate(Path(sft).read_text(encoding="utf-8").splitlines(), 1):
            try:
                r = json.loads(line)
                task_id = int(r["task_id"])
                chosen = r["chosen"]
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
                raise SystemExit(f"{sft}:{number}: not an SFT row with an integer task_id and a chosen answer: {e}")
            m = re.search(r"```t\n(.*?)```", chosen, re.S)
            entry = pool.get(task_id) or pool.get(str(task_id))
            body = m.group(1) if m else ""
            if not gate.admit(body, [r.get("task")] + loop_filter.task_names(body), {task_id}):
                continue
            if m is None:
                unusable.append(f"{Path(sft).name}:{number} task_id={task_id} has no fenced t block")
            elif entry is None:
                unusable.append(f"{Path(sft).name}:{number} task_id={task_id} is not in pool {a.pool}")
            else:
                docs.append(problem_head(entry, a.examples) + m.group(1).strip() + "\n")
                n_sft += 1
    if unusable:
        raise SystemExit(f"{len(unusable)} SFT row(s) reach no document; the corpus would not equal its "
                         f"inputs: {unusable[:5]}" + (" ..." if len(unusable) > 5 else ""))
    if a.lifted:
        keep = clean_rows(LIFTED_TABLE)
        lifted = sorted(LIFTED_DIR.glob("*.json"))
        if not lifted:
            raise SystemExit(f"--lifted asked for the lifted tasks and {LIFTED_DIR} holds none; a corpus "
                             f"with 0 lifted documents is not the corpus this flag names")
        for f in lifted:
            task = json.loads(f.read_text(encoding="utf-8"))
            if task.get("name") in keep:
                doc = surface.print_task(task).strip() + "\n"
                if gate.admit(doc, [task.get("name")]):
                    docs.append(doc)
                    n_lift += 1
        rows, missing = agreement_gap(AGREEMENT, COMMITTED_DIR)
        if missing:
            raise SystemExit(f"{AGREEMENT.name} has rows for {len(rows)} task(s) and {COMMITTED_DIR.name}/ holds "
                             f"{len(rows) + len(missing)}; no row for {missing[:5]}"
                             + (" ..." if len(missing) > 5 else "")
                             + ". Regrade the committed tasks (bash t/grade_lab.sh matrix) and copy "
                             "t/out/AGREEMENT-lab.md over the table before building a corpus from it")
        keep = clean_rows(AGREEMENT)
        for f in sorted(COMMITTED_DIR.glob("*.t")):
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


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resume_conflicts(record: dict, expected: dict) -> list[str]:
    """Everything an existing raw record disagrees with this invocation on, as `field: recorded -> now`.

    A tag holds one decoding configuration and one model, or its numbers mean
    nothing (blocker A6: a dropped flag sampled the headline arm at 0.5 while
    its neighbours decoded greedily). Recorded parameters are compared with the
    current invocation before an output is reused, as Snakemake's
    --list-params-changes does
    (snakemake.readthedocs.io/en/stable/project_info/faq.html); we refuse
    instead of rerunning, since mixing is the defect. A record without a
    checkpoint hash predates the hash and is a difference: two checkpoints
    trained in place at one path are two models with one name.
    """
    out = []
    options = record.get("options") if isinstance(record.get("options"), dict) else {}
    for key in RESUME_OPTIONS:
        if options.get(key) != expected["options"][key]:
            out.append(f"options.{key}: {options.get(key)!r} -> {expected['options'][key]!r}")
    for key in ("model", "checkpoint_sha256", "pool_version"):
        if record.get(key) != expected[key]:
            if key == "model" and _same_model_path(record.get(key), expected[key]):
                continue
            out.append(f"{key}: {record.get(key)!r} -> {expected[key]!r}")
    messages = record.get("messages") or [{}]
    prompt = messages[0].get("content") if isinstance(messages[0], dict) else None
    if prompt != expected["prompt"]:
        out.append("prompt: the recorded head differs from the one this invocation builds "
                   "(a different --examples, pool or problem text)")
    return out


def _same_model_path(recorded, now) -> bool:
    """`locallm:<path>` strings naming one directory by two spellings."""
    prefix = "locallm:"
    if not (isinstance(recorded, str) and isinstance(now, str)
            and recorded.startswith(prefix) and now.startswith(prefix)):
        return False
    try:
        return Path(recorded[len(prefix):]).resolve() == Path(now[len(prefix):]).resolve()
    except OSError:
        return False


def cmd_generate(a) -> int:
    import torch
    sys.path.insert(0, str(LOCALLM))
    import checkpoint
    split = json.loads(Path(a.split).read_text(encoding="utf-8"))
    pool_version = split.get("pool", "v1")
    pool = se.pool(pool_version)
    # which problems to answer: the split's held-out ids by default, or the ones named in --ids-file, so the
    # model can answer TRAINING problems and have its own failures graded and fed back (2026-09-17)
    which = "train_ids" if getattr(a, "train", False) else "eval_ids"
    ids = sorted(int(i) for i in split[which])
    if getattr(a, "ids_file", ""):
        ids = sorted(int(x) for x in Path(a.ids_file).read_text().split())
    # Every requested id must be answerable before anything is generated
    # (PCheck, Xu et al. OSDI'16: check a setting where it is read, not where
    # it is used, so the error is not latent). An id the pool lacks used to be
    # skipped with exit 0, and the set then graded as whole (blocker A4).
    entries = {tid: pool.get(tid) or pool.get(str(tid)) for tid in ids}
    missing = [tid for tid, entry in entries.items() if entry is None]
    if missing:
        print(f"generate: {len(missing)} of {len(ids)} requested ids are not in pool {pool_version}: "
              f"{missing[:10]}" + (" ..." if len(missing) > 10 else ""), file=sys.stderr)
        return 1
    d = se.outdir(a.tag)
    model, tok, _ = checkpoint.load_checkpoint(a.model)
    params = sum(p.numel() for p in model.parameters())
    # --model may name a kept weights-only file (ckpt-step-N.pt beside the
    # rolling checkpoint, --keep-every) as well as a run directory
    ckpt = Path(a.model) if Path(a.model).is_file() else Path(a.model) / "ckpt.pt"
    if not ckpt.is_file():
        print(f"generate: {ckpt} is not a file, so the checkpoint cannot be hashed into the records",
              file=sys.stderr)
        return 1
    checkpoint_sha256 = file_sha256(ckpt)
    # "stop" and "seeding" name the two 2026-09-25 changes to how an answer is
    # made, so score_heldout's identical-options rule (A6) never mixes a set
    # made the old way with one made this way
    options = {"temperature": a.temperature, "top_k": a.top_k, "max_new_tokens": a.tokens,
               "tokenizer": type(tok).__name__, "seed": a.seed,
               "stop": "reply-boundary", "seeding": "per-problem"}
    conflicts, resumed = [], []
    for tid in ids:
        path = d / "raw" / f"{tid}.json"
        if not path.exists():
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as e:
            conflicts.append(f"{tid}: raw record unreadable ({e}); a kill mid-write leaves one, delete it by hand")
            continue
        expected = {"model": f"locallm:{a.model}", "checkpoint_sha256": checkpoint_sha256,
                    "pool_version": pool_version, "prompt": problem_head(entries[tid], a.examples),
                    "options": options}
        found = resume_conflicts(record, expected)
        conflicts.extend(f"{tid}: {c}" for c in found)
        if not found:
            resumed.append(tid)
    if conflicts:
        print(f"generate: refusing to resume into {d}: {len(conflicts)} difference(s) between the recorded "
              f"answers and this invocation, so the tag would mix two configurations:", file=sys.stderr)
        for c in conflicts[:20]:
            print(f"  {c}", file=sys.stderr)
        if len(conflicts) > 20:
            print(f"  ... and {len(conflicts) - 20} more", file=sys.stderr)
        return 2
    # Until 2026-09-25 torch was seeded once per process, so a sampled (T > 0)
    # answer depended on which ids the process answered before it, and a resume
    # or another sharding drew differently. Each problem is now seeded from
    # (seed, task_id) as t/loop_generate.py derive_seed does; old sampled sets
    # carry no options["seeding"] and are never mixed with new ones (A6).
    todo = [tid for tid in ids if tid not in resumed]
    for i, tid in enumerate(todo):
        entry = entries[tid]
        path = d / "raw" / f"{tid}.json"
        head = problem_head(entry, a.examples)
        torch.manual_seed(per_problem_seed(a.seed, tid))
        # Generation stops once the reply boundary appears: the same stop-string
        # rule as Hugging Face's StopStringCriteria (github.com/huggingface/
        # transformers/blob/main/src/transformers/generation/stopping_criteria.py),
        # exact here because the stopped tokens are a prefix of the unstopped
        # run's (locallm/test_r12_decode.py). Measured 2026-09-25 on r9: a reply
        # that closes stops after ~130 tokens instead of the 1,200 budget.
        text = checkpoint.sample(model, tok, head, a.tokens, temperature=a.temperature,
                                 top_k=a.top_k, use_cache=a.use_cache, stop=reply_stop(head))
        stopped = reply_cut(head, text) is not None
        body = text[len(head):] if text.startswith(head) else text
        # cut at the next head this project writes; see REPLY_BOUNDARY
        body = REPLY_BOUNDARY.split(body, maxsplit=1)[0]
        # A corpus whose documents START with a head teaches the model to start
        # its answer with one. Measured 2026-09-20: trained on the examples
        # corpus, every one of 24 replies opened with `Example:` lines before
        # `t 1`, and all 24 failed to extract. The splitter above cuts at the
        # next document; this removes a head in front of this one. Third time
        # this family has bitten: the answer splitter, then the copy check's
        # stripper, now the extractor's input.
        body = loop_filter.strip_head(body)
        record = {"task_id": tid, "fn": entry["fn"], "model": f"locallm:{a.model}", "digest": f"{params} params",
                  "checkpoint_sha256": checkpoint_sha256,
                  "pool_version": pool_version, "prompt_version": "locallm-head",
                  "options": dict(options),
                  "messages": [{"role": "user", "content": head}],
                  "reply": "```t\n" + body.strip() + "\n```",
                  "done_reason": "stop" if stopped else "length"}
        # written whole or not at all: a worker killed mid-write used to leave a
        # truncated record, which the resume check now refuses by name
        # (os.replace is atomic on POSIX, docs.python.org/3/library/os.html#os.replace)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(record, indent=1), encoding="utf-8")
        os.replace(tmp, path)
        if (i + 1) % 25 == 0:
            print(f"generate: {i + 1} of {len(todo)}", flush=True)
    unanswered = [tid for tid in ids if not (d / "raw" / f"{tid}.json").exists()]
    if unanswered:
        print(f"generate: {len(unanswered)} of {len(ids)} requested ids have no answer: {unanswered[:10]}",
              file=sys.stderr)
        return 1
    print(f"generate: {len(ids)} problems into {d}: {len(todo)} answered now, {len(resumed)} resumed")
    return 0


def build_parser() -> argparse.ArgumentParser:
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
    # No default on purpose: the headline arm was sampled at a silent 0.5 while
    # its neighbours decoded greedily, and nothing said so (blocker A6). Every
    # recipe names its temperature, or it is refused here at parse time.
    p.add_argument("--temperature", type=float, required=True,
                   help="0 decodes greedily; every other value samples. Required, no default.")
    p.add_argument("--top-k", type=int, default=20)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--examples", action="store_true",
                   help="ask with the problem's own assertions in the prompt")
    p.add_argument("--use-cache", action="store_true",
                   help="cached decoding, off by default. locallm/FINDINGS-kv-cache-2026-09-19.md "
                        "verified it produces identical output and its registered speed prediction "
                        "failed on a different benchmark; it has never been measured on this path, "
                        "so register a prediction before quoting a speedup")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    return {"corpus": cmd_corpus, "train": cmd_train, "generate": cmd_generate}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
