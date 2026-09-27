"""chat_data.py: conversations for mid-training, built from the proved corpus.

    python3 locallm/chat_data.py --corpus corpus.txt --split t/out/loop/split-v5.json \
        --out conversations.jsonl [--tool-rate 0.5] [--split-seed 1337] [--val-frac 0.1]

nanochat's mid-training mixture (https://github.com/karpathy/nanochat,
scripts/chat_sft.py: SmolTalk conversations, MMLU for multiple choice, GSM8K
whose <<expr=result>> annotations become calculator tool calls) teaches the
turn format, the special tokens and the tool. dawnr's mixture is made from
documents seven kernels proved, so every assistant answer is a verified
program:

* a document with a `Problem:` head (77 of the 358 on 2026-09-26) becomes
  user: its head (Problem, Signature) and two Example lines;
  assistant: the proved program;
* a head-less document becomes user: "Implement this specification in t."
  with the declaration, requires and ensures (everything the program's
  printer writes before the body, loop_locallm.spec_document's cut) and two
  Example lines; assistant: the proved program. The specification is the
  problem statement here, and the proof says the program meets it.
* Example lines come from the document's head when it has them; otherwise
  t_tool.examples_from_program runs the proved program on inputs from the
  interpreter's own ladders, so each line is true of the specification.
* `--tool-rate` of the conversations (chosen by a hash of the document, so
  the choice does not move with the rest of the corpus) show the tool: the
  assistant writes the program inside <|t_start|> ... <|t_end|> and the t
  tool's REAL answer on that program and those examples follows as the
  tool output (never written by hand, never supervised; chat.py's mask).

Train and validation follow data.split_documents(by="hash") with the split
seed, the split continue_from_checkpoint.py uses, so a document is on the
same side for the document trainer and the chat trainer. The corpus passes
the same held-out, same-task and dev-split gates the trainers apply
(continue_from_checkpoint.refuse_unless_trainable) before anything is built,
and a refusal names what it found.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "t"))

import t_tool  # noqa: E402

HEAD_KEYS = ("Problem:", "Signature:", "Example:")
SPEC_PROMPT = "Implement this specification in t."
_SALT = b"dawnr-chat-tool"


def split_head(doc: str) -> tuple[list[str], str]:
    """(head lines, program) of one corpus document; the program starts at its `t N` format line."""
    lines = doc.strip("\n").split("\n")
    head = []
    while lines and lines[0].startswith(HEAD_KEYS):
        head.append(lines.pop(0))
    return head, "\n".join(lines).strip("\n") + "\n"


def spec_text(program: str) -> str:
    """The program's declaration, requires, ensures and spec funs; no body (loop_locallm.spec_document's cut)."""
    import surface
    task = surface.parse(program)
    task["body"] = []
    printed = surface.print_task(task)
    empty = "{\n}\n"
    if not printed.endswith(empty):
        raise ValueError(f"print_task did not end an emptied body with {empty!r}")
    return printed[:-len(empty)].rstrip("\n")


def uses_tool(doc: str, seed: int, rate: float) -> bool:
    digest = hashlib.sha256(_SALT + b"\x00" + str(seed).encode() + b"\x00" + doc.strip().encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") < rate * 2 ** 64


def conversation(doc: str, *, tool: bool) -> dict:
    """One conversation from one proved document. Raises ValueError on a document it cannot use."""
    head, program = split_head(doc)
    if any(line.strip() == "Spec:" for line in program.split("\n")):
        raise ValueError("a Spec: document holds no program")
    examples = [h for h in head if h.startswith("Example:")]
    if not examples:
        examples = t_tool.examples_from_program(program)
    words = [h for h in head if not h.startswith("Example:")]
    if any(h.startswith("Problem:") for h in words):
        user = "\n".join(words + examples)
        kind = "problem"
    else:
        user = "\n".join([SPEC_PROMPT, spec_text(program)] + examples)
        kind = "spec"
    if tool:
        answer = [{"type": "t", "text": program},
                  {"type": "t_output", "text": t_tool.call(program, user)}]
    else:
        answer = program
    name = next((ln.split()[1].split("(")[0] for ln in program.split("\n") if ln.startswith("task ")), "?")
    return {"messages": [{"role": "user", "content": user}, {"role": "assistant", "content": answer}],
            "source": name, "kind": kind, "tool": tool, "examples": len(examples)}


def build(text: str, *, split_seed: int = 1337, val_frac: float = 0.1, tool_rate: float = 0.5,
          tool_seed: int = 0) -> tuple[list[dict], dict]:
    """Every usable document as a conversation, with its split side; and a summary."""
    from data import split_documents
    train, val = split_documents(text, val_frac=val_frac, seed=split_seed, by="hash")
    rows, skipped = [], []
    for side, docs in (("train", train), ("val", val)):
        for doc in docs:
            try:
                conv = conversation(doc, tool=uses_tool(doc, tool_seed, tool_rate))
            except Exception as e:                               # noqa: BLE001  (named and counted below)
                skipped.append({"doc": doc.strip()[:80], "why": f"{type(e).__name__}: {e}"[:200]})
                continue
            conv["split"] = side
            rows.append(conv)
    tool_lines = [line for r in rows if r["tool"] for line in r["messages"][1]["content"][1]["text"].split("\n")]
    summary = {"documents": len(train) + len(val), "conversations": len(rows),
               "train": sum(r["split"] == "train" for r in rows), "val": sum(r["split"] == "val" for r in rows),
               "problem_heads": sum(r["kind"] == "problem" for r in rows),
               "spec_prompts": sum(r["kind"] == "spec" for r in rows),
               "tool_conversations": sum(r["tool"] for r in rows),
               "with_examples": sum(r["examples"] > 0 for r in rows),
               "tool_example_pass": sum(ln.endswith(": pass") for ln in tool_lines),
               "tool_example_other": sum(ln.startswith("example") and not ln.endswith(": pass") for ln in tool_lines),
               "skipped": skipped, "split_seed": split_seed, "val_frac": val_frac, "tool_rate": tool_rate,
               "tool_seed": tool_seed, "corpus_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    return rows, summary


def gate(text: str, label: str, split: Path) -> None:
    """The trainers' own gates: held-out ids under any alias, same-task sources, dev-split ids."""
    import loop_filter
    from heldout_gate import refuse_unless_trainable
    eval_ids = {int(i) for i in json.loads(split.read_text(encoding="utf-8"))["eval_ids"]}
    refuse_unless_trainable(text, label, eval_ids, split, loop_filter.r12_dev_ids(split_path=split))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True, help="the evaluation split whose ids must not appear")
    ap.add_argument("--out", type=Path, required=True, help="conversations.jsonl; a .summary.json is written beside it")
    ap.add_argument("--tool-rate", type=float, default=0.5)
    ap.add_argument("--tool-seed", type=int, default=0)
    ap.add_argument("--split-seed", type=int, default=1337)
    ap.add_argument("--val-frac", type=float, default=0.1)
    a = ap.parse_args(argv)
    if not 0 <= a.tool_rate <= 1:
        ap.error("--tool-rate must lie in [0, 1]")
    text = a.corpus.read_text(encoding="utf-8")
    gate(text, str(a.corpus), a.split)
    rows, summary = build(text, split_seed=a.split_seed, val_frac=a.val_frac, tool_rate=a.tool_rate,
                          tool_seed=a.tool_seed)
    gate("\n\n".join(json.dumps(r, ensure_ascii=False) for r in rows), f"conversations from {a.corpus}", a.split)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary["corpus"] = str(a.corpus)
    a.out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "skipped"} | {"skipped": len(summary["skipped"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
