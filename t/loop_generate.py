#!/usr/bin/env python3
"""loop_generate.py -- round N (N > 0) of the t error curve: generate with a
peft LoRA adapter trained by loop_train.py, instead of round 0's ollama path
(spec_experiment.py cmd_generate).

Why this file exists: ollama serves GGUF models and cannot serve a peft
adapter, and there is no GGUF converter on this box (loop_train.py --export
says so itself when it cannot find one). So this generates with transformers
directly: 4-bit bitsandbytes base + PeftModel.from_pretrained(adapter), the
same load path loop_train.py trains with, minus the training-only pieces
(prepare_model_for_kbit_training, gradient checkpointing, the trainer).

It writes raw/<task_id>.json records under spec_experiment.outdir(tag) in
EXACTLY the shape spec_experiment.cmd_generate writes (same keys, same
types), so that `spec_experiment.py extract/tests/table` and `run_par.py`
run unchanged over the output -- only the "how the reply was produced" part
differs; everything downstream reads records, not model servers.

    ~/.venv-train/bin/python loop_generate.py --adapter out/loop/adapter-r1 \\
        --tag qwen2.5-coder-1.5b-r1
    ~/.venv-train/bin/python loop_generate.py --adapter none --tag qwen2.5-coder-1.5b-r0ctl
    ~/.venv-train/bin/python loop_generate.py --adapter out/loop/adapter-r1 \\
        --tag qwen2.5-coder-1.5b-r1 --only-heldout out/loop/heldout.json

GPU selection reads nvidia-smi BEFORE importing torch (loop_train.py's own
pattern, reused verbatim: heavy imports deferred into main() so
CUDA_VISIBLE_DEVICES can be set first). The box is shared, so this always
picks the card with the most free VRAM at launch, unless --gpu pins one. If
every requested id already has a raw/<id>.json on disk, this returns before
touching nvidia-smi or importing torch at all -- a no-op run should not
touch the GPU.

Pool and prompt versions (added 2026-09-11): --pool and --prompt take the
same values as spec_experiment.py (v1 default, v2, v3) and are recorded in
each raw record as pool_version and prompt_version, the keys cmd_generate
writes. The first use is the string-library control column: the bare base
on pool v3 with prompt v3, tag qwen2.5-coder-1.5b-r0hf-v3. Downstream
stages must be run with the same --pool.

--adapter none loads the bare base through this same code path (4-bit,
same quant config, same generate() call) -- a round-0-equivalent control
that is not ollama, useful for isolating "transformers vs ollama sampling"
from "adapter vs no adapter" if the two ever disagree.

Sampling mode (added 2026-09-09), for expert iteration: --samples K > 1 asks
for K replies per problem instead of one greedy reply, so a round can keep
several candidate solutions per problem rather than a single point estimate.
The answers that VERIFY with a refuted twin (run_par.py's kernels) and pass
the problem's own tests (spec_experiment.py tests) become the next round's
positives; the ones that fail the tests become its negatives. Each sample k
(0-based) is a full spec-experiment record, written to its own tag directory
spec_experiment.outdir(f"{tag}-s{k}") so the existing extract/tests/table
and run_par.py stages consume it with `--model <tag>-s<k>`, unchanged, once
per k. K samples for one problem come from ONE model.generate call
(num_return_sequences=K, do_sample=True, --temperature/--top-p), seeded
right before the call from a hash of (--seed, task_id) so a re-run
reproduces the same K replies byte for byte. K=1 (the default) is the
original greedy path, untouched: do_sample=False, one record, one tag
directory. --temperature must be > 0 when --samples > 1 (sampling with
temperature 0 is degenerate); it is refused otherwise, before the GPU is
touched.

    ~/.venv-train/bin/python loop_generate.py --adapter out/loop/adapter-r1 \\
        --tag qwen2.5-coder-1.5b-r1 --samples 8 --temperature 0.8

Memory: K sequences of a ~1,600-token prompt plus up to --max-new new
tokens on a 1.5B nf4 base is small, but if K * --max-new is large this
catches torch.cuda.OutOfMemoryError, halves the batch, and retries the K
samples as two or more smaller generate() calls (each with its own chunk
seed derived from (--seed, task_id, chunk) so the fallback path is also
reproducible), printing a line when it happens. Per-sample eval_s and
wall_s are the whole batched call's time divided by K (there is no
per-sample timer inside one generate() call); options records this.

Bounded repair loop (added 2026-09-09), WS-19 move 1: --repair K, default 0
(off), only for the greedy K==1 path (refused together with --samples > 1,
before the GPU is touched). After each reply, check_reply() runs the same
three checks extract and tests would run, in the same order: (1) find the
fenced block and parse it with surface.parse, (2) fuzz_lower.check_wf, (3)
the problem's own test assertions through spec_experiment.run_point, graded
exactly as cmd_tests grades them. On the first failing check, the reply and
one short user turn carrying the exact message (the parser's line and
token text, check_wf's text, or the failing assertion with the expected
and actual values from the interpreter) are appended to the conversation
and the model is asked again, greedy, up to K times. The FINAL reply is
written into the record's "reply" field, in cmd_generate's exact record
shape, so extract/tests/run_par/table run unchanged over it; the retry
trail (attempts made, which check each failed attempt failed at, and the
message shown) is recorded alongside it in a "repair" field. Every path
with --repair 0 (the default) is byte-identical to before this flag
existed.

    ~/.venv-train/bin/python loop_generate.py --adapter none \\
        --tag qwen2.5-coder-1.5b-rep3 --repair 3 \\
        --only-heldout out/loop/split.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import spec_experiment as se   # noqa: E402  (pool, build_prompt, outdir, model_tag)

DEFAULT_BASE = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
MIN_FREE_MIB = 1536   # inference only (no ref model, no optimizer states, no
                       # backward pass); loop_train.py's own 4096 MiB floor is
                       # a training number and does not apply here


# ------------------------------------------------------------- GPU pick --
# Same idea as loop_train.py's free_vram_by_gpu/pick_gpu: read nvidia-smi
# before torch is imported, so CUDA_VISIBLE_DEVICES can still be set.

def free_vram_by_gpu() -> dict[int, int]:
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,memory.free",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=True)
    d = {}
    for line in out.stdout.strip().splitlines():
        idx, free = line.split(",")
        d[int(idx.strip())] = int(free.strip())
    return d


def busy_by_gpu() -> dict[int, int]:
    """How hard each card is already working, 0 to 100."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True)
    except (OSError, subprocess.SubprocessError):
        return {}
    d = {}
    for line in out.stdout.strip().splitlines():
        idx, util = line.split(",")
        d[int(idx.strip())] = int(util.strip())
    return d


def pick_gpu(explicit: int | None) -> tuple[int, dict[int, int]]:
    """The card this run should take.

    Free memory alone is the wrong question on a shared machine: on 2026-09-18 all four cards held another
    user's tensor-parallel job, with free memory within 3 GB of each other and utilisation between 21 and 79
    percent, and a run pinned to the busiest card answered at a third the rate of one on the quietest. So a
    card needs room first -- enough for this model, which is what free memory decides -- and among the cards
    that have room, the quietest wins."""
    free = free_vram_by_gpu()
    if not free:
        raise SystemExit("nvidia-smi reported no GPUs")
    if explicit is not None:
        return explicit, free
    busy = busy_by_gpu()
    if busy:
        roomy = max(free.values())
        # any card within 4 GB of the roomiest counts as having room; among those, take the least busy
        candidates = [i for i, f in free.items() if f >= roomy - 4096]
        best = min(candidates, key=lambda i: (busy.get(i, 0), -free[i]))
        print(f"loop_generate: card {best} ({free[best]} MiB free, {busy.get(best, 0)}% busy); "
              f"others: " + ", ".join(f"{i}:{free[i]}MiB/{busy.get(i, 0)}%"
                                      for i in sorted(free) if i != best), flush=True)
        return best, free
    best = max(free, key=free.get)
    return best, free


# --------------------------------------------------------------- ids --

def parse_ids_text(text: str) -> set[int]:
    """Comma- or newline-separated task ids -> a set of ints. Blank pieces
    (blank lines, trailing commas) are ignored."""
    parts = re.split(r"[,\n]+", text)
    return {int(x) for x in (p.strip() for p in parts) if x}


def select_ids(limit: int, ids_arg: str, only_heldout: str, ids_file: str = "",
               pool_version: str = "v1") -> tuple[dict, list]:
    P = se.pool(pool_version)
    ids = sorted(P)
    if only_heldout:
        held = json.loads(Path(only_heldout).read_text(encoding="utf-8"))
        # out/loop/heldout.json's actual key is "heldout_task_ids"
        # ({"pool_size", "used_task_ids", "heldout_task_ids"} as of 2026-09-09);
        # "heldout" is accepted too in case that shape changes.
        allow = set(held.get("heldout_task_ids") or held.get("heldout") or [])
        ids = [i for i in ids if i in allow]
    # --ids and --ids-file are both "restrict to" filters; given together
    # their union applies (anything named by either survives).
    want: set[int] = set()
    if ids_arg:
        want |= parse_ids_text(ids_arg)
    if ids_file:
        want |= parse_ids_text(Path(ids_file).read_text(encoding="utf-8"))
    if want:
        ids = [i for i in ids if i in want]
    if limit:
        ids = ids[:limit]
    return P, ids


# ------------------------------------------------------------- digest --

def adapter_digest(adapter_dir: Path) -> str:
    """adapter's config hash, or the sha256 of its adapter_model.safetensors
    if present (the actual trained weights, so it changes if a retrain wrote
    a different adapter to the same path)."""
    weights = adapter_dir / "adapter_model.safetensors"
    cfg = adapter_dir / "adapter_config.json"
    if weights.exists():
        h = hashlib.sha256()
        with weights.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return f"weights-sha256:{h.hexdigest()[:16]}"
    if cfg.exists():
        return f"config-sha256:{hashlib.sha256(cfg.read_bytes()).hexdigest()[:16]}"
    return "unknown"


# ----------------------------------------------------------- sample seed --

def derive_seed(seed: int, task_id: int, chunk: int | None = None) -> int:
    """Deterministic torch.manual_seed input from (seed, task_id[, chunk]),
    so a re-run with the same --seed reproduces the same K samples. `chunk`
    is only set on the OOM-fallback path (distinct sub-calls need distinct
    seeds); the normal one-call path omits it so its seed does not depend on
    whether the fallback ever triggers elsewhere."""
    key = f"{seed}:{task_id}" if chunk is None else f"{seed}:{task_id}:{chunk}"
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(h[:16], 16) % (2 ** 31 - 1)


def generate_samples(torch_mod, model, tokenizer, input_ids, attention_mask, eos_id,
                     args, tid: int, K: int, make_procs=None):
    """K sampled replies for one problem, as ONE num_return_sequences=K
    model.generate call whenever it fits. Returns (new_token_slices, elapsed_s,
    oom_hit) where new_token_slices is a list of K 1-D tensors (prompt
    stripped, still possibly right-padded -- callers trim to eos) and
    elapsed_s covers the whole call chain (all sub-calls if it fell back).

    torch is passed in rather than imported at module level: it is loaded
    lazily inside main(), after the GPU is picked, so a no-op run never
    touches CUDA.

    On torch.cuda.OutOfMemoryError from the single K-wide call, halves the
    batch and regenerates as two or more smaller calls, each seeded from
    (--seed, task_id, chunk) so the fallback path is itself reproducible on
    a re-run. If even batch size 1 OOMs, the error propagates (nothing left
    to shrink)."""
    prompt_len = input_ids.shape[-1]
    t0 = time.monotonic()
    try:
        torch_mod.manual_seed(derive_seed(args.seed, tid))
        with torch_mod.no_grad():
            out = model.generate(
                input_ids, attention_mask=attention_mask, max_new_tokens=args.max_new,
                do_sample=True, temperature=args.temperature, top_p=args.top_p,
                num_return_sequences=K, pad_token_id=tokenizer.pad_token_id,
                eos_token_id=eos_id,
                **({"logits_processor": make_procs()} if make_procs else {}))
        return [out[i][prompt_len:] for i in range(K)], time.monotonic() - t0, False
    except torch_mod.cuda.OutOfMemoryError:
        print(f"loop_generate: task {tid}: CUDA OOM generating all {K} samples in one "
              f"call; falling back to smaller batches", flush=True)
        torch_mod.cuda.empty_cache()

    slices = []
    chunk = 0
    remaining = K
    batch = max(1, K // 2)
    while remaining > 0:
        this = min(batch, remaining)
        while True:
            try:
                torch_mod.manual_seed(derive_seed(args.seed, tid, chunk))
                with torch_mod.no_grad():
                    out = model.generate(
                        input_ids, attention_mask=attention_mask, max_new_tokens=args.max_new,
                        do_sample=True, temperature=args.temperature, top_p=args.top_p,
                        num_return_sequences=this, pad_token_id=tokenizer.pad_token_id,
                        eos_token_id=eos_id,
                        **({"logits_processor": make_procs()} if make_procs else {}))
                break
            except torch_mod.cuda.OutOfMemoryError:
                torch_mod.cuda.empty_cache()
                if this == 1:
                    raise
                this = max(1, this // 2)
                batch = this   # keep later chunks at the size that worked
                print(f"loop_generate: task {tid}: still OOM, shrinking chunk to {this}",
                      flush=True)
        slices.extend(out[i][prompt_len:] for i in range(this))
        remaining -= this
        chunk += 1
    return slices, time.monotonic() - t0, True


# --------------------------------------------------------------- misc --

def print_followups(tag: str) -> None:
    tag_dir = se.model_tag(tag)
    print()
    print("follow-up commands:")
    print(f"  python3 spec_experiment.py extract --model {tag}")
    print(f"  python3 spec_experiment.py tests    --model {tag}")
    print(f"  python3 run_par.py --tasks out/spec-experiment/{tag_dir}/tasks "
          f"--out out/spec-experiment/{tag_dir}/kernels "
          f"--table out/spec-experiment/{tag_dir}/kernels.md")
    print(f"  python3 spec_experiment.py table    --model {tag} "
          f"--out SPEC-EXPERIMENT-{tag_dir}.md")


def print_sample_followups(tag: str, K: int) -> None:
    tags = [f"{tag}-s{k}" for k in range(K)]
    print()
    print(f"sample tag directories ({K}): " + ", ".join(tags))
    print(f"follow-up commands for one sample (repeat for each of the {K} tags above, "
          f"substituting --model):")
    print_followups(tags[0])


# ----------------------------------------------------------------- repair --
# WS-19 move 1: the same three checks cmd_extract/cmd_tests run, so a
# repair turn can hand the model the parser's own message instead of a
# generic "try again". se.find_block/se.surface/se.fuzz_lower/se.run_point
# are spec_experiment's own functions/modules (imported there, not here) --
# using them keeps this the SAME check extract and tests will run later,
# not a reimplementation that could drift from it.

REPAIR_ASK = ("Reply with the corrected t task as a single ```t fenced "
              "block and nothing else.")


def check_reply(reply: str, entry: dict) -> tuple[bool, str, str]:
    """(ok, stage, message). stage is "" on ok; else "parse", "wf", or
    "tests", the first of the three checks that failed. message is the
    parser's line and token text, check_wf's text (errors joined with
    "; ", the same join cmd_extract uses), or the failing assertion's
    source text with the expected and actual values from the interpreter
    (interp.run_point's own "got"/"expected", the same values cmd_tests
    would report)."""
    block = se.find_block(reply)
    if block is None:
        return (False, "parse",
                "no ```t fenced block (or a line starting 't 0' / 't 1') found in the reply")
    try:
        task = se.surface.parse(block)
    except se.surface.SurfaceError as e:
        return False, "parse", str(e)
    except Exception as e:                                     # noqa: BLE001
        return False, "parse", f"{type(e).__name__}: {e}"

    try:
        errs = se.fuzz_lower.check_wf(task)
    except Exception as e:                                     # noqa: BLE001
        return False, "wf", f"check_wf raised {type(e).__name__}: {e}"
    if errs:
        return False, "wf", "; ".join(errs)

    points = entry["points"]
    tests_src = entry["rec"]["test_list"]
    results = [se.run_point(task, p) for p in points]
    verdicts = [r["verdict"] for r in results]
    if all(v == "pass" for v in verdicts):
        return True, "", ""
    # same priority cmd_tests uses to pick one "overall" verdict for the
    # problem: signature mismatch, then a failing value, then an excluded
    # requires, else undefined (budget included, cmd_tests does not single
    # it out either).
    if any(v in ("arity", "type") for v in verdicts):
        overall = "signature"
    elif any(v == "fail" for v in verdicts):
        overall = "fail"
    elif any(v == "requires-excluded" for v in verdicts):
        overall = "requires-excluded"
    else:
        overall = "undefined"
    if overall == "signature":
        idx = next(i for i, v in enumerate(verdicts) if v in ("arity", "type"))
    elif overall == "fail":
        idx = next(i for i, v in enumerate(verdicts) if v == "fail")
    elif overall == "requires-excluded":
        idx = next(i for i, v in enumerate(verdicts) if v == "requires-excluded")
    else:
        idx = next(i for i, v in enumerate(verdicts) if v != "pass")
    src = tests_src[idx].strip() if idx < len(tests_src) else f"test point {idx}"
    r = results[idx]
    if overall == "fail":
        msg = f"assertion `{src}` failed: expected {r['expected']!r}, got {r['got']!r}"
    elif overall == "undefined":
        msg = f"assertion `{src}` hit undefined behavior in the interpreter: {r.get('why', '')}"
    elif overall == "requires-excluded":
        msg = f"assertion `{src}` is excluded by the task's own requires clause"
    else:
        msg = f"assertion `{src}` does not match the task's signature: {r.get('why', '')}"
    return False, "tests", msg


# ------------------------------------------------------------------ main --

def grammar_processors(tokenizer, grammar_path: str, torch_mod, vocab_size: int | None = None):
    """A logits processor that lets only tokens t's grammar can still accept (WS-21, 2026-09-18).

    The measurement that asks for this: the round 5 student parsed 32 percent of the time, exactly where the
    untrained 1.5B already sat, and training moved it not at all; the constrained arm on the lab workstation
    took a 30B from 32 percent parsing to 63. Constraining the student at inference is the same move for the
    model this project is actually trying to make good.

    xgrammar compiles the grammar once against this tokenizer's vocabulary, then masks per step. Returns None
    if anything about that fails, so a run without xgrammar is a run without the constraint rather than no run
    at all -- and says so, because a silent fallback here would be a measurement quietly changed."""
    try:
        import xgrammar as xgr
        from xgrammar.contrib.hf import LogitsProcessor
    except ImportError as e:
        print(f"loop_generate: no xgrammar ({e}); generating unconstrained", flush=True)
        return None
    try:
        text = "\n".join(line for line in Path(grammar_path).read_text(encoding="utf-8").splitlines()
                         if not line.lstrip().startswith("#"))
        # The mask has to be as wide as the logits, not as wide as the tokenizer. Phi-4-mini's tokenizer holds
        # 200,032 tokens and its logits 200,064, and xgrammar leaves anything past the mask UNMASKED -- so 32
        # tokens could still be sampled and the reply would not be what the grammar promised. Measured
        # 2026-09-18 from xgrammar's own warning; the model's own vocab_size is the right width.
        info = xgr.TokenizerInfo.from_huggingface(tokenizer, vocab_size=vocab_size or len(tokenizer))
        compiled = xgr.GrammarCompiler(info).compile_grammar(xgr.Grammar.from_ebnf(text))
        print(f"loop_generate: decoding against {grammar_path}", flush=True)
        return lambda: [LogitsProcessor(compiled)]
    except Exception as e:                                      # noqa: BLE001
        print(f"loop_generate: could not compile {grammar_path}: {e}; generating unconstrained", flush=True)
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--adapter", required=True,
                    help="peft adapter dir (out/loop/adapter-r1), or 'none' for the bare base")
    ap.add_argument("--tag", required=True,
                    help="model tag; records land under out/spec-experiment/<model_tag(tag)>")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v1",
                    help="problem pool version, as spec_experiment.py --pool (added 2026-09-11)")
    ap.add_argument("--prompt", choices=se.PROMPT_VERSIONS, default="v1",
                    help="prompt version, as spec_experiment.py generate --prompt (added 2026-09-11)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="", help="comma-separated task ids, e.g. 100,101")
    ap.add_argument("--ids-file", default="",
                    help="path to a file of comma- or newline-separated task ids; "
                         "unions with --ids if both are given")
    ap.add_argument("--gpu", type=int, default=None, help="pin a GPU index; default: most free VRAM")
    ap.add_argument("--max-new", type=int, default=1024)
    ap.add_argument("--grammar", default="",
                    help="decode against this grammar (t/t.gbnf), so the reply cannot be something the parser "
                         "would refuse; needs xgrammar (WS-21)")
    ap.add_argument("--only-heldout", default="", help="path to a heldout.json; restricts to its held-out ids")
    ap.add_argument("--samples", type=int, default=1,
                    help="K replies per problem (default 1: today's single greedy reply). "
                         "K > 1 samples K replies in one model.generate call per problem "
                         "and writes each to its own <tag>-s<k> tag directory")
    ap.add_argument("--temperature", type=float, default=0.0,
                    help="sampling temperature; must be > 0 when --samples > 1 "
                         "(ignored, generation stays greedy, when --samples is 1)")
    ap.add_argument("--top-p", type=float, default=0.95, help="nucleus sampling p, used only when --samples > 1")
    ap.add_argument("--seed", type=int, default=1,
                    help="--samples 1: recorded in the digest/options only, generation is greedy. "
                         "--samples > 1: seeds torch.manual_seed, derived per (seed, task_id), "
                         "right before each problem's generate call, so a re-run reproduces the "
                         "same K samples")
    ap.add_argument("--min-free-mib", type=int, default=MIN_FREE_MIB)
    ap.add_argument("--repair", type=int, default=0,
                    help="bounded repair loop, K retries per problem (default 0: off, "
                         "every existing path byte-identical). Only for the greedy "
                         "--samples 1 path: after each reply, run the parse/check_wf/tests "
                         "checks extract and tests would run and, on the first failure, "
                         "send the reply back with the exact message and ask for a "
                         "corrected block, up to K times. The final reply is recorded in "
                         "the normal record shape; the retry trail is recorded beside it "
                         "in a 'repair' field. Refused together with --samples > 1.")
    args = ap.parse_args()

    K = args.samples
    if K < 1:
        print(f"loop_generate: --samples must be >= 1, got {K}")
        return 2
    if K > 1 and args.temperature <= 0:
        print(f"loop_generate: --samples {K} > 1 requires --temperature > 0 "
              f"(got {args.temperature}); sampling at temperature 0 is degenerate. Refusing "
              f"before touching the GPU.")
        return 2
    if args.repair < 0:
        print(f"loop_generate: --repair must be >= 0, got {args.repair}")
        return 2
    if args.repair > 0 and K > 1:
        print(f"loop_generate: --repair {args.repair} is not supported together with "
              f"--samples {K} > 1; the repair loop is a single-reply, multi-turn "
              f"conversation, not part of the sampling path. Refusing before touching "
              f"the GPU.")
        return 2

    if K == 1:
        tag_dirs = [se.outdir(args.tag)]
    else:
        tag_dirs = [se.outdir(f"{args.tag}-s{k}") for k in range(K)]

    P, ids = select_ids(args.limit, args.ids, args.only_heldout, args.ids_file, args.pool)
    if K == 1:
        todo = [tid for tid in ids if not (tag_dirs[0] / "raw" / f"{tid}.json").exists()]
    else:
        todo = [tid for tid in ids
                if not all((dk / "raw" / f"{tid}.json").exists() for dk in tag_dirs)]
    already = len(ids) - len(todo)
    if K == 1:
        print(f"loop_generate: {len(ids)} problems selected, {already} already on disk, "
              f"{len(todo)} to generate")
    else:
        print(f"loop_generate: {len(ids)} problems selected, {already} already have all "
              f"{K} samples on disk, {len(todo)} to generate (a partial set on disk still "
              f"counts as to-generate: the whole K-set for a problem is regenerated together)")
    if not todo:
        print("loop_generate: nothing to do (no selected id needs a raw record); "
              "not touching the GPU")
        if K == 1:
            print_followups(args.tag)
        else:
            print_sample_followups(args.tag, K)
        return 0

    # --------------------------------------------------- GPU, before torch
    gpu, free = pick_gpu(args.gpu)
    print("free VRAM by GPU (MiB): " + ", ".join(f"{i}={m}" for i, m in sorted(free.items())))
    if free.get(gpu, 0) < args.min_free_mib and args.gpu is None:
        print(f"refusing to run: best card is GPU {gpu} with {free[gpu]} MiB free, "
              f"below --min-free-mib={args.min_free_mib}. Not importing torch, not "
              f"touching any GPU.")
        return 3
    print(f"selected GPU {gpu} ({free.get(gpu, '?')} MiB free)")
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    # ------------------------------------------------------- heavy imports
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    torch.cuda.init()   # lazy CUDA init; without this, reset_peak_memory_stats(dev)
                        # below raises "Invalid device argument" on a torch.device
                        # object (loop_train.py dodges this only because its peft/trl
                        # imports happen to touch CUDA first -- this script does not
                        # import peft until after this point, so it needs the init
                        # explicitly)
    dev = torch.device("cuda:0")   # index 0 WITHIN CUDA_VISIBLE_DEVICES
    torch.cuda.reset_peak_memory_stats(dev)

    print(f"loading tokenizer + base model: {args.base}")
    tokenizer = AutoTokenizer.from_pretrained(args.base)
    # A tokenizer that cannot return what it was given will not return what the model said either.
    # DeepSeek-Prover-V2-7B loads as LlamaTokenizer under transformers 5.17 and drops every space on the way
    # back -- 122 answers came out as "t1tasksmall_nnum(s:seq,n:int)" before this check existed (2026-09-18).
    # The model's own tokenizer.json is fine; it is the class detection that is wrong, so try that file.
    probe = "t 1 task f(x: int) returns (r: int)"
    if tokenizer.decode(tokenizer(probe)["input_ids"], skip_special_tokens=True) != probe:
        print(f"loop_generate: {type(tokenizer).__name__} does not round-trip this notation; "
              f"trying the model's own tokenizer.json", flush=True)
        try:
            from transformers import PreTrainedTokenizerFast
            from huggingface_hub import hf_hub_download
            alt = PreTrainedTokenizerFast(tokenizer_file=hf_hub_download(args.base, "tokenizer.json"))
            if alt.decode(alt(probe)["input_ids"], skip_special_tokens=True) == probe:
                for attr in ("eos_token", "pad_token", "bos_token"):
                    if getattr(alt, attr, None) is None and getattr(tokenizer, attr, None) is not None:
                        setattr(alt, attr, getattr(tokenizer, attr))
                alt.chat_template = alt.chat_template or tokenizer.chat_template
                tokenizer = alt
                print("loop_generate: using the model's tokenizer.json directly", flush=True)
            else:
                print("loop_generate: that does not round-trip either; answers from this model are suspect",
                      flush=True)
        except Exception as e:                                  # noqa: BLE001
            print(f"loop_generate: no usable tokenizer.json ({e}); answers from this model are suspect",
                  flush=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.base, quantization_config=bnb, device_map={"": 0},
        torch_dtype=torch.bfloat16)

    adapter_note = "none"
    adapter_hash = "n/a"
    if args.adapter and args.adapter != "none":
        from peft import PeftModel
        adapter_dir = Path(args.adapter)
        print(f"applying adapter: {adapter_dir}")
        model = PeftModel.from_pretrained(model, str(adapter_dir))
        adapter_note = str(adapter_dir)
        adapter_hash = adapter_digest(adapter_dir)
    model.eval()
    model.config.use_cache = True
    make_procs = (grammar_processors(tokenizer, args.grammar, torch,
                                     vocab_size=getattr(model.config, "vocab_size", None))
                  if args.grammar else None)

    digest = (f"base={args.base} adapter={adapter_note} "
              f"adapter_digest={adapter_hash} torch={torch.__version__} "
              f"transformers={transformers.__version__}")

    eos_id = tokenizer.eos_token_id
    if eos_id is None:
        eos_set: set[int] = set()
    elif isinstance(eos_id, int):
        eos_set = {eos_id}
    else:
        eos_set = set(eos_id)

    def trim_to_eos(new_tok) -> tuple["torch.Tensor", bool]:  # noqa: F821 (torch imported in main)
        """new_tok is a 1-D new-token tensor, possibly right-padded (batched
        sampling pads shorter sequences to the batch's longest). Trim at the
        first eos token so reply/reply_tokens describe what the model
        actually said, not the padding."""
        ids_list = new_tok.tolist()
        for i, t in enumerate(ids_list):
            if t in eos_set:
                return new_tok[:i + 1], True
        return new_tok, False

    oom_hit_any = False
    t_start = time.monotonic()
    asked = 0
    for tid in todo:
        entry = P[tid]
        messages = se.build_prompt(entry, args.prompt)
        t_task0 = time.monotonic()
        # transformers 5.5.0 defaults apply_chat_template(return_tensors="pt") to
        # return_dict=True, i.e. a BatchEncoding, not a bare input_ids tensor --
        # pull input_ids/attention_mask out of it explicitly.
        enc = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt", return_dict=True)
        input_ids = enc["input_ids"].to(dev)
        attention_mask = enc.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(dev)
        prompt_tokens = int(input_ids.shape[-1])

        if K == 1 and args.repair <= 0:
            t_gen0 = time.monotonic()
            with torch.no_grad():
                out = model.generate(
                    input_ids, attention_mask=attention_mask, max_new_tokens=args.max_new,
                    do_sample=False, pad_token_id=tokenizer.pad_token_id, eos_token_id=eos_id,
                    # this is the path every held-out run takes (one sample, no repair), and it was the one
                    # path --grammar did not reach on 2026-09-18: the constrained student came back with 158
                    # parse failures against the unconstrained 159, which is what an unapplied constraint
                    # looks like
                    **({"logits_processor": make_procs()} if make_procs else {}))
            eval_s = time.monotonic() - t_gen0

            new_tokens = out[0][input_ids.shape[-1]:]
            reply = tokenizer.decode(new_tokens, skip_special_tokens=True)
            reply_tokens = int(new_tokens.shape[-1])
            hit_eos = reply_tokens > 0 and int(new_tokens[-1].item()) in eos_set
            done_reason = "stop" if hit_eos else "length"
            wall = time.monotonic() - t_task0

            options = {"temperature": 0, "seed": args.seed, "max_new_tokens": args.max_new,
                       "note": "greedy transformers generate"}
            record = {"task_id": tid, "fn": entry["fn"], "model": args.tag, "digest": digest,
                      "pool_version": args.pool, "prompt_version": args.prompt,
                      "options": options, "messages": messages, "reply": reply,
                      "prompt_tokens": prompt_tokens, "reply_tokens": reply_tokens,
                      "eval_s": round(eval_s, 3), "wall_s": round(wall, 3),
                      "done_reason": done_reason}
            (tag_dirs[0] / "raw" / f"{tid}.json").write_text(
                json.dumps(record, indent=1), encoding="utf-8")
        elif K == 1:
            # --repair loop: same greedy decoding as above, but after each
            # reply, check_reply() runs the same checks extract/tests would
            # and, on the first failure, one more greedy turn is asked for
            # with the exact message appended to the conversation. Up to
            # args.repair extra turns (attempt 0 is the original reply,
            # attempts 1..args.repair are retries).
            local_messages = list(messages)
            cur_input_ids, cur_attention_mask, cur_prompt_tokens = (
                input_ids, attention_mask, prompt_tokens)
            trail: list[dict] = []
            eval_s_total = 0.0
            reply, reply_tokens, done_reason, ok = "", 0, "length", False
            attempt = 0
            for attempt in range(args.repair + 1):
                if attempt > 0:
                    enc_a = tokenizer.apply_chat_template(
                        local_messages, add_generation_prompt=True,
                        return_tensors="pt", return_dict=True)
                    cur_input_ids = enc_a["input_ids"].to(dev)
                    cur_attention_mask = enc_a.get("attention_mask")
                    if cur_attention_mask is not None:
                        cur_attention_mask = cur_attention_mask.to(dev)
                    cur_prompt_tokens = int(cur_input_ids.shape[-1])
                t_gen0 = time.monotonic()
                with torch.no_grad():
                    out_a = model.generate(
                        cur_input_ids, attention_mask=cur_attention_mask,
                        max_new_tokens=args.max_new, do_sample=False,
                        pad_token_id=tokenizer.pad_token_id, eos_token_id=eos_id,
                        **({"logits_processor": make_procs()} if make_procs else {}))
                eval_s_total += time.monotonic() - t_gen0
                new_tokens_a = out_a[0][cur_input_ids.shape[-1]:]
                reply = tokenizer.decode(new_tokens_a, skip_special_tokens=True)
                reply_tokens = int(new_tokens_a.shape[-1])
                hit_eos_a = reply_tokens > 0 and int(new_tokens_a[-1].item()) in eos_set
                done_reason = "stop" if hit_eos_a else "length"

                ok, stage, msg = check_reply(reply, entry)
                if ok:
                    break
                trail.append({"attempt": attempt, "stage": stage, "message": msg})
                if attempt == args.repair:
                    break
                local_messages.append({"role": "assistant", "content": reply})
                local_messages.append({"role": "user", "content": msg + "\n\n" + REPAIR_ASK})

            wall = time.monotonic() - t_task0
            options = {"temperature": 0, "seed": args.seed, "max_new_tokens": args.max_new,
                       "note": "greedy transformers generate"}
            record = {"task_id": tid, "fn": entry["fn"], "model": args.tag, "digest": digest,
                      "pool_version": args.pool, "prompt_version": args.prompt,
                      "options": options, "messages": local_messages, "reply": reply,
                      "prompt_tokens": cur_prompt_tokens, "reply_tokens": reply_tokens,
                      "eval_s": round(eval_s_total, 3), "wall_s": round(wall, 3),
                      "done_reason": done_reason,
                      "repair": {"k": args.repair, "attempts": attempt, "rescued": ok,
                                 "trail": trail}}
            (tag_dirs[0] / "raw" / f"{tid}.json").write_text(
                json.dumps(record, indent=1), encoding="utf-8")
        else:
            new_slices, elapsed, oom_hit = generate_samples(
                torch, model, tokenizer, input_ids, attention_mask, eos_id, args, tid, K, make_procs)
            oom_hit_any = oom_hit_any or oom_hit
            per_sample_t = elapsed / K
            note = ("sampled transformers generate (do_sample=True); eval_s and wall_s "
                    "are the whole num_return_sequences batch call's time divided evenly "
                    "across the K samples, not a per-sample timer")
            if oom_hit:
                note += "; CUDA OOM fallback triggered: batch was split into smaller generate() calls"
            for k, new_tok in enumerate(new_slices):
                trimmed, hit_eos = trim_to_eos(new_tok)
                reply = tokenizer.decode(trimmed, skip_special_tokens=True)
                reply_tokens = int(trimmed.shape[-1])
                done_reason = "stop" if hit_eos else "length"
                options = {"temperature": args.temperature, "top_p": args.top_p,
                           "seed": args.seed, "sample_index": k, "num_samples": K,
                           "max_new_tokens": args.max_new, "note": note}
                record = {"task_id": tid, "fn": entry["fn"], "model": f"{args.tag}-s{k}",
                          "digest": digest, "pool_version": args.pool,
                          "prompt_version": args.prompt,
                          "options": options, "messages": messages,
                          "reply": reply, "prompt_tokens": prompt_tokens,
                          "reply_tokens": reply_tokens, "eval_s": round(per_sample_t, 3),
                          "wall_s": round(per_sample_t, 3), "done_reason": done_reason}
                (tag_dirs[k] / "raw" / f"{tid}.json").write_text(
                    json.dumps(record, indent=1), encoding="utf-8")

        asked += 1
        if asked % 10 == 0 or asked == 1:
            el = time.monotonic() - t_start
            print(f"generate: {already + asked}/{len(ids)} ({asked} asked this run, "
                  f"{el:.0f} s, {el / asked:.1f} s each)", flush=True)

    wall_total = time.monotonic() - t_start
    peak = torch.cuda.max_memory_allocated(dev) / 1e9
    print(f"generate: {already + asked} of {len(ids)} problems have a reply on disk")
    print(f"peak VRAM: {peak:.2f} GB")
    print(f"wall time: {wall_total:.1f} s ({wall_total / max(asked, 1):.1f} s/problem)")
    print(f"GPU used: {gpu}")
    if K == 1:
        print_followups(args.tag)
    else:
        print(f"CUDA OOM fallback triggered: {'yes' if oom_hit_any else 'no'}")
        print_sample_followups(args.tag, K)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
