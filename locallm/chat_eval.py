"""chat_eval.py: judge a chat-trained locallm with the proof engine's own grader.

    python3 locallm/chat_eval.py --model <dir> --conversations conv.jsonl --out eval.json \
        [--dev 100] [--val 0] [--max-tokens 400]

nanochat's scripts/chat_eval.py (https://github.com/karpathy/nanochat) samples
an answer per task problem through the engine and checks it (GSM8K's number,
HumanEval's tests). dawnr's checks are the project's own, and nothing here
re-implements one:

* dev problems (t/r12-dev-ids.json: MBPP train-side problems no training
  document names, the set r12 chooses stopping steps on) are asked with the
  prompt the r12 generator uses (loop_locallm.problem_head with its two
  Example lines), greedily, through the engine with the t tool live; the
  final program is graded by t/rl_reward.local_signals and rl_reward.tier:
  none, parses, typed, tests (the problem's assertions and 50 drawn inputs
  against its reference). The proof tiers need Dafny; `--prove` is not
  offered here, so the report says the top tiers were not asked.
* validation conversations (the corpus documents chat_data.py put on the
  validation side of the hash split) are asked with their user turn; the
  final program is checked by t_tool (parses, well formed, the examples).

Both sets also get the numbers that say whether the model acts on a failed
check (FINDINGS-repair-2026-09-26.md): the final program (the last call, else
the text) run by the t tool on the prompt's own Example lines; whether an
answer that got a failing verdict made a later call with a different program
(acted on it) or the same one again; whether a failing first verdict ended in
a program that passes every example (repaired); and the calls themselves:
opened, closed, ended inside a call by <|assistant_end|>, out of tokens inside
a call, and the grammar's overrides (engine.py). `--grammar` evaluates with
engine.py's chat-token grammar (off by default, as in the engine), to measure
what it changes on the same checkpoint; `--max-calls N` (with `--grammar`)
gives the engine a budget of N tool calls.

Which program is the answer: `--answer last` (the default, and the rule the
first repair runs registered) takes the last call, else the text.
`--answer best-verdict` takes the call whose t-tool verdict ranks highest
(every example passes, then parses and well formed, then parses), the latest
among equals, else the text: the reply's calls are samples the tool already
ran on the user's own examples, and AlphaCode (arXiv:2203.07814) filters its
samples by their behaviour on the problem's example tests. `--rescore ROWS`
recomputes every number from an earlier run's rows under `--answer` without
generating anything (the rows hold every call and verdict).

`--samples N` (N above 1) asks each dev problem N times by sampling instead of once
greedily: the base rate a reward or a selector would have to work with. It draws at
`--temperature` and `--top-k` (defaults 0.8 and 20, the sampler t/RL-DESIGN-2026-09-26.md
section 3 measured with) through the same engine, grammar, call budget and answer rule, in
batches of `--sample-batch` rows, each batch seeded by t/pilot_sampling.derive_seed. Every
draw is graded like a greedy answer. The report gives, for well formed, passes all shown
examples, the tests tier, and agrees with the specification check: the problems with any
such draw, the rate per draw, pass@k (human-eval's unbiased estimate
1 - comb(n - c, k) / comb(n, k), arXiv:2107.03374,
https://github.com/openai/human-eval), and the problems whose rate lies in the design's
difficulty band (0, 1/4]. Draws that pass their examples and disagree with the
specification are counted: they are the negatives t/NEGATIVES-2026-09-25.md lacked.

The held-out evaluation problems are never asked: an id in the split's
eval_ids is refused by name.

Each validation row also carries "tool": chat_data.py's own per-conversation flag for whether
the proved answer needed the tool. This is the held-out tool-conversation subset
locallm/dawnr_report.py's scorecard reports separately ("tool use"): filtering a run's
.rows.jsonl to "tool": true isolates conversations no training document answers where using
the tool was part of a correct answer, instead of mixing them into the whole validation
average.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "t"))


def ask(engine, tok, user: str, max_tokens: int) -> dict:
    import chat
    prompt = chat.render_for_completion(tok, {"messages": [{"role": "user", "content": user}]})
    results, _masks = engine.generate_batch(prompt, 1, max_tokens=max_tokens, temperature=0.0, seed=0)
    return row_record(tok, results[0], engine.rows[0])


def ask_many(engine, tok, user: str, max_tokens: int, samples: int, temperature: float, top_k, seed_of,
             batch: int = 32) -> list[dict]:
    """`samples` sampled replies to one prompt, `batch` rows at a time (the engine copies the prompt's
    cache to every row, so the batch bounds the memory); `seed_of(b)` seeds batch b's generator."""
    import chat
    prompt = chat.render_for_completion(tok, {"messages": [{"role": "user", "content": user}]})
    out = []
    for b, start in enumerate(range(0, samples, batch)):
        n = min(batch, samples - start)
        results, _masks = engine.generate_batch(prompt, n, max_tokens=max_tokens, temperature=temperature,
                                                top_k=top_k, seed=seed_of(b))
        out.extend(row_record(tok, results[i], engine.rows[i]) for i in range(n))
    return out


def row_record(tok, new_tokens: list[int], row) -> dict:
    """One generated row as the answer record every scorer here reads."""
    import chat
    from engine import reply_parts
    parts = reply_parts(tok, new_tokens)
    # the calls that submitted a program (a t span, or a registry call to t or an MCP t_check: chat.call_program),
    # with their verdicts; a registry call that submits none (a fetch, an unknown tool) is not a draft
    checked = [(program, out) for (text, out), kind in zip(row.tool_calls, row.call_kinds)
               if (program := text if kind == "t" else chat.call_program({"type": "tool", "text": text})) is not None]
    return {"parts": parts, "program": chat.final_program(parts) if parts else None,
            "tool_calls": len(row.tool_calls), "calls": [c[0] for c in checked],
            "tool_verdicts": [c[1] for c in checked], "ended": row.completed,
            "unclosed_call": row.in_tool_block or row.ended_in_call, "ended_in_call": row.ended_in_call,
            "budget_in_call": row.in_tool_block and not row.completed,
            "grammar_overrides": row.grammar_overrides, "budget_refusals": row.budget_refusals,
            "new_tokens": len(new_tokens)}


def verdict_rank(verdict: str) -> int:
    """3 nothing wrong, 2 parses and well formed, 1 parses, 0 does not."""
    lines = verdict.split("\n")
    return 3 if verdict_ok(verdict) else 2 if "well formed: yes" in lines else 1 if "parses: yes" in lines else 0


def answer_program(got: dict, policy: str) -> str | None:
    """The program that answers: the last call or text ("last"), or the best-verdict call ("best-verdict")."""
    if policy == "last":
        return got["program"]
    if policy != "best-verdict":
        raise ValueError(f"unknown answer policy {policy!r}")
    ranked = [(verdict_rank(v), i) for i, v in enumerate(got["tool_verdicts"])]
    if not ranked:
        return got["program"]
    return got["calls"][max(ranked)[1]].strip() or None


def verdict_ok(verdict: str) -> bool:
    """A t-tool verdict with nothing wrong in it: parses, well formed, every example passes."""
    lines = [ln for ln in verdict.split("\n") if ln.strip()]
    return bool(lines) and all(ln in ("parses: yes", "well formed: yes") or
                               (ln.startswith(("example ", "drawn ")) and ln.endswith(": pass")) for ln in lines)


def judge(got: dict, user: str) -> dict:
    """got["program"] (the answer) under the t tool on the prompt's examples, and what the reply did with its
    verdicts."""
    import t_tool
    verdict = t_tool.call(got["program"], user) if got["program"] else "parses: no: no program"
    lines = verdict.split("\n")
    examples = [ln for ln in lines if ln.startswith("example")]
    failed = [i for i, v in enumerate(got["tool_verdicts"]) if not verdict_ok(v)]
    calls = [c.strip() for c in got["calls"]]
    acted = any(any(calls[j] != calls[i] for j in range(i + 1, len(calls))) for i in failed)
    repeated = any(any(calls[j] == calls[i] for j in range(i + 1, len(calls))) for i in failed)
    pass_all = bool(examples) and all(ln.endswith(": pass") for ln in examples)
    return {"verdict": verdict, "parses": "parses: yes" in lines, "well_formed": "well formed: yes" in lines,
            "examples_all_pass": pass_all, "got_failing_verdict": bool(failed), "acted_on_failure": acted,
            "repeated_after_failure": repeated, "repaired": bool(failed) and failed[0] == 0 and pass_all}


def _jsonable(v):
    try:
        json.dumps(v)
        return v
    except (TypeError, ValueError):
        return repr(v)


def spec_agreement(program: str | None, entry: dict, n: int = 200, seed: int = 0) -> dict:
    """The answer's specification against the problem's own solution on n drawn inputs
    (t/spec_check.check_task, the check the held-out scorer applies as step 8), brought to
    the dev split (2026-09-29). Two shown examples underdetermine a problem: on the held-out
    232 one parity program answered three unrelated problems, passed each one's shown
    examples, was proved against its own specification in seven kernels, and failed every
    problem on drawn inputs. CodeT (arXiv:2207.10397) selects code by execution on generated
    tests beyond the given examples for the same reason. The status is "agrees" only when
    every drawn input the reference computes satisfies the ensures; "disagrees" names the
    first input that does not; anything else is the check's own refusal, reported, never
    counted as either."""
    import random
    import spec_check
    import surface
    if not program:
        return {"status": "no program"}
    try:
        task = surface.parse(program)
    except Exception as e:                                        # noqa: BLE001
        return {"status": "parse", "why": str(e)[:120]}
    try:
        r = spec_check.check_task(task, entry, n, random.Random(seed))
    except Exception as e:                                        # noqa: BLE001
        return {"status": f"check failed: {type(e).__name__}"}
    return {k: _jsonable(v) for k, v in r.items()}


COUNTED = ("parses", "well_formed", "examples_all_pass", "got_failing_verdict", "acted_on_failure",
           "repeated_after_failure", "repaired")


def tally(counts, got: dict, judged: dict) -> None:
    counts["asked"] += 1
    for key in COUNTED:
        counts[key] += judged[key]
    counts["used_tool"] += got["tool_calls"] > 0
    counts["opened_call"] += got["tool_calls"] > 0 or got["unclosed_call"]
    counts["closed_every_call"] += got["tool_calls"] > 0 and not got["unclosed_call"]
    counts["unclosed_call"] += got["unclosed_call"]
    counts["ended_in_call"] += got["ended_in_call"]
    counts["budget_in_call"] += got["budget_in_call"]
    counts["ended"] += got["ended"]
    counts["tool_calls_total"] += got["tool_calls"]
    counts["grammar_overrides"] += got["grammar_overrides"]
    counts["answers_overridden"] += got["grammar_overrides"] > 0
    counts["budget_refusals"] += got.get("budget_refusals", 0)
    counts["answer_not_last"] += (got["program"] or "").strip() != (got["last_program"] or "").strip()


ROW_KEYS = ("program", "last_program", "tool_calls", "calls", "tool_verdicts", "ended", "unclosed_call",
            "ended_in_call", "budget_in_call", "grammar_overrides", "budget_refusals", "new_tokens")
GOT_KEYS = ("tool_calls", "calls", "tool_verdicts", "ended", "unclosed_call", "ended_in_call", "budget_in_call",
            "grammar_overrides", "new_tokens")


def from_row(row: dict) -> dict:
    """An earlier run's answer as ask() returned it, for --rescore."""
    got = {k: row[k] for k in GOT_KEYS}
    got["program"] = row.get("last_program", row["program"])
    got["budget_refusals"] = row.get("budget_refusals", 0)
    return got


def answered(got: dict, policy: str) -> dict:
    return dict(got, program=answer_program(got, policy), last_program=got["program"])


def pass_at_k(n: int, c: int, k: int) -> float:
    """The unbiased estimate that at least one of k draws is correct, from n draws of which c were:
    1 - comb(n - c, k) / comb(n, k) (human-eval's estimate_pass_at_k, arXiv:2107.03374)."""
    from math import comb
    if not (0 <= c <= n and 1 <= k <= n):
        raise ValueError(f"pass@{k} needs 0 <= c <= n and 1 <= k <= n; got n={n}, c={c}")
    return 1.0 - comb(n - c, k) / comb(n, k)


SAMPLED = ("well_formed", "examples_all_pass", "tests", "spec_agrees", "examples_pass_spec_disagrees")


def sampled_summary(per_problem: list[dict], ks=(1, 8, 16, 64)) -> dict:
    """Per-problem counts over n draws -> what sampling reaches, per measure: the problems with any
    such draw, the rate per draw, pass@k averaged over problems (a k above some problem's n is left
    out, as human-eval does), and the problems whose rate lies in (0, 1/4], the difficulty band
    t/RL-DESIGN-2026-09-26.md takes from STP."""
    if not per_problem:
        raise ValueError("no problems were sampled")
    fewest = min(p["n"] for p in per_problem)
    total = sum(p["n"] for p in per_problem)
    out: dict = {"problems": len(per_problem), "draws": total}
    for key in SAMPLED:
        out[key] = {"problems_with_any": sum(p[key] > 0 for p in per_problem),
                    "draws": sum(p[key] for p in per_problem),
                    "per_draw": round(sum(p[key] for p in per_problem) / total, 5),
                    "in_band": sum(0 < p[key] / p["n"] <= 0.25 for p in per_problem),
                    "pass_at": {str(k): round(sum(pass_at_k(p["n"], p[key], k) for p in per_problem)
                                              / len(per_problem), 5) for k in ks if k <= fewest}}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--conversations", type=Path, default=None, help="chat_data.py JSONL (validation side is asked)")
    ap.add_argument("--split", type=Path, default=ROOT / "t" / "out" / "loop" / "split-v5.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dev", type=int, default=100, help="how many dev problems to ask (0: none)")
    ap.add_argument("--val", type=int, default=0, help="how many validation conversations to ask (0: all)")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--grammar", action="store_true", help="engine.py's chat-token grammar (off by default)")
    ap.add_argument("--max-calls", type=int, default=None, help="a budget of tool calls per answer (with the grammar)")
    ap.add_argument("--answer", choices=("last", "best-verdict"), default="last")
    ap.add_argument("--rescore", type=Path, default=None,
                    help="an earlier run's .rows.jsonl: recompute its numbers under --answer, generate nothing")
    ap.add_argument("--samples", type=int, default=1,
                    help="draws per dev problem; above 1 the dev problems are sampled instead of answered "
                         "greedily, and only they are asked")
    ap.add_argument("--temperature", type=float, default=0.8, help="with --samples above 1")
    ap.add_argument("--top-k", type=int, default=20, help="with --samples above 1")
    ap.add_argument("--sample-batch", type=int, default=32, help="rows generated at once, with --samples above 1")
    ap.add_argument("--seed", type=int, default=1, help="with --samples above 1: the seed every batch's is derived from")
    ap.add_argument("--device", default=None)
    a = ap.parse_args(argv)
    if a.max_calls is not None and not a.grammar:
        ap.error("--max-calls works through the grammar; add --grammar")
    if a.samples < 1 or a.sample_batch < 1:
        ap.error("--samples and --sample-batch are at least 1")
    if a.samples > 1 and (a.rescore or a.conversations is not None or not a.dev or a.temperature <= 0):
        ap.error("--samples above 1 samples the dev problems only: no --rescore, no --conversations, "
                 "--dev above 0 and a temperature above 0")

    import chat
    import loop_filter
    import loop_locallm
    import rl_reward
    import spec_experiment as se
    from checkpoint import load_checkpoint
    from engine import Engine

    eval_ids = {int(i) for i in json.loads(a.split.read_text(encoding="utf-8"))["eval_ids"]}
    started = time.monotonic()
    if a.rescore:
        earlier = json.loads(a.rescore.with_name(a.rescore.name.replace(".rows.jsonl", ".json")).read_text())
        old_rows = [json.loads(line) for line in a.rescore.read_text(encoding="utf-8").splitlines() if line.strip()]
        dev_rows = {r["task_id"]: r for r in old_rows if r["set"] == "dev"}
        val_rows = [r for r in old_rows if r["set"] == "val"]
        out: dict = {"model": earlier["model"], "max_tokens": earlier["max_tokens"], "decoding": "greedy",
                     "grammar": earlier.get("grammar", True), "max_calls": earlier.get("max_calls"),
                     "answer": a.answer, "rescored_from": str(a.rescore)}

        def reply(user, key):
            row = dev_rows[key] if isinstance(key, int) else val_rows[key[1]]
            if isinstance(key, tuple) and row.get("source") != key[0]:
                raise SystemExit(f"{a.rescore}: validation row {key[1]} is {row.get('source')}, not {key[0]}")
            return answered(from_row(row), a.answer)
    else:
        model, tok, _ = load_checkpoint(a.model, a.device)
        if not chat.has_chat_tokens(tok):
            raise SystemExit(f"{a.model} has no chat tokens; chat_eval judges chat-trained checkpoints")
        engine = Engine(model, tok, grammar=a.grammar, max_calls=a.max_calls)
        out = {"model": str(a.model), "max_tokens": a.max_tokens, "decoding": "greedy",
               "grammar": a.grammar, "max_calls": a.max_calls, "answer": a.answer}

        def reply(user, key):
            return answered(ask(engine, tok, user, a.max_tokens), a.answer)
    rows_path = a.out.with_suffix(".rows.jsonl")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    rows_file = rows_path.open("w", encoding="utf-8")

    if a.samples > 1:
        import pilot_sampling
        dev = sorted(loop_filter.r12_dev_ids())[:a.dev]
        leak = set(dev) & eval_ids
        if leak:
            raise SystemExit(f"dev ids overlap the held-out evaluation ids: {sorted(leak)[:5]}")
        pool = se.pool("v5")
        out.update(decoding="sampled", samples=a.samples, temperature=a.temperature, top_k=a.top_k,
                   sample_batch=a.sample_batch, seed=a.seed)
        per_problem, generating, grading = [], 0.0, 0.0
        for tid in dev:
            entry = pool[tid]
            user = loop_locallm.problem_head(entry, with_examples=True).rstrip("\n")
            t0 = time.monotonic()
            draws = ask_many(engine, tok, user, a.max_tokens, a.samples, a.temperature, a.top_k,
                             lambda b, tid=tid: pilot_sampling.derive_seed(a.seed, tid, a.temperature, b),
                             a.sample_batch)
            t1 = time.monotonic()
            generating += t1 - t0
            counts = Counter()
            for i, raw in enumerate(draws):
                got = answered(raw, a.answer)
                tier = rl_reward.tier(rl_reward.local_signals(tid, got["program"] or "", entry))
                judged = judge(got, user)
                # the drawn-input check only where it can count: an answer that fails a shown example
                # is not an agreeing answer whatever its specification says
                spec = (spec_agreement(got["program"], entry, seed=tid) if judged["examples_all_pass"]
                        else {"status": "not checked: an example fails"})
                counts["well_formed"] += judged["well_formed"]
                counts["examples_all_pass"] += judged["examples_all_pass"]
                counts["tests"] += tier in rl_reward.ORDER[3:]
                counts["spec_agrees"] += judged["examples_all_pass"] and spec.get("status") == "agrees"
                counts["examples_pass_spec_disagrees"] += (judged["examples_all_pass"]
                                                           and spec.get("status") == "disagrees")
                counts["used_tool"] += got["tool_calls"] > 0
                rows_file.write(json.dumps({"set": "dev-sampled", "task_id": tid, "draw": i, "tier": tier,
                                            "verdict": judged["verdict"], "spec": spec,
                                            "well_formed": judged["well_formed"],
                                            "examples_all_pass": judged["examples_all_pass"],
                                            **{k: got[k] for k in ROW_KEYS}}) + "\n")
            grading += time.monotonic() - t1
            per_problem.append({"task_id": tid, "n": len(draws), **{k: counts[k] for k in SAMPLED},
                                "used_tool": counts["used_tool"]})
            rows_file.flush()
            print(json.dumps(per_problem[-1]), flush=True)
        rows_file.close()
        out["dev_sampled"] = {**sampled_summary(per_problem), "per_problem": per_problem,
                              "generate_seconds": round(generating, 1), "grade_seconds": round(grading, 1)}
        out["seconds"] = round(time.monotonic() - started, 1)
        out["rows"] = str(rows_path)
        a.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in out["dev_sampled"].items() if k != "per_problem"}))
        return 0

    if a.dev:
        dev = sorted(loop_filter.r12_dev_ids())[:a.dev]
        leak = set(dev) & eval_ids
        if leak:
            raise SystemExit(f"dev ids overlap the held-out evaluation ids: {sorted(leak)[:5]}")
        pool = se.pool("v5")
        tiers, counts = Counter(), Counter()
        if a.rescore and set(dev) != set(dev_rows):
            raise SystemExit(f"{a.rescore} holds other dev problems than --dev {a.dev} asks")
        for tid in dev:
            entry = pool[tid]
            user = loop_locallm.problem_head(entry, with_examples=True).rstrip("\n")
            got = reply(user, tid)
            sig = rl_reward.local_signals(tid, got["program"] or "", entry)
            tier = rl_reward.tier(sig)
            tiers[tier] += 1
            judged = judge(got, user)
            tally(counts, got, judged)
            # the specification against the problem's own solution on drawn inputs, counted
            # beside "pass all examples" (spec_agreement above): the honest dev number is
            # an answer that passes the shown examples AND agrees on the draws
            spec = spec_agreement(got["program"], entry, seed=tid)
            counts["spec_agrees"] += judged["examples_all_pass"] and spec.get("status") == "agrees"
            counts["examples_pass_spec_disagrees"] += judged["examples_all_pass"] and spec.get("status") == "disagrees"
            counts["spec_unchecked"] += judged["examples_all_pass"] and spec.get("status") not in ("agrees", "disagrees")
            rows_file.write(json.dumps({"set": "dev", "task_id": tid, "tier": tier, "stage": sig.get("stage"),
                                        "tests": sig.get("tests"), "verdict": judged["verdict"], "spec": spec,
                                        **{k: judged[k] for k in COUNTED}, **{k: got[k] for k in ROW_KEYS}}) + "\n")
        out["dev"] = {**dict(counts), "asked": len(dev), "tiers": {t: tiers.get(t, 0) for t in rl_reward.ORDER},
                      "at_least_typed": sum(tiers[t] for t in rl_reward.ORDER[2:]),
                      "tests_passed": sum(tiers[t] for t in rl_reward.ORDER[3:]),
                      "proof": "not asked (the proof tiers need Dafny; rl_reward.prove)"}

    if a.conversations is not None:
        convs = [json.loads(line) for line in a.conversations.read_text(encoding="utf-8").splitlines() if line.strip()]
        val = [c for c in convs if c.get("split") == "val"]
        if a.val:
            val = val[:a.val]
        if a.rescore and len(val) != len(val_rows):
            raise SystemExit(f"{a.rescore} holds {len(val_rows)} validation rows, not {len(val)}")
        counts = Counter()
        for n, c in enumerate(val):
            user = c["messages"][0]["content"]
            got = reply(user, (c.get("source"), n))
            judged = judge(got, user)
            tally(counts, got, judged)
            exact = (got["program"] or "").strip() == chat.final_program(c["messages"][1]["content"]).strip()
            counts["exact_program"] += exact
            rows_file.write(json.dumps({"set": "val", "source": c.get("source"), "tool": bool(c.get("tool", False)),
                                        "verdict": judged["verdict"], "exact_program": exact,
                                        **{k: judged[k] for k in COUNTED}, **{k: got[k] for k in ROW_KEYS}}) + "\n")
        out["val"] = dict(counts)
    rows_file.close()
    out["seconds"] = round(time.monotonic() - started, 1)
    out["rows"] = str(rows_path)
    a.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
