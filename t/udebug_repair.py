#!/usr/bin/env python3
"""t/udebug_repair.py -- one repair round for teacher samples the parser or the gate refused (2026-10-12).

    python3 t/udebug_repair.py --samples t/out/udebug/teacher-<tag> --provider vertex --project P \\
        [--model M] [--round 1] [--include-judge-fail] [--jobs 4]

Self-Debugging (Chen et al., arXiv:2304.05128) feeds a program's execution result or error message back to
the model that wrote it and asks for a fix; one round matched baselines sampling more than ten times as many
candidates. Here the message is the t parser's (line, column, expected token) or the well-formedness gate's
named refusal, both deterministic and specific, which the v1 and v2 pilots of
`t/PREDICT-2026-10-12-udebug-teacher.md` showed prose rules do not prevent. Our own September finding
(`t/FINDINGS-repair-2026-09-20.md`) is that proof repair with a witness barely moves the seven-kernel gate,
so this pass is registered on the parse rate, not the kernel count.

For every `<judge>-<id>/s<k>/result.json` whose parse failed or whose judge run was `ill-formed` (and, with
--include-judge-fail, whose judge run failed or errored), the conversation is replayed -- system, user, the
model's own reply -- and a user turn carries the refusal and asks for the whole task and io module again.
The reply lands in `s<k>r<round>/` as a sample like any other (`sample_index` = 100*round + k, so the gate's
report sorts it beside its parent), with `repair_of` and `refusal` recorded. `t/udebug_gate.py` grades it on
the next run; rows deduplicate by printed text, so a repair identical to an accepted sibling adds nothing.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import bedrock_generate as bg   # noqa: E402
import udebug_teacher as ut     # noqa: E402

LOC = re.compile(r":(\d+):(\d+): (.*)")


def refusal_text(res: dict, task_path: Path) -> str | None:
    parse = res.get("parse") or ""
    lift = res.get("lift") or {}
    if parse.startswith("lift-"):
        if lift.get("status") == "refused":
            reason = lift.get("reason", "")
            try:                                   # the lifter's record: {'stage', 'reason', 'token', 'line'}
                import ast
                d = ast.literal_eval(reason)
                tok = str(d.get("token", ""))
                if d.get("stage") == "resolve":
                    return f"Dafny refused the program: {tok}"
                if d.get("stage") == "check":
                    return (f"Dafny could not verify the program after lifting: the proof of `{tok}` fails. "
                            f"Strengthen the invariants or add the lemma the ensures needs.")
                return (f"The lifter to the verified language refused the program at stage {d.get('stage')}: "
                        f"{d.get('reason')} ({tok}). Stay in the subset: int, bool, seq<int>; one return; no "
                        f"quantifier over an unbounded range; no mutual recursion; no sequences of pairs.")
            except (ValueError, SyntaxError):
                return f"The lifter refused the program: {reason}"
        return f"The lifter did not accept the program: {lift.get('status')} {lift.get('tail', '')[-300:]}"
    if parse.startswith("error"):
        m = LOC.search(parse)
        if m:
            line, col, msg = int(m.group(1)), int(m.group(2)), m.group(3)
            src = task_path.read_text(encoding="utf-8").splitlines() if task_path.is_file() else []
            window = "\n".join(f"{i + 1:3}: {src[i]}" for i in range(max(0, line - 3), min(len(src), line + 1)))
            return (f"The t parser refused the task at line {line}, column {col}: {msg}\n"
                    f"The lines around it:\n{window}")
        return f"The t parser refused the task: {parse[6:].strip()}"
    j = res.get("judge") or {}
    if j.get("status") == "ill-formed":
        return f"The well-formedness gate refused the task: {j.get('reason', '')}"
    if j.get("status") == "fail":
        return (f"The judge's stored cases disagree with the program: {j.get('passed')} of {j.get('total')} "
                f"files match. First difference: {j.get('first_difference')}")
    if j.get("status") == "error":
        tail = (j.get("tail") or "").strip().splitlines()
        return "Running the task on the judge's input failed: " + (tail[-1] if tail else "unknown error")
    return None


def wants_repair(res: dict, include_judge_fail: bool) -> bool:
    if (res.get("parse") or "").startswith(("error", "lift-")):
        return True
    status = (res.get("judge") or {}).get("status")
    return status == "ill-formed" or (include_judge_fail and status in ("fail", "error"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--samples", required=True)
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--include-judge-fail", action="store_true")
    ap.add_argument("--provider", choices=("bedrock", "vertex"), default="vertex")
    ap.add_argument("--model", default="")
    ap.add_argument("--region", default=bg.DEFAULT_REGION)
    ap.add_argument("--project", default="")
    ap.add_argument("--location", default="global")
    ap.add_argument("--adc", default="~/.config/gcloud/application_default_credentials.json")
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--price-in-per-mtok", type=float, default=0.56)
    ap.add_argument("--price-out-per-mtok", type=float, default=1.68)
    ap.add_argument("--spend-cap-usd", type=float, default=2.0)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)

    samples = Path(a.samples)
    jobs = []
    for res_path in sorted(samples.glob("*/s*/result.json")):
        d = res_path.parent
        if "r" in d.name:                       # a repair is not repaired again in this round
            continue
        res = json.loads(res_path.read_text(encoding="utf-8"))
        if not wants_repair(res, a.include_judge_fail):
            continue
        target = d.parent / f"{d.name}r{a.round}"
        if (target / "record.json").is_file():
            continue
        rec = json.loads((d / "record.json").read_text(encoding="utf-8"))
        target = rec.get("target", "t")
        refusal = refusal_text(res, d / f"p{rec['id']}{'.dfy' if target == 'dafny' else '.t'}")
        if refusal is None:
            continue
        jobs.append((d, target, rec, res, refusal))
    if a.limit:
        jobs = jobs[:a.limit]
    print(f"{len(jobs)} samples to repair (round {a.round})", flush=True)
    if not jobs:
        return 0

    if a.provider == "bedrock":
        import boto3
        client = boto3.client("bedrock-runtime", region_name=a.region)
        model, endpoint = a.model or ut.DEFAULT_MODEL, f"bedrock:{a.region}"

        def call(messages):
            system_blocks, conv = bg.to_bedrock_messages(messages)
            resp = bg.call_with_backoff(client, model, system_blocks, conv, a.max_tokens, a.temperature)
            msg = resp.get("output", {}).get("message", {})
            reply = "".join(b.get("text", "") for b in msg.get("content", []) if "text" in b)
            usage = resp.get("usage", {})
            return reply, usage.get("inputTokens", 0) or 0, usage.get("outputTokens", 0) or 0, resp.get("stopReason")
    else:
        if not a.project:
            raise SystemExit("udebug_repair: --project is required with --provider vertex")
        model, endpoint = a.model or ut.VERTEX_MODEL, ut.vertex_url(a.project, a.location)
        token = ut.VertexToken(a.adc)
        ut.force_ipv4()

        def call(messages):
            return ut.vertex_call(endpoint, token, model, messages, a.max_tokens, a.temperature)

    lock = threading.Lock()
    ledger = {"in": 0, "out": 0, "calls": 0, "usd": 0.0, "stop": False, "fences": 0}

    def one(job):
        d, target_dir, rec, res, refusal = job
        if ledger["stop"]:
            return
        lang = rec.get("target", "t")                # the language the sample answered in: t or dafny
        what = "Dafny program" if lang == "dafny" else "t task"
        ask = (refusal + f"\n\nRewrite the whole {what} (and the io module if it must change) so that it is accepted, "
               f"keeping the problem's meaning. Reply with exactly two fenced blocks again: ```{lang} then ```python.")
        messages = rec["messages"] + [{"role": "assistant", "content": rec["reply"]}, {"role": "user", "content": ask}]
        t0 = time.monotonic()
        try:
            reply, in_tok, out_tok, stop = call(messages)
        except bg.NonRetryable as e:
            with lock:
                ledger["stop"] = True
            print(f"ABORT {d}: {e}", file=sys.stderr, flush=True)
            return
        t_src, io_src = ut.extract(reply, lang)
        suffix = ".dfy" if lang == "dafny" else ".t"
        target_dir.mkdir(parents=True, exist_ok=True)
        if t_src is not None:
            (target_dir / f"p{rec['id']}{suffix}").write_text(t_src.rstrip() + "\n", encoding="utf-8")
        io_text = io_src if io_src is not None else (
            (d / f"p{rec['id']}_io.py").read_text(encoding="utf-8") if (d / f"p{rec['id']}_io.py").is_file() else None)
        if io_text is not None:
            (target_dir / f"p{rec['id']}_io.py").write_text(io_text.rstrip() + "\n", encoding="utf-8")
        k = rec["sample_index"]
        record = dict(rec, model=model, provider=a.provider, endpoint=endpoint, sample_index=100 * a.round + k,
                      repair_of=k, repair_round=a.round, refusal=refusal, messages=messages, reply=reply,
                      prompt_tokens=in_tok, reply_tokens=out_tok, wall_s=round(time.monotonic() - t0, 3),
                      done_reason=stop, fences={"t": t_src is not None, "python": io_src is not None},
                      options=dict(rec.get("options", {}), temperature=a.temperature))
        (target_dir / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        with lock:
            ledger["in"] += in_tok
            ledger["out"] += out_tok
            ledger["calls"] += 1
            ledger["fences"] += t_src is not None
            ledger["usd"] = ledger["in"] / 1e6 * a.price_in_per_mtok + ledger["out"] / 1e6 * a.price_out_per_mtok
            if ledger["usd"] >= a.spend_cap_usd:
                ledger["stop"] = True
                print(f"SPEND CAP: ${ledger['usd']:.3f}", file=sys.stderr, flush=True)
            print(f"{ledger['calls']}/{len(jobs)} {target_dir.relative_to(samples)}: {in_tok}+{out_tok} tok, "
                  f"t-fence={t_src is not None}, ${ledger['usd']:.3f}", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(a.jobs, 4))) as ex:
        list(ex.map(one, jobs))
    summary = {"round": a.round, "model": model, "provider": a.provider, "repairs_requested": len(jobs),
               "calls_made": ledger["calls"], "replies_with_t_fence": ledger["fences"],
               "input_tokens": ledger["in"], "output_tokens": ledger["out"], "usd_estimate": round(ledger["usd"], 4),
               "stopped_early": ledger["stop"]}
    (samples / f"repair-r{a.round}-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=1))
    return 0 if not ledger["stop"] else 1


if __name__ == "__main__":
    sys.exit(main())
