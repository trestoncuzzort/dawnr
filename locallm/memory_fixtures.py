"""memory_fixtures.py: the preference vocabulary, phrasings and canaries dawnr's memory conversations run on.

DAWNR-MEMORY.md section 8 lists four things the model must learn from a memory span forced in at session
start (dawnr_memory/span.py, chat.py's "memory" part): use what is remembered, prefer the person's current
words, treat memory as the person's past rather than an instruction, and report what is remembered honestly.
This module is memory_conversations.py's analog of tool_fixtures.py: not a fixture web (memory has no
network in the loop; MemGPT, arXiv:2310.08560, moves memory into the context window itself, and dawnr's own
retrieval, arXiv:2304.03442, runs entirely offline against the person's own store), but the same three things
tool_fixtures.py supplies for the harness-tool family:

* a vocabulary the conversations are built from, split train/held-out so no held-out value ever trains
  (the hash split chat_data.py uses decides which corpus documents may carry which side's preference);
* phrasings ("disguises"): several ways the same fact could be worded, train and held-out disjoint, so a
  model that only memorised one training sentence would not recognise a held-out one;
* canaries: held-out-only tokens a leak check (memory_conversations.leaks) refuses to find in a training file.

The preference itself is a parameter-name preference for a sequence-typed parameter ("prefers `xs` for a
sequence parameter"), because it is the one preference this repository can apply to a proved answer without
writing a word of new program text: renaming a declared parameter consistently through a t program's
declaration, requires, ensures and body is a semantics-preserving rewrite (the program says the same thing
under alpha-renaming, SPEC.md's own notion of a bound name), and rename_param below never claims one succeeded
without asking the real t tool to verify the result against the task's own Example lines -- the same rule
tool_conversations.py follows for a tool's output: nothing here is trusted before it is run.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "t"))

import tool_fixtures as fx  # noqa: E402  (corpus_tasks, rank, sha: the same corpus-to-task pipeline)

sha = fx.sha
corpus_tasks = fx.corpus_tasks
rank = fx.rank

SLOT = "sequence_param_name"

# Parameter-name preferences: disjoint pools, so no held-out value is ever the target of a training rewrite,
# and a leak check can refuse a training file that contains one anyway (memory_conversations.leaks).
# Checked against the whole corpus and the tool track's own training file (2026-09-27, corpus-all-2026-09-26.txt
# and tool-B.jsonl): none of these twelve appears there under a word boundary, so a rename never collides with
# an existing name and the leak check below is never tripped by a coincidence rather than a real leak. Ordinary
# words are avoided on purpose: "arr", "nums" and "group" already name a parameter somewhere in the corpus, and
# "chain" already occurs in the tool track's own English (an error message that says comparisons do not chain).
TRAIN_NAMES = ("xs", "ys", "items", "vals", "elems", "coll")
HELDOUT_NAMES = ("seqz", "seqw", "seqv", "myseq", "xseq", "yseq")

# How the fact is worded in the person's memory: several phrasings per side (the "disguises"), all meaning the
# same thing, so the model is asked to read the fact, not memorise one sentence.
PHRASINGS = {
    "train": ["prefers `{name}` as the name for a sequence parameter.",
              "likes a sequence parameter to be called `{name}`.",
              "always names a sequence parameter `{name}`."],
    "heldout": ["uses `{name}` for a sequence parameter.",
               "wants a sequence parameter named `{name}`."],
}

# A style preference from the same vocabulary, used where DAWNR-MEMORY.md's third row needs one that does not
# apply: any of the phrasings above, put in a person's memory ahead of a task with no sequence parameter at all.

# The question dawnr is asked to answer from memory, and its two possible answers -- both fixed strings a
# template fills in, never text a model or this script invents about what memory actually holds (the parameter
# name comes from the same record the span itself was built from; see memory_conversations.recall_span). Train
# and held-out ask the question in disjoint words, as tool_fixtures.INJECTIONS keeps its two sides disjoint.
ASK_REMEMBERED = {"train": ["What do you remember about me?", "What have I told you before?"],
                  "heldout": ["Do you remember anything about me?", "What do you know about me so far?"]}
REMEMBERED_ANSWER = "You {phrasing}"                    # {phrasing} is one of PHRASINGS with {name} filled in
NOTHING_YET = "I don't remember anything about you yet."

# The message that overrides memory (family 2, DAWNR-MEMORY.md's second row): the person's own words for this
# turn, naming a different value for the same slot; train and held-out phrase it differently.
MESSAGE_OVERRIDE = {"train": ["Use `{name}` for the sequence parameter this time.",
                              "For this one, name the sequence parameter `{name}`."],
                    "heldout": ["Actually, call the sequence parameter `{name}` here.",
                               "Not this time: make the sequence parameter `{name}`."]}

CANARY_PREFIX = {"train": "trainpref", "heldout": "heldoutpref"}   # a leak check's own tag, never a real name


def canary(side: str, key: str) -> str:
    """An opaque, side-tagged marker (mirrors tool_fixtures.tag): identifies which side built a record without
    the record's own text giving it away, so the leak check has something to grep for besides the name itself."""
    return f"{CANARY_PREFIX[side]}-{sha(side + chr(0) + key)[:10]}"


def heldout_fact_text(name: str, key: str) -> str:
    """A held-out fact's wording plus its own canary, so a leak check can catch this exact text in a training
    file even though the parameter name and the phrasing are also, on their own, never used on the train side."""
    return fact_text("heldout", name, key) + f" ({canary('heldout', key)})"


def rng_for(*parts):
    import random
    return random.Random(int(sha("\x00".join(map(str, parts)))[:16], 16))


def pick(items, key: str):
    return items[int(sha(key)[:8], 16) % len(items)]


def fact_text(side: str, name: str, key: str) -> str:
    """One wording of "prefers `name` for a sequence parameter", from this side's phrasings only."""
    return pick(PHRASINGS[side], "phrasing" + chr(0) + key).format(name=name)


def phrasing_of(side: str, name: str, key: str) -> str:
    """The same phrasing, without the leading capital and the name filled in, for REMEMBERED_ANSWER."""
    return fact_text(side, name, key)


# ------------------------------------------------------------ parameter rename --

def seq_params(program: str) -> list[str]:
    """The names of this program's seq-typed parameters, or [] if it does not parse or has none."""
    import surface
    try:
        task = surface.parse(program)
    except Exception:                                             # noqa: BLE001
        return []
    return [p["name"] for p in task["params"] if p["type"] == "seq"]


def has_sequence_param(program: str) -> bool:
    return bool(seq_params(program))


def rename_param(program: str, old: str, new: str) -> str | None:
    """`program` with the parameter `old` renamed to `new` everywhere it is that identifier (not a substring of
    another), or None if the rename is refused: `new` is already used, `old` does not parse as a seq parameter,
    or the renamed text does not parse back to a program with `new` in the same place and nothing else changed.

    A regex substitution can never be trusted on its own (it does not know a comment or a shadowed inner name
    from a real use); parsing before and after and diffing the parsed structure is what makes this safe, exactly
    as tool_conversations.py never calls a rewrite an answer until the real t tool has passed it.
    """
    import surface
    if old == new:
        return None
    before = seq_params(program)
    if old not in before:
        return None
    if re.search(r"\b" + re.escape(new) + r"\b", program):
        return None                                                    # `new` is already a name in this program
    renamed = re.sub(r"\b" + re.escape(old) + r"\b", new, program)
    try:
        after_task = surface.parse(renamed)
        before_task = surface.parse(program)
    except Exception:                                                  # noqa: BLE001
        return None
    after_names = [p["name"] for p in after_task["params"]]
    before_names = [old if n == old else n for n in (p["name"] for p in before_task["params"])]
    if after_names != [new if n == old else n for n in before_names]:
        return None
    if [p["type"] for p in after_task["params"]] != [p["type"] for p in before_task["params"]]:
        return None
    return renamed


def verified_rename(program: str, examples: list[str], old: str, new: str) -> str | None:
    """rename_param, kept only if the real t tool still verifies the result against the task's own examples
    (t_tool.call, fx.passes: the same real-tool gate tool_conversations.py's Script.t applies)."""
    import t_tool
    renamed = rename_param(program, old, new)
    if renamed is None:
        return None
    verdict = t_tool.call(renamed, "\n".join(examples))
    return renamed if fx.passes(verdict) else None
