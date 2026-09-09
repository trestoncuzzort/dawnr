#!/usr/bin/env python3
"""bedrock_generate.py -- WS-19 move 2: Claude on Amazon Bedrock as the
loop's sampler, so a round's positives come from a frontier model instead
of the 1.5B adapter (round 2 had 82; this measures whether Bedrock lifts
that into the hundreds).

Same idea as loop_generate.py, a different inference path: instead of a
peft adapter through transformers, this calls a Claude model through the
Bedrock Runtime `converse` API (boto3), using spec_experiment's own
build_prompt (same messages, same grammar, same few-shots) so the pool,
the prompt and the grading are identical across every sampler this loop
has tried (ollama, transformers+adapter, now Bedrock). It writes
raw/<task_id>.json records under spec_experiment.outdir(tag) in the SAME
shape spec_experiment.cmd_generate writes (same keys, same types) --
extract, tests, run_par and table run unchanged over the output.
--samples K writes K sample-tag directories <tag>-s<k>, exactly
loop_generate's convention, so loop_dataset.py --from-samples reads them
the same way.

Prompt version v1 only is meaningful here (12.7's rule: no round is
compared under the v2 prompt until the control is re-measured under it);
--prompt defaults to v1 and nothing in WS-19 move 2 asks for v2.

Bedrock's `converse` API has no seed parameter. Samples (--samples > 1,
--temperature > 0) are therefore NOT reproducible run to run; every
record's "options" says so explicitly. The greedy control path
(--samples 1 --temperature 0) is close to deterministic on Anthropic's
serving stack but is not guaranteed bit-identical either -- there is no
seed to pin it, unlike ollama's `seed` option spec_experiment.chat uses.

Concurrency: at most 4 requests in flight (--concurrency, hard-capped at
4 regardless of what is asked). Throttling and transient server errors
(ThrottlingException, ServiceUnavailableException, ModelTimeoutException,
InternalServerException, ModelNotReadyException, and botocore connection/
read timeouts) retry with exponential backoff (1, 2, 4, 8, 16 s, +/-20%
jitter, 6 attempts). Everything else -- ValidationException,
AccessDeniedException, ResourceNotFoundException, and any other 4xx --
is NOT retried: backing off against "you are not authorized to invoke
this model" wastes time and teaches nothing. The first such error aborts
the whole run (a shared stop flag, checked before every new request) and
prints the exact error and the fix (the Bedrock console's Model access
page, or `aws bedrock get-use-case-for-model-access` /
`create-foundation-model-agreement`).

Cost: every call's usage.inputTokens/outputTokens is logged, a running
dollar estimate is printed as it goes (--price-in-per-mtok 3.0,
--price-out-per-mtok 15.0 by default, Bedrock on-demand Sonnet 4.5 list
price), and a --spend-cap-usd (default 40.0) stops the run -- refusing to
submit further requests, not merely warning -- once the running estimate
would pass it. The estimate is a lower bound: it is computed only from
calls that actually returned usage, so a run that aborts mid-flight may
have a few in-flight requests whose tokens are not yet counted.

    ~/.venv-aws/bin/python bedrock_generate.py --tag claude-sonnet-4.5-bedrock \\
        --only-heldout out/loop/split.json --limit 3

    ~/.venv-aws/bin/python bedrock_generate.py --tag claude-sonnet-4.5-bedrock \\
        --only-heldout out/loop/split.json

    ~/.venv-aws/bin/python bedrock_generate.py --tag claude-sonnet-4.5-bedrock-samp \\
        --ids-file /path/to/train-ids.txt --samples 8 --temperature 0.8
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import random
import re
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import spec_experiment as se   # noqa: E402  (pool, build_prompt, outdir, model_tag, PROMPT_VERSIONS)

DEFAULT_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_REGION = "us-east-1"
PRICE_IN_PER_MTOK = 3.0     # dollars/million input tokens, Bedrock on-demand Sonnet 4.5
PRICE_OUT_PER_MTOK = 15.0   # dollars/million output tokens, Bedrock on-demand Sonnet 4.5
HARD_MAX_CONCURRENCY = 4    # never exceeded, whatever --concurrency asks for

RETRYABLE_CODES = ("ThrottlingException", "ServiceUnavailableException",
                    "ModelTimeoutException", "InternalServerException",
                    "ModelNotReadyException")


# ----------------------------------------------------------------- ids --

def parse_ids_text(text: str) -> set[int]:
    """Comma- or newline-separated task ids -> a set of ints. Blank pieces
    (blank lines, trailing commas) are ignored. Same rule as
    loop_generate.parse_ids_text, kept independent on purpose (this file
    owns no import of loop_generate -- another agent owns that file)."""
    parts = re.split(r"[,\n]+", text)
    return {int(x) for x in (p.strip() for p in parts) if x}


def select_ids(limit: int, ids_file: str, only_heldout: str) -> tuple[dict, list]:
    P = se.pool()
    ids = sorted(P)
    if only_heldout:
        held = json.loads(Path(only_heldout).read_text(encoding="utf-8"))
        # split.json's keys are {"eval_ids", "train_ids", "heldout_task_ids",
        # "used_task_ids", ...}; heldout.json's are {"heldout_task_ids", ...}.
        # Accept both, same fallback loop_generate.select_ids uses.
        allow = set(held.get("heldout_task_ids") or held.get("heldout") or [])
        ids = [i for i in ids if i in allow]
    if ids_file:
        want = parse_ids_text(Path(ids_file).read_text(encoding="utf-8"))
        ids = [i for i in ids if i in want]
    if limit:
        ids = ids[:limit]
    return P, ids


# ------------------------------------------------------------- Bedrock --

class NonRetryable(Exception):
    """A Bedrock error that must not be retried (bad request, not
    authorized, not found, ...). Raising this aborts the whole run."""


class TokenTotals:
    """Thread-safe running token/dollar counter, shared across the
    concurrency pool so the spend cap is checked against the true total,
    not a per-thread partial one."""

    def __init__(self, price_in: float, price_out: float, cap: float):
        self.lock = threading.Lock()
        self.in_tokens = 0
        self.out_tokens = 0
        self.calls = 0
        self.price_in = price_in
        self.price_out = price_out
        self.cap = cap

    def add(self, in_tok: int, out_tok: int) -> None:
        with self.lock:
            self.in_tokens += in_tok or 0
            self.out_tokens += out_tok or 0
            self.calls += 1

    def dollars(self) -> float:
        with self.lock:
            return (self.in_tokens / 1e6) * self.price_in + (self.out_tokens / 1e6) * self.price_out

    def over_cap(self) -> bool:
        return self.dollars() >= self.cap

    def snapshot(self) -> tuple[int, int, int, float]:
        with self.lock:
            d = (self.in_tokens / 1e6) * self.price_in + (self.out_tokens / 1e6) * self.price_out
            return self.in_tokens, self.out_tokens, self.calls, d


def to_bedrock_messages(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    """spec_experiment.build_prompt's shape ([{"role": "system"/"user",
    "content": <str>}, ...], ollama's /api/chat shape) -> Bedrock
    converse's shape: a separate `system` list of text blocks, and a
    `messages` list whose every entry's content is itself a list of
    blocks ({"text": ...})."""
    system: list[dict] = []
    conv: list[dict] = []
    for m in messages:
        if m["role"] == "system":
            system.append({"text": m["content"]})
        else:
            conv.append({"role": m["role"], "content": [{"text": m["content"]}]})
    return system, conv


def converse_once(client, model_id: str, system: list[dict], conv: list[dict],
                   max_tokens: int, temperature: float):
    kwargs = {"modelId": model_id, "messages": conv,
              "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature}}
    if system:
        kwargs["system"] = system
    return client.converse(**kwargs)


def call_with_backoff(client, model_id: str, system: list[dict], conv: list[dict],
                       max_tokens: int, temperature: float, max_attempts: int = 6):
    import botocore.exceptions
    delay = 1.0
    for attempt in range(1, max_attempts + 1):
        try:
            return converse_once(client, model_id, system, conv, max_tokens, temperature)
        except botocore.exceptions.ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            msg = e.response.get("Error", {}).get("Message", "")
            if code not in RETRYABLE_CODES:
                raise NonRetryable(f"{code}: {msg}") from e
            if attempt == max_attempts:
                raise NonRetryable(f"{code}: {msg} (exhausted {max_attempts} attempts)") from e
            sleep_s = delay * (1 + random.uniform(-0.2, 0.2))
            print(f"  throttled ({code}), retry {attempt}/{max_attempts} in {sleep_s:.1f}s",
                  file=sys.stderr, flush=True)
            time.sleep(sleep_s)
            delay *= 2
        except (botocore.exceptions.EndpointConnectionError,
                botocore.exceptions.ReadTimeoutError,
                botocore.exceptions.ConnectTimeoutError) as e:
            if attempt == max_attempts:
                raise NonRetryable(f"connection error, exhausted {max_attempts} attempts: {e}") from e
            sleep_s = delay * (1 + random.uniform(-0.2, 0.2))
            print(f"  connection error, retry {attempt}/{max_attempts} in {sleep_s:.1f}s",
                  file=sys.stderr, flush=True)
            time.sleep(sleep_s)
            delay *= 2
    raise NonRetryable("unreachable: retry loop exited without returning or raising")


# ----------------------------------------------------------------- one --

def one_call(client, args, digest: str, tid: int, entry: dict, k: int) -> tuple[dict, int, int]:
    messages = se.build_prompt(entry, args.prompt)
    system, conv = to_bedrock_messages(messages)
    t0 = time.monotonic()
    resp = call_with_backoff(client, args.model, system, conv, args.max_tokens, args.temperature)
    wall = time.monotonic() - t0
    out_msg = resp.get("output", {}).get("message", {})
    reply = "".join(b.get("text", "") for b in out_msg.get("content", []) if "text" in b)
    usage = resp.get("usage", {})
    in_tok = usage.get("inputTokens", 0) or 0
    out_tok = usage.get("outputTokens", 0) or 0
    stop_reason = resp.get("stopReason")
    options = {"temperature": args.temperature, "seed": args.seed, "max_tokens": args.max_tokens,
               "note": "Bedrock Runtime converse API has no seed parameter; --seed is recorded "
                       "for parity with spec_experiment/loop_generate options but this reply is "
                       "NOT reproducible from it"}
    model_field = args.tag if args.samples == 1 else f"{args.tag}-s{k}"
    if args.samples > 1:
        options["sample_index"] = k
        options["num_samples"] = args.samples
    record = {"task_id": tid, "fn": entry["fn"], "model": model_field, "digest": digest,
              "pool_version": "v1", "prompt_version": args.prompt,
              "options": options, "messages": messages, "reply": reply,
              "prompt_tokens": in_tok, "reply_tokens": out_tok,
              "eval_s": round(wall, 3), "wall_s": round(wall, 3), "done_reason": stop_reason}
    return record, in_tok, out_tok


# ----------------------------------------------------------------- main --

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tag", required=True, help="model tag; records land under "
                     "out/spec-experiment/<tag-slug>/ (spec_experiment.outdir)")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                     help="Bedrock model id / cross-region inference profile id "
                          f"(default: {DEFAULT_MODEL})")
    ap.add_argument("--region", default=DEFAULT_REGION)
    ap.add_argument("--prompt", choices=se.PROMPT_VERSIONS, default="v1",
                     help="v1 (default; 12.7's rule -- no round is compared under v2 "
                          "until the control is re-measured under it)")
    ap.add_argument("--samples", type=int, default=1,
                     help="K replies per problem (default 1: greedy). K > 1 writes K "
                          "sample-tag directories <tag>-s<k>, loop_generate's convention")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids-file", default="", help="path to a file of comma/newline-separated "
                     "task ids; restricts the pool to these")
    ap.add_argument("--only-heldout", default="", help="path to a split.json or heldout.json; "
                     "restricts to its heldout_task_ids (== eval_ids in split.json)")
    ap.add_argument("--seed", type=int, default=1, help="recorded for parity with "
                     "spec_experiment/loop_generate; Bedrock has no seed parameter, so this "
                     "does NOT make samples reproducible (see the module docstring)")
    ap.add_argument("--concurrency", type=int, default=HARD_MAX_CONCURRENCY,
                     help=f"requests in flight at once, hard-capped at {HARD_MAX_CONCURRENCY}")
    ap.add_argument("--price-in-per-mtok", type=float, default=PRICE_IN_PER_MTOK)
    ap.add_argument("--price-out-per-mtok", type=float, default=PRICE_OUT_PER_MTOK)
    ap.add_argument("--spend-cap-usd", type=float, default=40.0,
                     help="stop submitting new requests once the running dollar estimate "
                          "would reach this (default 40.0)")
    args = ap.parse_args(argv)

    if args.samples < 1:
        print(f"bedrock_generate: --samples must be >= 1, got {args.samples}")
        return 2
    if args.samples > 1 and args.temperature <= 0:
        print(f"bedrock_generate: --samples {args.samples} > 1 requires --temperature > 0 "
              f"(got {args.temperature}); sampling at temperature 0 is degenerate. Refusing "
              f"before making any request.")
        return 2
    concurrency = min(args.concurrency, HARD_MAX_CONCURRENCY)
    if args.concurrency > HARD_MAX_CONCURRENCY:
        print(f"bedrock_generate: --concurrency {args.concurrency} exceeds the hard cap "
              f"{HARD_MAX_CONCURRENCY}; using {concurrency}")

    K = args.samples
    if K == 1:
        tag_dirs = [se.outdir(args.tag)]
    else:
        tag_dirs = [se.outdir(f"{args.tag}-s{k}") for k in range(K)]

    P, ids = select_ids(args.limit, args.ids_file, args.only_heldout)
    jobs: list[tuple[int, int]] = []   # (task_id, sample_index)
    for tid in ids:
        for k in range(K):
            if not (tag_dirs[k] / "raw" / f"{tid}.json").exists():
                jobs.append((tid, k))
    already = len(ids) * K - len(jobs)
    print(f"bedrock_generate: {len(ids)} problems selected x {K} sample(s) = "
          f"{len(ids) * K} records wanted, {already} already on disk, {len(jobs)} to generate")
    if not jobs:
        print("bedrock_generate: nothing to do; not calling Bedrock")
        return 0

    # deferred: keeps a bare --help / no-op run from touching AWS at all,
    # matching loop_generate's "heavy imports after argument validation and
    # after the no-op check" convention (there it is torch/CUDA; here it is
    # boto3 talking to a real service and needing live credentials)
    import boto3
    import botocore

    client = boto3.client("bedrock-runtime", region_name=args.region)
    digest = f"bedrock model={args.model} region={args.region} boto3={boto3.__version__}"
    totals = TokenTotals(args.price_in_per_mtok, args.price_out_per_mtok, args.spend_cap_usd)
    stop = threading.Event()
    first_error: list[BaseException] = []
    lock = threading.Lock()
    done = 0
    t_start = time.monotonic()

    def worker(tid: int, k: int):
        if stop.is_set():
            return
        if totals.over_cap():
            stop.set()
            return
        entry = P[tid]
        try:
            record, in_tok, out_tok = one_call(client, args, digest, tid, entry, k)
        except NonRetryable as e:
            stop.set()
            with lock:
                if not first_error:
                    first_error.append(e)
            return
        except botocore.exceptions.BotoCoreError as e:   # anything else botocore raises
            stop.set()
            with lock:
                if not first_error:
                    first_error.append(e)
            return
        totals.add(in_tok, out_tok)
        (tag_dirs[k] / "raw" / f"{tid}.json").write_text(
            json.dumps(record, indent=1), encoding="utf-8")

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = []
        for tid, k in jobs:
            if stop.is_set():
                break
            futures.append(pool.submit(worker, tid, k))
        for fut in concurrent.futures.as_completed(futures):
            fut.result()   # re-raise anything worker() itself failed to catch
            done += 1
            if done % 10 == 0 or done == 1:
                el = time.monotonic() - t_start
                i, o, c, d = totals.snapshot()
                print(f"generate: {done}/{len(jobs)} ({el:.0f}s, {el / max(done, 1):.1f} s each) "
                      f"tokens in={i} out={o} calls={c} est=${d:.4f}", flush=True)

    wall_total = time.monotonic() - t_start
    i, o, c, d = totals.snapshot()
    print(f"bedrock_generate: {c} calls completed, {i} input tokens, {o} output tokens, "
          f"estimated ${d:.4f} (in ${args.price_in_per_mtok}/Mtok, out ${args.price_out_per_mtok}/Mtok)")
    print(f"wall time: {wall_total:.1f} s ({wall_total / max(c, 1):.1f} s/call, "
          f"concurrency {concurrency})")

    if first_error:
        e = first_error[0]
        print(f"bedrock_generate: ABORTED on a non-retryable error: {e}", file=sys.stderr)
        print("bedrock_generate: this is not a code bug to retry around -- if the error names "
              "authorization / model access, fix it in the Bedrock console's Model access page "
              "(or `aws bedrock get-use-case-for-model-access` / "
              "`aws bedrock create-foundation-model-agreement`) and re-run; every already-"
              "written raw/<id>.json record stands and will be skipped on the next run.",
              file=sys.stderr)
        return 2
    if totals.over_cap():
        print(f"bedrock_generate: STOPPED, spend cap ${args.spend_cap_usd} reached "
              f"(estimate ${d:.4f}); re-run to continue from the records already on disk.")
        return 3
    if done < len(jobs):
        print(f"bedrock_generate: only {done} of {len(jobs)} jobs completed before stopping")
        return 1
    if K == 1:
        print()
        print("follow-up commands:")
        print(f"  python3 spec_experiment.py extract --model {args.tag}")
        print(f"  python3 spec_experiment.py tests    --model {args.tag}")
        tag_dir = se.model_tag(args.tag)
        print(f"  python3 run_par.py --tasks out/spec-experiment/{tag_dir}/tasks "
              f"--out out/spec-experiment/{tag_dir}/kernels "
              f"--table out/spec-experiment/{tag_dir}/kernels.md")
        print(f"  python3 spec_experiment.py table    --model {args.tag} "
              f"--out SPEC-EXPERIMENT-mbpp-{tag_dir}.md")
    else:
        tags = [f"{args.tag}-s{k}" for k in range(K)]
        print()
        print(f"sample tag directories ({K}): " + ", ".join(tags))
        print("follow-up commands (repeat for each tag above, substituting --model):")
        print(f"  python3 spec_experiment.py extract --model {tags[0]}")
        print(f"  python3 spec_experiment.py tests    --model {tags[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
