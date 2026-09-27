"""dawnr_report.py: one pipeline run's report card, report.md, from what its stages wrote.

    python3 locallm/dawnr_report.py --run <pipeline out dir> [--heldout-tag TAG]

nanochat's first release gathered every stage's numbers into one report.md
(https://github.com/karpathy/nanochat, nanochat/report.py); it was deleted
upstream on 2026-07-02 (commit f10bd751, "it just bloats the code"), because
every script had to call into it. This one only READS: each stage's
stage.json (its inputs by hash, its result, its time) and the eval stage's
eval.json, so no stage knows the report exists and a report can be rebuilt
from a finished run at any time.

dawnr's numbers, not nanochat's: characters per token; held-out loss on the
validation-side documents no stage trains on; the mid stage's loss on the
assistant's tokens; the dev problems' reward tiers from t/rl_reward.py (none,
parses, typed, tests; proved needs Dafny and is marked not asked); the t tool's
verdicts on validation conversations. The clean-200 score appears only for an
answer set that already exists (`--heldout-tag`, scored by t/score_heldout.py);
the report never generates on the held-out problems.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--heldout-tag", default=None)
    ap.add_argument("--split", type=Path, default=ROOT / "t" / "out" / "loop" / "split-v5.json")
    a = ap.parse_args(argv)
    print(write(a.run, a.heldout_tag, a.split))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
