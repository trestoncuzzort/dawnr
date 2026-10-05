"""assistant_rows.py: the conversations dawnr_teach.py kept, as rows a model is trained on (2026-10-05).

    python3 locallm/assistant_rows.py --rows teach.jsonl --model Qwen/Qwen3.5-4B --out sft-assistant.jsonl

A kept conversation is what the larger model saw and wrote over one task. Two things are done to it before it
teaches anything.

**What was sent back is taken out.** The front door corrects a driver as it goes: a plan that would lose a file's
contents goes back with that said, an answer about code that was never run is sent back to run it, an answer the
journal contradicts is asked for again. In a kept conversation each of those is a wrong turn, the correction, and
then the right turn. A smaller model trained on all three learns to make the wrong turn first. So the wrong turn
and its correction are removed and the right turn stands where the wrong one stood: the conversation a driver
would have had if it had needed no correcting. Nothing is invented by this: every remaining call was really made
and every result really came back. (A call that a tool itself refused or that failed stays, with what it was
told: that is how a refusal is learned.)

**It is rendered the way the server will render it.** A row is the text of the whole conversation in the model's
own chat template with the tools, cut into pieces that are either context or something the model wrote, so that
the loss falls only on what it wrote (t/student_sft.py: "only training on the target is beneficial", QLoRA
appendix B.3, arXiv:2305.14314). The template renders an assistant turn inside a task as
`<|im_start|>assistant\\n<think>\\n\\n</think>\\n\\n` and then the turn, which is exactly the generation prompt with
thinking off followed by what is generated, so one pass over the conversation trains every turn in the context
the server would give it. That is checked row by row (the prompt for turn k must be a prefix of the whole text and
the turn must follow it); a row where it does not hold is cut into one row a turn instead. The first call of a
task, the folder's listing, is the front door's own and is context, never a target.

The output: JSON lines {"id", "family", "pieces": [[text, trained?], ...]}, read by `t/student_sft.py --sft`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# how a correction of the front door's begins, where it stands in a result's place and where it is a turn of its own
SENT_BACK = "[From dawnr itself, not output of the call:]"
NUDGES = ("You have not looked yet.", "Your reply was cut off at its length limit.", "You changed ", "The journal of what this task changed says")


def calls_of(message: dict) -> list:
    return [(c["function"]["name"], c["function"]["arguments"]) for c in message.get("tool_calls") or []]


def clean(messages: list) -> list:
    """The conversation without the turns that were sent back and without the sending back."""
    out: list = []
    i = 0
    while i < len(messages):
        m = messages[i]
        nxt = messages[i + 1] if i + 1 < len(messages) else None
        if m["role"] == "assistant" and nxt is not None:
            # an answer (or a fragment) followed by the front door's own words: both go, the next turn stands
            if not m.get("tool_calls") and nxt["role"] == "user" and str(nxt.get("content") or "").startswith(NUDGES):
                i += 2
                continue
            # one call, answered by the front door instead of run, and then another turn: the call and the answer go
            if (len(m.get("tool_calls") or []) == 1 and nxt["role"] == "tool" and str(nxt.get("content") or "").startswith(SENT_BACK)
                    and i + 2 < len(messages) and messages[i + 2]["role"] == "assistant"):
                i += 2
                continue
        out.append(m)
        i += 1
    return out


def for_template(messages: list) -> list:
    """The messages as a chat template takes them: a call's arguments as a mapping, not as the JSON text of one."""
    out = []
    for m in messages:
        m = dict(m)
        if m.get("tool_calls"):
            m["tool_calls"] = [{"type": "function", "function": {"name": c["function"]["name"],
                                                                 "arguments": json.loads(c["function"]["arguments"]) if isinstance(c["function"]["arguments"], str) else c["function"]["arguments"]}}
                               for c in m["tool_calls"]]
        out.append(m)
    return out


def pieces(messages: list, tools: list, render) -> list:
    """[[[text, trained?], ...], ...]: one list of pieces when the whole conversation is one consistent text (the
    usual case), else one list a turn. `render(messages, generate)` is the chat template with the tools."""
    messages = for_template(messages)
    turns = [k for k, m in enumerate(messages) if m["role"] == "assistant"]
    own = lambda k: not (k == turns[0] and calls_of(messages[k])[:1] and calls_of(messages[k])[0][0] == "fs_list" and len(messages[k]["tool_calls"]) == 1
                         and messages[k - 1]["role"] == "user")     # the listing the front door makes itself
    spans = []
    for k in turns:
        prompt, upto = render(messages[:k], True), render(messages[:k + 1], False)
        if not upto.startswith(prompt):
            raise ValueError(f"turn {k} does not follow its own generation prompt in this template")
        spans.append((prompt, upto[len(prompt):].rstrip("\n"), own(k)))
    whole = render(messages, False)
    at, one = 0, []
    for prompt, target, trained in spans:                       # is every turn's prompt where the whole text says it is?
        if not whole.startswith(prompt + target, 0) or len(prompt) < at:
            one = None
            break
        one += [[whole[at:len(prompt)], False], [target, trained]]
        at = len(prompt) + len(target)
    if one is not None:
        return [[p for p in one if p[0]]] if any(t for _x, t in one) else []
    return [[[prompt, False], [target, True]] for prompt, target, trained in spans if trained]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rows", type=Path, required=True, action="append",
                    help="what dawnr_teach.py kept; given more than once (several teachers), a task that more than one did is "
                         "taken from the one that needed fewer model calls, then fewer tokens")
    ap.add_argument("--model", required=True, help="the student's hub id or folder: its tokenizer holds the chat template")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--per-family", type=int, default=0, help="at most this many rows of one family (0: all)")
    a = ap.parse_args(argv)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(a.model)
    kept = split = cleaned = 0
    seen: dict = {}
    best: dict = {}
    for path in a.rows:                                         # the shorter way through a task is the one to learn
        for line in path.read_text().splitlines():
            row = json.loads(line)
            have = best.get(row["id"])
            if have is None or (row.get("calls", 0), row.get("written", 0)) < (have.get("calls", 0), have.get("written", 0)):
                best[row["id"]] = row
    order = lambda row: (row["family"], int(row["id"].rsplit(":", 1)[-1]) if row["id"].rsplit(":", 1)[-1].isdigit() else 0)
    by: dict = {}
    with open(a.out, "w") as out:
        for row in sorted(best.values(), key=order):
            if a.per_family and seen.get(row["family"], 0) >= a.per_family:
                continue
            messages = clean(row["messages"])
            cleaned += len(messages) != len(row["messages"])
            render = lambda ms, generate, tools=row["tools"]: tokenizer.apply_chat_template(ms, tools=tools, tokenize=False, add_generation_prompt=generate, enable_thinking=False)
            units = pieces(messages, row["tools"], render)
            split += len(units) > 1
            for n, unit in enumerate(units):
                out.write(json.dumps({"id": row["id"] + (f"#{n}" if len(units) > 1 else ""), "family": row["family"],
                                      "teacher": row.get("teacher", ""), "pieces": unit}) + "\n")
            kept += bool(units)
            seen[row["family"]] = seen.get(row["family"], 0) + bool(units)
            by[row.get("teacher", "")] = by.get(row.get("teacher", ""), 0) + bool(units)
    print(f"{kept} conversations written ({cleaned} had turns that were sent back taken out; {split} cut into a row a turn), {len(seen)} families"
          + ("; by teacher: " + ", ".join(f"{k or 'unnamed'} {v}" for k, v in sorted(by.items())) if len(by) > 1 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
