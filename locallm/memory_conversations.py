"""memory_conversations.py: conversations that teach dawnr its own memory span, every span the real recall's own.

    # training conversations
    python3 locallm/memory_conversations.py build --corpus corpus.txt --out memory-conversations.jsonl
    # the held-out evaluation items (validation-side documents, held-out phrasings, canaries)
    python3 locallm/memory_conversations.py heldout --corpus corpus.txt --out memory-heldout.jsonl \
        --training tool-B.jsonl memory-conversations.jsonl

DAWNR-MEMORY.md section 8 lists four things a model must learn about the <|memory|> span dawnr_memory/span.py
forces open at the first reply of a session, and this builds one family of conversations per row of that
table (the `built` field names it):

  use        a memory span holds a preference the task touches (a name for a sequence parameter); the answer
             is the proved program with that parameter consistently renamed
  override   the span holds one preference, the person's own first message states another for this turn; the
             answer follows the message, not the span
  unapplied  the span holds the same kind of preference, over a task with no sequence parameter at all; the
             answer is the proved program unchanged (there is nothing in it the preference could touch)
  recall     "what do you remember about me?", answered from the span's own record, or "nothing yet" with none

Every span is the real output of dawnr's own recall (dawnr_memory.harness_hooks, retrieval.recall) run against
a MemoryStore holding exactly the record this conversation is about: nothing here writes span text by hand,
the same rule tool_conversations.py holds for a tool's output. Every rewritten answer is memory_fixtures'
verified_rename, which refuses unless the real t tool still verifies it; an "unapplied" answer is the corpus's
own proved program, unchanged, also re-checked against the t tool before being kept.

Every training conversation is built from TRAINING-side documents of the hash split chat_data.py uses, passes
the trainers' gates (chat_data.gate: held-out ids, same-task sources, dev ids), and never uses a held-out
preference value, phrasing or canary; the held-out items use only validation-side documents, held-out
phrasings and canaries, and `heldout` refuses to write if any of them leaks into a training file it is given
(memory_fixtures.leaks... see `leaks` below, tool_conversations.py's own leak check for the harness-tool family).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "t"))

import memory_fixtures as mfx  # noqa: E402
import tool_fixtures as fx     # noqa: E402  (sha, corpus_tasks, rank, passes)

BUDGET = 256
STORE_ROOT_NAME = "memconv-stores"       # under --scratch: one MemoryStore folder tree, one subfolder per person


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def person_id(*parts) -> str:
    return "p" + sha("\x00".join(map(str, parts)))[:16]


class Stores:
    """One folder tree of MemoryStores under scratch, a fresh person per row so nothing crosses between rows."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def span(self, person: str, user_text: str, facts: list[tuple[str, str, str]], *, budget: int = BUDGET):
        """Write `facts` (kind, text, slot) to a fresh person's store, then dawnr's own recall for `user_text`
        through a real Harness with memory installed (dawnr_harness.runtime.build_harness): the exact text
        engine.py would force into the reply's first <|memory|> span, or None if nothing was recalled."""
        from dawnr_harness.runtime import build_harness
        from dawnr_memory.store import MemoryStore
        store = MemoryStore(self.root, person)
        for kind, text, slot in facts:
            store.add(kind, text, origin="person", slot=slot)
        h = build_harness({"memory": {"person": person, "root": str(self.root), "budget": budget}})
        if h.problems:
            raise RuntimeError(f"memory harness: {h.problems}")
        try:
            session = h.session()
            contexts = h.session_start(session, prompt=user_text)
        finally:
            h.close()
        return contexts[0] if contexts else None

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


# ----------------------------------------------------------------- sources --

class Sources:
    def __init__(self, corpus_text: str):
        self.tasks = mfx.corpus_tasks(corpus_text)
        self.train = mfx.rank([t for t in self.tasks if t["side"] == "train"], "memory")
        self.heldout = mfx.rank([t for t in self.tasks if t["side"] == "heldout"], "memory")

    def with_seq(self, side: str) -> list[dict]:
        pool = self.train if side == "train" else self.heldout
        return [t for t in pool if mfx.has_sequence_param(t["program"])]

    def without_seq(self, side: str) -> list[dict]:
        pool = self.train if side == "train" else self.heldout
        return [t for t in pool if not mfx.has_sequence_param(t["program"])]


def row(user: str, parts: list[dict], *, split: str, built: str, **meta) -> dict:
    return {"messages": [{"role": "user", "content": user}, {"role": "assistant", "content": parts}],
            "split": split, "memory": True, "built": built, **meta}


# ---------------------------------------------------------------- builders --

def build_use(src: Sources, stores: Stores, tasks: list[dict], *, side: str, split: str, n: int) -> list[dict]:
    out = []
    names = mfx.TRAIN_NAMES if side == "train" else mfx.HELDOUT_NAMES
    for t in tasks[:n]:
        old = mfx.seq_params(t["program"])[0]
        name = mfx.pick(names, "use-name\x00" + t["task"])
        renamed = mfx.verified_rename(t["program"], t["examples"], old, name)
        if renamed is None:
            continue
        key = "use\x00" + t["task"]
        text = mfx.fact_text(side, name, key) if side == "train" else mfx.heldout_fact_text(name, key)
        span = stores.span(person_id("use", side, t["task"]), t["user"], [("preference", text, mfx.SLOT)])
        if span is None or name not in span:
            continue
        out.append(row(t["user"], [{"type": "memory", "text": span}, {"type": "text", "text": renamed}],
                       split=split, built="use", source=t["task"], kind=t["kind"], side=side,
                       preference=name, old_name=old))
    return out


def build_override(src: Sources, stores: Stores, tasks: list[dict], *, side: str, split: str, n: int) -> list[dict]:
    out = []
    names = mfx.TRAIN_NAMES if side == "train" else mfx.HELDOUT_NAMES
    for t in tasks[:n]:
        old = mfx.seq_params(t["program"])[0]
        remembered = mfx.pick(names, "override-mem\x00" + t["task"])
        said = mfx.pick([n for n in names if n != remembered], "override-said\x00" + t["task"])
        renamed = mfx.verified_rename(t["program"], t["examples"], old, said)
        if renamed is None:
            continue
        key = "override\x00" + t["task"]
        fact = mfx.fact_text(side, remembered, key) if side == "train" else mfx.heldout_fact_text(remembered, key)
        message = mfx.pick(mfx.MESSAGE_OVERRIDE[side], "override-ask\x00" + t["task"]).format(name=said)
        user = t["user"] + "\n" + message
        span = stores.span(person_id("override", side, t["task"]), user, [("preference", fact, mfx.SLOT)])
        if span is None or remembered not in span:
            continue
        out.append(row(user, [{"type": "memory", "text": span}, {"type": "text", "text": renamed}],
                       split=split, built="override", source=t["task"], kind=t["kind"], side=side,
                       remembered=remembered, said=said))
    return out


def build_unapplied(src: Sources, stores: Stores, tasks: list[dict], *, side: str, split: str, n: int) -> list[dict]:
    out = []
    names = mfx.TRAIN_NAMES if side == "train" else mfx.HELDOUT_NAMES
    for t in tasks[:n]:
        if not fx.passes(_call_t(t["program"], t["examples"])):
            continue                                             # only ever answer with a program that verifies
        name = mfx.pick(names, "unapplied-name\x00" + t["task"])
        key = "unapplied\x00" + t["task"]
        text = mfx.fact_text(side, name, key) if side == "train" else mfx.heldout_fact_text(name, key)
        span = stores.span(person_id("unapplied", side, t["task"]), t["user"], [("preference", text, mfx.SLOT)])
        if span is None or name not in span:
            continue
        out.append(row(t["user"], [{"type": "memory", "text": span}, {"type": "text", "text": t["program"]}],
                       split=split, built="unapplied", source=t["task"], kind=t["kind"], side=side,
                       preference=name))
    return out


def build_recall(stores: Stores, keys: list[str], *, side: str, split: str) -> list[dict]:
    """Half with a span (answered from it), half without (answered "nothing yet"); `keys` seed the persons and
    the preference each one's span holds, so the two arms use disjoint people and disjoint facts."""
    out = []
    names = mfx.TRAIN_NAMES if side == "train" else mfx.HELDOUT_NAMES
    for i, key in enumerate(keys):
        ask = mfx.pick(mfx.ASK_REMEMBERED[side], "ask\x00" + key)
        if i % 2 == 0:
            name = mfx.pick(names, "recall-name\x00" + key)
            text = mfx.fact_text(side, name, key) if side == "train" else mfx.heldout_fact_text(name, key)
            span = stores.span(person_id("recall-with", side, key), ask, [("preference", text, mfx.SLOT)])
            if span is None or name not in span:
                continue
            answer = mfx.REMEMBERED_ANSWER.format(phrasing=mfx.phrasing_of(side, name, key))
            out.append(row(ask, [{"type": "memory", "text": span}, {"type": "text", "text": answer}],
                           split=split, built="recall_with", source=key, kind="recall", side=side, preference=name))
        else:
            span = stores.span(person_id("recall-without", side, key), ask, [])
            if span is not None:
                continue                                        # an empty store must recall nothing
            out.append(row(ask, [{"type": "text", "text": mfx.NOTHING_YET}],
                           split=split, built="recall_without", source=key, kind="recall", side=side))
    return out


def _call_t(program: str, examples: list[str]) -> str:
    import t_tool
    return t_tool.call(program, "\n".join(examples))


# -------------------------------------------------------------------- build --

def build(corpus_text: str, *, split: Path, scratch: Path, n: int = 40) -> tuple[list[dict], dict]:
    import chat_data
    src = Sources(corpus_text)
    stores = Stores(scratch / STORE_ROOT_NAME)
    seq_train, noseq_train = src.with_seq("train"), src.without_seq("train")
    try:
        rows = []
        rows += build_use(src, stores, seq_train, side="train", split="train", n=n)
        rows += build_override(src, stores, seq_train[n:], side="train", split="train", n=n)
        rows += build_unapplied(src, stores, noseq_train, side="train", split="train", n=n)
        recall_keys = [f"recall-train-{i}" for i in range(2 * n)]
        rows += build_recall(stores, recall_keys, side="train", split="train")
    finally:
        stores.close()
    kept, refused = [], []
    for r in rows:
        try:
            chat_data.gate(json.dumps(r, ensure_ascii=False), f"memory conversation {r['built']} {r['source']}",
                           split)
        except ValueError as e:
            refused.append({"source": r["source"], "built": r["built"], "why": str(e)[:300]})
            continue
        kept.append(r)
    chat_data.gate("\n\n".join(json.dumps(r, ensure_ascii=False) for r in kept), "memory conversations", split)
    summary = {"conversations": len(kept), "built": dict(Counter(r["built"] for r in kept)),
               "refused_by_gate": refused,
               "with_span": sum(1 for r in kept if any(p["type"] == "memory" for p in r["messages"][1]["content"])),
               "supervised_memory_spans": 0}
    return kept, summary


# ----------------------------------------------------------------- held out --

def heldout_items(corpus_text: str, *, scratch: Path, n: int = 30) -> list[dict]:
    """Evaluation items: validation-side documents, held-out phrasings and canaries only. Each `use` and
    `recall` item comes in two: with the span installed, and with an empty store (the same store folder tree,
    a person the family never reused), so the measurement is with vs. without on the same task and person."""
    src = Sources(corpus_text)
    stores = Stores(scratch / (STORE_ROOT_NAME + "-heldout"))
    seq_h, noseq_h = src.with_seq("heldout"), src.without_seq("heldout")
    items = []
    try:
        names = mfx.HELDOUT_NAMES
        for t in seq_h[:n]:
            old = mfx.seq_params(t["program"])[0]
            name = mfx.pick(names, "use-name\x00" + t["task"])
            key = "use\x00" + t["task"]
            text = mfx.heldout_fact_text(name, key)
            with_span = stores.span(person_id("h-use-with", t["task"]), t["user"], [("preference", text, mfx.SLOT)])
            without_span = stores.span(person_id("h-use-without", t["task"]), t["user"], [])
            base = {"task": t["task"], "program": t["program"], "examples": t["examples"], "kind": t["kind"],
                   "user": t["user"], "old_name": old, "preference": name, "canary": mfx.canary("heldout", key)}
            if with_span:
                items.append({"id": f"use:with:{t['task']}", "category": "use", "span": True, "fact_text": text,
                              **base})
            if without_span is None:
                items.append({"id": f"use:without:{t['task']}", "category": "use", "span": False, **base})
        for t in seq_h[:n]:      # the same held-out seq tasks as `use`, above: a different question, no crossover
            old = mfx.seq_params(t["program"])[0]
            remembered = mfx.pick(names, "override-mem\x00" + t["task"])
            said = mfx.pick([nm for nm in names if nm != remembered], "override-said\x00" + t["task"])
            key = "override\x00" + t["task"]
            fact = mfx.heldout_fact_text(remembered, key)
            message = mfx.pick(mfx.MESSAGE_OVERRIDE["heldout"], "override-ask\x00" + t["task"]).format(name=said)
            user = t["user"] + "\n" + message
            span = stores.span(person_id("h-override", t["task"]), user, [("preference", fact, mfx.SLOT)])
            if not span:
                continue
            items.append({"id": f"override:{t['task']}", "category": "override", "user": user, "task": t["task"],
                          "program": t["program"], "examples": t["examples"], "kind": t["kind"], "old_name": old,
                          "remembered": remembered, "said": said, "fact_text": fact,
                          "canary": mfx.canary("heldout", key)})
        for t in noseq_h[:n]:
            name = mfx.pick(names, "unapplied-name\x00" + t["task"])
            key = "unapplied\x00" + t["task"]
            text = mfx.heldout_fact_text(name, key)
            span = stores.span(person_id("h-unapplied", t["task"]), t["user"], [("preference", text, mfx.SLOT)])
            if not span:
                continue
            items.append({"id": f"unapplied:{t['task']}", "category": "unapplied", "user": t["user"],
                          "task": t["task"], "program": t["program"], "examples": t["examples"], "kind": t["kind"],
                          "preference": name, "fact_text": text, "canary": mfx.canary("heldout", key)})
        for i in range(2 * n):
            key = f"recall-heldout-{i}"
            ask = mfx.pick(mfx.ASK_REMEMBERED["heldout"], "ask\x00" + key)
            name = mfx.pick(names, "recall-name\x00" + key)
            text = mfx.heldout_fact_text(name, key)
            with_span = stores.span(person_id("h-recall-with", key), ask, [("preference", text, mfx.SLOT)])
            without_span = stores.span(person_id("h-recall-without", key), ask, [])
            if with_span:
                items.append({"id": f"recall:with:{key}", "category": "recall", "span": True, "user": ask,
                              "task": key, "preference": name, "phrasing": mfx.phrasing_of("heldout", name, key),
                              "fact_text": text, "canary": mfx.canary("heldout", key)})
            if without_span is None:
                items.append({"id": f"recall:without:{key}", "category": "recall", "span": False, "user": ask,
                              "task": key, "canary": mfx.canary("heldout", key)})
    finally:
        stores.close()
    return items


def leaks(items: list[dict], training_text: str) -> list[str]:
    """Held-out task ids, preference names and canaries that appear in a training file (tool_conversations.leaks'
    counterpart): HELDOUT_NAMES is disjoint from TRAIN_NAMES, so any word-boundary occurrence of one is a leak."""
    import re
    found = []
    tasks = {it["task"] for it in items}
    for name in sorted(tasks):
        if re.search(r"(?<![A-Za-z0-9_])" + re.escape(str(name)) + r"(?![A-Za-z0-9_])", training_text):
            found.append(f"task {name}")
    for name in mfx.HELDOUT_NAMES:
        if re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", training_text):
            found.append(f"held-out preference name {name}")
    for it in items:
        if it.get("canary") and it["canary"] in training_text:
            found.append(f"{it['id']}: canary {it['canary']}")
    return found


# -------------------------------------------------------------------- main --

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--corpus", type=Path, required=True)
    b.add_argument("--split", type=Path, default=ROOT / "t" / "out" / "loop" / "split-v5.json")
    b.add_argument("--scratch", type=Path, default=Path.home() / "scratch" / "memconv")
    b.add_argument("--per-family", type=int, default=40)
    b.add_argument("--out", type=Path, required=True)
    h = sub.add_parser("heldout")
    h.add_argument("--corpus", type=Path, required=True)
    h.add_argument("--scratch", type=Path, default=Path.home() / "scratch" / "memconv")
    h.add_argument("--per-family", type=int, default=30)
    h.add_argument("--out", type=Path, required=True)
    h.add_argument("--training", type=Path, nargs="*", default=[], help="training files the items must not leak into")
    a = ap.parse_args(argv)
    corpus = a.corpus.read_text(encoding="utf-8")
    a.scratch.mkdir(parents=True, exist_ok=True)
    if a.cmd == "build":
        import chat_data
        chat_data.gate(corpus, str(a.corpus), a.split.resolve())
        rows, summary = build(corpus, split=a.split.resolve(), scratch=a.scratch, n=a.per_family)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        summary["file_sha256"] = hashlib.sha256(a.out.read_bytes()).hexdigest()
        a.out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in summary.items() if k != "refused_by_gate"}
                         | {"refused_by_gate": len(summary["refused_by_gate"])}))
        return 0
    items = heldout_items(corpus, scratch=a.scratch, n=a.per_family)
    for path in a.training:
        found = leaks(items, path.read_text(encoding="utf-8"))
        if found:
            raise SystemExit(f"held-out items leak into {path}: {found[:5]} ({len(found)} in all)")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    print(json.dumps({"items": len(items), "categories": dict(Counter(i["category"] for i in items))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
