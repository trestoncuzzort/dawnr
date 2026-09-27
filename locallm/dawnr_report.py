"""dawnr_report.py: report cards from what dawnr's stages and evaluators already wrote.

    python3 locallm/dawnr_report.py --run <pipeline out dir> [--heldout-tag TAG]
    python3 locallm/dawnr_report.py --checkpoint <dir> [--eval-json F] [--eval-rows F]
        [--heldout-tag TAG] [--injection-json F] [--memory-jsonl F] [--personalization-jsonl F]
        [--english-json F | --english-shard F] [--cpu-json F] [--out DIR]

nanochat's first release gathered every stage's numbers into one report.md
(https://github.com/karpathy/nanochat, nanochat/report.py); it was deleted
upstream on 2026-07-02 (commit f10bd751, "it just bloats the code"), because
every script had to call into it. Everything below only READS: `--run` reads
one dawnr_pipeline.py run's stage.json/eval.json files (`build`/`write`,
unchanged since 2026-09-26); `--checkpoint` reads whichever independent eval
files are named for one checkpoint (`scorecard`/`write_scorecard`, added
2026-09-27) so a checkpoint that never went through that one driver --
continued training, another track's own trainer, a per-person adapter -- gets
the same report card: core t skill, tool use, the injection-following rate,
memory recall and personalization (hooks only, until those tracks land),
general-English loss and CPU latency/memory. No stage or evaluator knows the
report exists, and a report can be rebuilt from a finished run, or from a
loose set of eval files, at any time.

dawnr's numbers, not nanochat's: characters per token; held-out loss on the
validation-side documents no stage trains on; the mid stage's loss on the
assistant's tokens; the dev problems' reward tiers from t/rl_reward.py (none,
parses, typed, tests; proved needs Dafny and is marked not asked); the t tool's
verdicts on validation conversations. The clean-200 score appears only for an
answer set that already exists (`--heldout-tag`, scored by t/score_heldout.py);
this never generates on the held-out problems.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
STAGES = ("tokenizer", "base", "conversations", "mid", "sft", "rl", "eval")


def _stage(run: Path, name: str) -> dict:
    hits = sorted(run.glob(f"*-{name}/stage.json"))
    return json.loads(hits[0].read_text(encoding="utf-8")) if hits else {}


def _f(v, digits=4):
    return "-" if v is None else (f"{v:.{digits}f}" if isinstance(v, float) else str(v))


def _pct(n, d):
    return "-" if not d else f"{n} of {d} ({100.0 * n / d:.1f}%)"


def _acting(counts: dict, n: int) -> list[str]:
    """What the answers did with the tool's verdicts (chat_eval.judge), when the eval recorded it."""
    if "got_failing_verdict" not in counts:
        return []
    failed = counts["got_failing_verdict"]
    return [f"- final program passes every example of the prompt: {_pct(counts['examples_all_pass'], n)}",
            f"- got a failing verdict: {_pct(failed, n)}; of those, a later call with a different program "
            f"{_pct(counts['acted_on_failure'], failed)}, the same program again "
            f"{_pct(counts['repeated_after_failure'], failed)}; first verdict failed and the final program passes "
            f"every example: {counts['repaired']}",
            f"- ended inside a call by <|assistant_end|>: {counts.get('ended_in_call', 0)}; out of tokens inside a "
            f"call: {counts.get('budget_in_call', 0)}; the grammar overrode the model's top token "
            f"{counts.get('grammar_overrides', 0)} times in {counts.get('answers_overridden', 0)} answers"]


def heldout_section(tag: str, split: Path) -> list[str]:
    cmd = [sys.executable, str(ROOT / "t" / "score_heldout.py"), "--split", str(split), tag]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    out = (r.stdout + r.stderr).strip()
    return ["## Clean 200 (existing answer set, t/score_heldout.py)", "",
            f"`{' '.join(cmd[1:])}` exited {r.returncode}:", "", "```", out[-4000:], "```", ""]


def build(run: Path, heldout_tag: str | None = None, split: Path | None = None) -> str:
    s = {name: _stage(run, name) for name in STAGES}
    lines = [f"# dawnr report card: {run.name}", "",
             "Every number below links to the stage record it came from (`<n>-<stage>/stage.json`, which also "
             "holds the sha256 of every input). Built by locallm/dawnr_report.py from those files alone.", "",
             "| stage | status | seconds |", "|---|---|---|"]
    for name in STAGES:
        rec = s[name]
        lines.append(f"| {name} | {rec.get('status', 'not run')} | {_f(rec.get('seconds'), 1)} |")
    lines.append("")

    tok = s["tokenizer"].get("result", {})
    if tok:
        lines += ["## Tokenizer", "",
                  f"- origin: {tok['origin']}; vocabulary {tok['vocab_size']}",
                  f"- characters per token: {_f(tok['chars_per_token_train'])} on the train side "
                  f"({tok['train_documents']} documents), {_f(tok['chars_per_token_val'])} on the validation side "
                  f"({tok['val_documents']} documents)", ""]
    base = s["base"].get("result", {})
    if base:
        tr = base.get("training", {})
        ho = base.get("heldout", {})
        lines += ["## Base", "", f"- {base['origin']}: `{base['model']}`"]
        if tr:
            lines.append(f"- {base.get('n_layer')} layers, width {base.get('n_embd')}, context "
                         f"{base.get('block_size')}; kept weights: {tr.get('weights')} at step {tr.get('saved_step')} "
                         f"(train.py's own holdout loss {_f(tr.get('saved_val_loss'))} nats/token, stop: "
                         f"{tr.get('stop_reason')})")
        if ho:
            lines.append(f"- held-out loss on the {ho['documents']} validation-side documents (never trained on): "
                         f"**{_f(ho['nats_per_token'])} nats/token**, {_f(ho['nats_per_char'])} nats/char "
                         f"({ho['target_tokens']} tokens, {ho['cut_documents']} documents cut at the block)")
        lines.append("")
    conv = s["conversations"].get("result", {})
    if conv:
        lines += ["## Conversations (chat_data.py)", "",
                  f"- {conv['conversations']} from {conv['documents']} proved documents ({conv['train']} train, "
                  f"{conv['val']} validation; {conv['skipped']} skipped)",
                  f"- prompts: {conv['problem_heads']} with a Problem head, {conv['spec_prompts']} from the "
                  f"specification; {conv['with_examples']} with Example lines",
                  f"- tool conversations: {conv['tool_conversations']}; the tool's own verdicts on them: "
                  f"{conv['tool_example_pass']} examples pass, {conv['tool_example_other']} otherwise"]
        if conv.get("extra"):
            x = conv["extra"]
            lines.append(f"- added on the training side: {x['rows']} conversations from `{x['file']}` "
                         f"({', '.join(f'{v} {k}' for k, v in sorted(x['built'].items()))})")
        lines.append("")
    for name in ("mid", "sft"):
        rec = s[name]
        r = rec.get("result", {})
        if rec.get("status") == "skipped":
            lines += [f"## {name.upper()}", "", f"Skipped: {r.get('why')}", ""]
        elif r:
            i, f = r["initial"], r["final"]
            lines += [f"## {name.upper()} (chat_train.py)", "",
                      f"- {r['steps']} steps at lr {r['lr']}, {r['parameters']:,} parameters, "
                      f"{r['chat_tokens_added']} chat tokens added; {r['train']['conversations']} training "
                      f"conversations ({r['train']['target_tokens']} supervised tokens, "
                      f"{r['train']['tool_calls']} tool calls)",
                      f"- loss on the assistant's tokens, nats/token: train {_f(i['train'])} -> **{_f(f['train'])}**, "
                      f"validation {_f(i['val'])} -> **{_f(f['val'])}**",
                      f"- {r['seconds']} s" + (f", peak GPU memory {r['peak_cuda_bytes'] / 2**30:.2f} GiB"
                                               if r.get("peak_cuda_bytes") else ""), ""]
    rl = s["rl"]
    if rl:
        lines += ["## RL", "", f"{rl.get('status')}: {rl.get('result', {}).get('why', '')}", ""]
    ev = s["eval"].get("result", {})
    if ev:
        grammar = {True: "the chat-token grammar on", False: "the grammar off"}.get(ev.get("grammar"), "")
        lines += [f"## Evaluation (chat_eval.py, greedy, the t tool live{', ' + grammar if grammar else ''}, "
                  f"up to {ev.get('max_tokens')} new tokens)", ""]
        dev = ev.get("dev")
        if dev:
            n = dev["asked"]
            lines += [f"Dev problems (t/r12-dev-ids.json, train-side, named by no training document): {n}", "",
                      "| tier (t/rl_reward.py) | answers |", "|---|---|"]
            lines += [f"| {t} | {c} |" for t, c in dev["tiers"].items()]
            lines += ["",
                      f"- at least well formed: {_pct(dev['at_least_typed'], n)}; tests passed: "
                      f"**{_pct(dev['tests_passed'], n)}**",
                      f"- used the tool: {_pct(dev['used_tool'], n)}; opened a call and ended without closing "
                      f"it: {_pct(dev.get('unclosed_call', 0), n)}; ended with <|assistant_end|>: "
                      f"{_pct(dev['ended'], n)}"]
            lines += _acting(dev, n)
            lines += [f"- proof tiers: {dev['proof']}", ""]
        val = ev.get("val")
        if val:
            n = val["asked"]
            lines += [f"Validation conversations (proved documents on the validation side): {n}", "",
                      f"- parses {_pct(val.get('parses', 0), n)}; well formed {_pct(val.get('well_formed', 0), n)}; "
                      f"every example passes {_pct(val.get('examples_all_pass', 0), n)}; the proved program "
                      f"exactly {_pct(val.get('exact_program', 0), n)}",
                      f"- used the tool {_pct(val.get('used_tool', 0), n)}; opened a call without closing it "
                      f"{_pct(val.get('unclosed_call', 0), n)}; ended "
                      f"{_pct(val.get('ended', 0), n)}"]
            lines += _acting(val, n) + [""]
        lines += [f"Rows: `{ev.get('rows')}`", ""]
    if heldout_tag:
        lines += heldout_section(heldout_tag, split or ROOT / "t" / "out" / "loop" / "split-v5.json")
    else:
        lines += ["## Clean 200", "", "Not scored: this run generated nothing on the held-out problems, and no "
                  "existing answer set was named (`--heldout-tag`).", ""]
    return "\n".join(lines)


def write(run: Path, heldout_tag: str | None = None, split: Path | None = None) -> Path:
    path = Path(run) / "report.md"
    path.write_text(build(Path(run), heldout_tag, split), encoding="utf-8")
    return path


# =============================================================== the scorecard ==
# "One report card for all of dawnr" (AMBITION.md's dawnr and harness tables). build()/write()
# above read one dawnr_pipeline.py run's stages; scorecard() reads whatever independent eval
# files are named for one checkpoint instead, because a checkpoint dawnr grows into --
# continued training, another track's own trainer, a per-person adapter -- will not always
# have gone through that one driver. Every section below is independent, and a section whose
# input was not given, or whose file has nothing in it yet, is "not available" with why, never
# a false zero: AGENTS.md rule 2 is that an honest refusal beats a false verdict, and a memory,
# personalization or injection number before those tracks exist would be exactly the kind of
# unfalsifiable claim rule 1 forbids. Markdown and JSON are built from the same dict
# (render_scorecard(scorecard(...))), so the two outputs cannot disagree with each other.

SCORECARD_SECTIONS = ("core_skill", "tool_use", "injection", "memory", "personalization",
                      "general_english", "cpu")


def _na(why: str) -> dict:
    return {"status": "not available", "why": why}


def _ok(**data) -> dict:
    return {"status": "ok", **data}


def _read_json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_rows(path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def heldout_scores(tag: str, split: Path) -> dict:
    """t/score_heldout.py's own numbers for one existing answer tag, both panels (every eval
    id, and the clean 200 with same-task overlap removed) read back via --outcomes, which it
    already computes for t/compare_arms.py's paired comparison rather than re-implemented here.
    The markdown table it prints to stdout is kept verbatim (the same text heldout_section()
    above embeds in the pipeline-run report) so the two report formats never show different
    arithmetic for the same tag."""
    with tempfile.TemporaryDirectory() as d:
        outcomes = Path(d) / "outcomes.json"
        cmd = [sys.executable, str(ROOT / "t" / "score_heldout.py"), "--split", str(split),
               "--outcomes", str(outcomes), tag]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
        data = json.loads(outcomes.read_text(encoding="utf-8")) if outcomes.exists() else None
    if r.returncode != 0 or data is None:
        return {"ok": False, "returncode": r.returncode, "stderr_tail": (r.stderr or "")[-2000:],
                "table_markdown": (r.stdout or "").strip()}
    panels = data.get("panels", {})

    def panel(prefix):
        return next((v["tags"][tag] for k, v in panels.items() if k.startswith(prefix) and tag in v.get("tags", {})),
                    None)
    return {"ok": True, "table_markdown": (r.stdout or "").strip(), "all": panel("all-"), "clean_200": panel("clean-")}


def core_skill_section(eval_json, heldout_tag: str | None, split: Path) -> dict:
    """dev pass rate (chat_eval.py's own dev block, unmodified) and the clean 200 -- only ever
    from an EXISTING answer set named by tag, exactly as the pipeline-run report above already
    promises: this never generates on the held-out problems, it only reads a tag someone
    already ran."""
    out: dict = {}
    if eval_json is None:
        out["dev"] = _na("no --eval-json (locallm/chat_eval.py --out FILE)")
    else:
        rec = _read_json(eval_json)
        out["model"] = rec.get("model")
        dev = rec.get("dev")
        out["dev"] = _ok(**dev) if dev else _na(f"{eval_json} was not asked --dev problems (chat_eval.py --dev)")
    out["clean_200"] = (_na("no --heldout-tag (an existing t/score_heldout.py answer set)") if heldout_tag is None
                        else _ok(**heldout_scores(heldout_tag, split)))
    return out


TOOL_USE_KEYS = ("parses", "well_formed", "examples_all_pass", "got_failing_verdict", "acted_on_failure",
                 "repeated_after_failure", "repaired", "used_tool", "unclosed_call", "ended", "exact_program")


def tool_use_section(eval_rows) -> dict:
    """The held-out tool-conversation subset: chat_eval.py's val rows tagged "tool": true by
    chat_data.py (validation-side conversations no training document answers, where the proved
    program used the tool). "When present": an eval run with --val 0, or one from before
    chat_eval.py tagged rows this way, has none, and that is reported by name rather than as a
    zero, the same distinction core_skill_section draws for a missing dev block."""
    if eval_rows is None:
        return _na("no --eval-rows (chat_eval.py's --out FILE with .rows.jsonl next to it)")
    rows = [r for r in _read_rows(eval_rows) if r.get("set") == "val" and r.get("tool")]
    if not rows:
        return _na(f"{eval_rows} has no validation row tagged tool: true")
    n = len(rows)
    return _ok(n=n, **{key: _pct(sum(bool(r.get(key)) for r in rows), n) for key in TOOL_USE_KEYS})


def injection_section(injection_json) -> dict:
    """InjecAgent-shaped attack success rate (Zhan et al., arXiv:2403.02691) read from
    locallm/injection_eval.py's own output; that script refuses a checkpoint with no harness
    tokens by name (DAWNR-HARNESS.md section 8), so "not available" here covers both "never
    run" and "this checkpoint cannot be asked yet"."""
    if injection_json is None:
        return _na("no --injection-json (locallm/injection_eval.py --out FILE)")
    rec = _read_json(injection_json)
    return _ok(**{k: v for k, v in rec.items() if k != "rows"})


def memory_section(memory_jsonl) -> dict:
    """memory_metrics.recall_metrics over the memory track's own probe file (the schema
    locallm/memory_metrics.py documents is the hook that track fills). Empty or absent is "not
    available": the memory track has not landed yet (AMBITION.md: "being built")."""
    import memory_metrics
    if memory_jsonl is None:
        return _na("no --memory-jsonl (schema: locallm/memory_metrics.py)")
    rows = memory_metrics.read_jsonl(memory_jsonl)
    return _ok(**memory_metrics.recall_metrics(rows)) if rows else _na(f"{memory_jsonl} has no probes yet")


def personalization_section(personalization_jsonl) -> dict:
    """memory_metrics.personalization_metrics over the per-person learning track's own probe
    file; same "being built" status as memory, same hook module."""
    import memory_metrics
    if personalization_jsonl is None:
        return _na("no --personalization-jsonl (schema: locallm/memory_metrics.py)")
    rows = memory_metrics.read_jsonl(personalization_jsonl)
    return (_ok(**memory_metrics.personalization_metrics(rows)) if rows
            else _na(f"{personalization_jsonl} has no probes yet"))


def general_english_section(english_json) -> dict:
    """dawnr_pipeline.heldout_loss's own nats/token and nats/char, either freshly computed
    against --english-shard or read back from a prior run's --english-json. "When available"
    (this section's own condition): the general-English pretraining layer is surveyed and
    decontaminated but not yet run (internal/PRETRAIN-DAWNR-GENERAL.md), so today's checkpoints
    have no such shard to score."""
    if english_json is None:
        return _na("no --english-json / --english-shard (internal/PRETRAIN-DAWNR-GENERAL.md; not yet run)")
    return _ok(**_read_json(english_json))


def cpu_section(bench_json) -> dict:
    """locallm/checkpoint_bench.py's own numbers for this checkpoint: tokens/second and peak
    resident memory generating its own text on the CPU it was measured on."""
    if bench_json is None:
        return _na("no --cpu-json (locallm/checkpoint_bench.py --out FILE)")
    return _ok(**{k: v for k, v in _read_json(bench_json).items() if k != "runs"})


def english_loss_from_shard(model_dir: Path, shard: Path, block: int = 0) -> dict:
    """Run dawnr_pipeline.heldout_loss (base pretraining's own held-out-loss function) on an
    already-held-out English text shard, documents separated by a blank line (data.DOC_END's
    convention), instead of a second implementation of the same cross-entropy loop."""
    import dawnr_pipeline as dp
    docs = [d for d in Path(shard).read_text(encoding="utf-8").split("\n\n") if d.strip()]
    if not docs:
        raise ValueError(f"{shard}: no documents (blank-line separated, data.DOC_END)")
    return {"shard": str(shard), **dp.heldout_loss(model_dir, docs, block)}


def scorecard(*, checkpoint=None, eval_json=None, eval_rows=None, heldout_tag: str | None = None,
             split: Path = ROOT / "t" / "out" / "loop" / "split-v5.json", injection_json=None, memory_jsonl=None,
             personalization_jsonl=None, english_json=None, cpu_json=None) -> dict:
    """One dict, every key of SCORECARD_SECTIONS present, "not available" where an input was
    not named. checkpoint is recorded but not itself read: every number comes from a file some
    other command already wrote, the same "only reads" rule build() follows above."""
    return {"checkpoint": str(checkpoint) if checkpoint else None,
            "core_skill": core_skill_section(eval_json, heldout_tag, split),
            "tool_use": tool_use_section(eval_rows),
            "injection": injection_section(injection_json),
            "memory": memory_section(memory_jsonl),
            "personalization": personalization_section(personalization_jsonl),
            "general_english": general_english_section(english_json),
            "cpu": cpu_section(cpu_json)}


def _status_lines(title: str, section: dict) -> list[str]:
    lines = [f"## {title}", ""]
    return lines + [f"Not available: {section['why']}", ""] if section.get("status") == "not available" else lines


def render_scorecard(data: dict) -> str:
    lines = [f"# dawnr scorecard: {data.get('checkpoint') or '(no checkpoint path given)'}", "",
            "Every section below either reads a file named on the command line or says why it "
            "could not (`--help` lists them); built by locallm/dawnr_report.py's scorecard() "
            "from those files alone, none of them generated here.", ""]

    lines += ["## Core t skill", ""]
    dev = data["core_skill"].get("dev", {})
    if dev.get("status") == "ok":
        n = dev["asked"]
        lines += [f"Dev problems (t/r12-dev-ids.json): {n}", "",
                  f"- at least well formed: {_pct(dev['at_least_typed'], n)}; tests passed: "
                  f"**{_pct(dev['tests_passed'], n)}**", ""]
    else:
        lines += [f"Dev pass rate not available: {dev.get('why')}", ""]
    c200 = data["core_skill"].get("clean_200", {})
    if c200.get("status") == "ok" and c200.get("ok"):
        lines += ["Clean 200 (existing answer set, t/score_heldout.py):", "", "```",
                  c200["table_markdown"][-4000:], "```", ""]
    elif c200.get("status") == "ok":
        lines += [f"Clean 200: t/score_heldout.py exited {c200.get('returncode')}:", "", "```",
                  (c200.get("table_markdown") or c200.get("stderr_tail") or "")[-2000:], "```", ""]
    else:
        lines += [f"Clean 200 not available: {c200.get('why')}", ""]

    lines += _status_lines("Tool use (held-out tool-conversation subset)", data["tool_use"])
    if data["tool_use"].get("status") == "ok":
        tu = data["tool_use"]
        lines += [f"{tu['n']} held-out validation conversations whose proved answer used the tool:", "",
                  f"- every example passes: {tu['examples_all_pass']}; used the tool this reply: "
                  f"{tu['used_tool']}; opened a call without closing it: {tu['unclosed_call']}",
                  f"- got a failing verdict, then acted on it (a different program): {tu['acted_on_failure']}; "
                  f"repeated the same one: {tu['repeated_after_failure']}; repaired: {tu['repaired']}", ""]

    lines += _status_lines("Injection-following rate", data["injection"])
    if data["injection"].get("status") == "ok":
        inj = data["injection"]
        lines += [f"{inj['fixtures']} fixtures (locallm/injection_eval.py, InjecAgent-shaped, arXiv:2403.02691): "
                  f"**{_pct(inj['followed'], inj['fixtures'])}** followed the planted instruction", "",
                  "| disguise | n | followed | rate |", "|---|---|---|---|"]
        lines += [f"| {d} | {v['n']} | {v['followed']} | {v['rate']} |" for d, v in inj["by_disguise"].items()]
        lines += [""]

    lines += _status_lines("Memory recall", data["memory"])
    if data["memory"].get("status") == "ok":
        m = data["memory"]
        lines += [f"{m['probes']} probes over {m['people']} people (LongMemEval-shaped, arXiv:2410.10813): "
                  f"recall **{m['recall']}**, false-abstention rate {m['false_abstention_rate']}, "
                  f"hallucinated on an untold fact {m['hallucinated_on_untold_fact_rate']}", ""]

    lines += _status_lines("Personalization", data["personalization"])
    if data["personalization"].get("status") == "ok":
        p = data["personalization"]
        lines += [f"{p['probes']} probes over {p['people']} people: mean task uplift **{p['mean_task_uplift']}** "
                  f"({p['task_improved_share']} improved), mean general-loss change "
                  f"{p['mean_general_loss_change']} ({p['general_regressed_share']} regressed); both held at "
                  f"once: {p['net_positive_share']}", ""]

    lines += _status_lines("General-English held-out loss", data["general_english"])
    if data["general_english"].get("status") == "ok":
        ge = data["general_english"]
        lines += [f"{ge.get('documents')} documents, `{ge.get('shard', '')}`: "
                  f"**{_f(ge.get('nats_per_token'))} nats/token**, {_f(ge.get('nats_per_char'))} nats/char", ""]

    lines += _status_lines("CPU latency and memory", data["cpu"])
    if data["cpu"].get("status") == "ok":
        c = data["cpu"]
        params = f"{c['parameters']:,}" if isinstance(c.get("parameters"), int) else c.get("parameters", "-")
        lines += [f"{params} parameters on {c.get('processor', '?')} ({c.get('threads', '?')} threads): "
                  f"**{_f(c.get('median_tokens_per_second'), 2)} tok/s** median, "
                  f"{_f(c.get('median_ms_per_token'), 2)} ms/token, peak RSS "
                  f"{c.get('peak_rss_bytes', 0) / 2**20:.0f} MiB", ""]
    return "\n".join(lines)


def write_scorecard(out_dir: Path, **kwargs) -> tuple[Path, Path]:
    data = scorecard(**kwargs)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out_dir / "scorecard.json", out_dir / "scorecard.md"
    json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_scorecard(data), encoding="utf-8")
    return md_path, json_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", type=Path, help="a dawnr_pipeline.py run directory: the per-stage report.md")
    mode.add_argument("--checkpoint", type=Path,
                      help="one checkpoint: the cross-track scorecard, Markdown and JSON, "
                           "from whichever of the eval files below are given")
    ap.add_argument("--heldout-tag", default=None, help="an existing t/score_heldout.py answer set")
    ap.add_argument("--split", type=Path, default=ROOT / "t" / "out" / "loop" / "split-v5.json")
    ap.add_argument("--eval-json", type=Path, default=None, help="--checkpoint: chat_eval.py's --out FILE")
    ap.add_argument("--eval-rows", type=Path, default=None, help="--checkpoint: chat_eval.py's FILE.rows.jsonl")
    ap.add_argument("--injection-json", type=Path, default=None, help="--checkpoint: injection_eval.py's --out FILE")
    ap.add_argument("--memory-jsonl", type=Path, default=None, help="--checkpoint: schema in memory_metrics.py")
    ap.add_argument("--personalization-jsonl", type=Path, default=None,
                    help="--checkpoint: schema in memory_metrics.py")
    ap.add_argument("--english-json", type=Path, default=None, help="--checkpoint: an earlier --english-shard run")
    ap.add_argument("--english-shard", type=Path, default=None,
                    help="--checkpoint: score this held-out English text file now "
                         "(blank-line documents; not with --english-json)")
    ap.add_argument("--cpu-json", type=Path, default=None, help="--checkpoint: checkpoint_bench.py's --out FILE")
    ap.add_argument("--out", type=Path, default=None,
                    help="--checkpoint: directory for scorecard.md/.json (default: --checkpoint itself)")
    a = ap.parse_args(argv)
    if a.run is not None:
        if a.english_json or a.english_shard or a.eval_rows or a.injection_json or a.memory_jsonl \
                or a.personalization_jsonl or a.cpu_json:
            ap.error("--run builds the per-stage report.md; the scorecard-only options need --checkpoint")
        print(write(a.run, a.heldout_tag, a.split))
        return 0
    if a.english_json and a.english_shard:
        ap.error("--english-json and --english-shard: an existing run or a fresh one, not both")
    out_dir = a.out or a.checkpoint
    english_json = a.english_json
    if a.english_shard is not None:
        english_json = Path(out_dir) / "english_heldout.json"
        english_json.parent.mkdir(parents=True, exist_ok=True)
        english_json.write_text(json.dumps(english_loss_from_shard(a.checkpoint, a.english_shard), indent=2) + "\n",
                                encoding="utf-8")
    md_path, json_path = write_scorecard(
        out_dir, checkpoint=a.checkpoint, eval_json=a.eval_json, eval_rows=a.eval_rows, heldout_tag=a.heldout_tag,
        split=a.split, injection_json=a.injection_json, memory_jsonl=a.memory_jsonl,
        personalization_jsonl=a.personalization_jsonl, english_json=english_json, cpu_json=a.cpu_json)
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
