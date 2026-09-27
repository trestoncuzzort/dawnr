"""harness_hooks.py: dawnr's memory in the harness, as two builtin hooks on the session events.

memory_recall runs at SessionStart, when the person's first message of a conversation arrives: it opens the
person's store, recalls within the budget (retrieval.recall, UTF-8 bytes as the counter, since a hook does not know
the model's tokenizer) and returns the text as additionalContext; the engine renders it as the reply's opening
<|output_start|><|memory|> ... <|output_end|> span, counted again with the model's tokenizer (span.py).
memory_extract runs at SessionEnd with the transcript: extraction, the gate, the update (extract.end_session);
what it did is a systemMessage, for the person and never for the model.

The contract is Claude Code's (code.claude.com/docs/en/hooks, read 2026-09-27): SessionStart's matcher is how the
session started, it may add additionalContext and cannot block; SessionEnd's matcher is why it ended and it has
no decision control, only side effects. So an operator can replace, reorder or add to these two with their own
command hooks, which receive the same JSON (the person's id and the memory folder included) on stdin.

Configuration, in the harness's JSON (DAWNR-MEMORY.md section 6):

    "memory": {"person": "ann", "root": "path/to/memory", "budget": 256, "half_life_days": 30}

every key optional: the person defaults to "default", the root to the app's data folder (store.memory_root), the
budget to 256 tokens. With no "memory" key nothing is recalled and nothing is written, as before.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dawnr_harness import hooks
from dawnr_harness.hooks import Handler

from .extract import end_session
from .retrieval import HALF_LIFE_DAYS, recall
from .store import MemoryStore, memory_root, normalize_person

DEFAULT_BUDGET = 256
CONFIG_KEYS = {"person", "root", "budget", "half_life_days"}
HOOKS = (("SessionStart", "memory_recall"), ("SessionEnd", "memory_extract"))


@dataclass
class MemoryConfig:
    root: Path
    person: str = "default"
    budget: int = DEFAULT_BUDGET
    half_life_days: float = HALF_LIFE_DAYS

    def payload(self) -> dict:
        """What the session hooks receive about memory, alongside the event's own fields."""
        return {"person": self.person, "memory": {"root": str(self.root), "budget": self.budget,
                                                  "half_life_days": self.half_life_days}}


def parse_config(spec, base: str | Path | None = None) -> MemoryConfig:
    """The operator's "memory" object, checked; relative roots resolve from the configuration file's folder."""
    if spec is True:
        spec = {}
    if not isinstance(spec, dict):
        raise ValueError('"memory" is an object such as {"person": "ann", "budget": 256}, or true')
    unknown = set(spec) - CONFIG_KEYS
    if unknown:
        raise ValueError(f"unknown memory keys: {', '.join(sorted(unknown))} (known: {', '.join(sorted(CONFIG_KEYS))})")
    person = normalize_person(spec.get("person", "default"))
    root = spec.get("root")
    if root is None:
        path = memory_root()
    else:
        path = Path(str(root)).expanduser()
        if not path.is_absolute():
            path = Path(base or Path.cwd()) / path
    try:
        budget = int(spec.get("budget", DEFAULT_BUDGET))
        half_life = float(spec.get("half_life_days", HALF_LIFE_DAYS))
    except (TypeError, ValueError):
        raise ValueError('"budget" is a whole number of tokens and "half_life_days" a number of days') from None
    if budget < 0 or not half_life > 0:
        raise ValueError('"budget" must be at least 0 and "half_life_days" above 0')
    return MemoryConfig(path, person, budget, half_life)


def install(harness, spec, base: str | Path | None = None) -> MemoryConfig:
    """Turn memory on for a harness: its settings on harness.memory, and memory_recall and memory_extract added
    to the session events unless the operator's own hooks already place them."""
    config = parse_config(spec, base)
    harness.memory = config
    for event, name in HOOKS:
        groups = harness.hooks.groups.setdefault(event, [])
        if not any(h.type == "builtin" and h.name == name for _matcher, handlers in groups for h in handlers):
            groups.append((None, [Handler("builtin", name=name)]))
    return config


def _store(payload: dict) -> MemoryStore | None:
    memory = payload.get("memory")
    if not isinstance(memory, dict) or not memory.get("root"):
        return None                                   # the harness was not given a memory: nothing to do
    return MemoryStore(memory["root"], payload.get("person") or "default")


@hooks.builtin("memory_recall")
def memory_recall(payload: dict) -> dict:
    store = _store(payload)
    if store is None:
        return {}
    memory = payload["memory"]
    result = recall(store, str(payload.get("prompt") or ""), budget=int(memory.get("budget", DEFAULT_BUDGET)),
                    half_life_days=float(memory.get("half_life_days", HALF_LIFE_DAYS)))
    if not result.text:
        return {}
    note = f"memory: recalled {len(result.ids)} of {result.considered} item(s) for {store.person}"
    if result.left_out:
        note += f"; {result.left_out} not recalled"
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": result.text},
            "systemMessage": note}


@hooks.builtin("memory_extract")
def memory_extract(payload: dict) -> dict:
    store = _store(payload)
    if store is None:
        return {}
    report = end_session(store, payload.get("transcript") or [], session_id=str(payload.get("session_id") or ""),
                         index=str(payload.get("index") or ""), tainted=bool(payload.get("tainted")),
                         known_tools=payload.get("tools") or ())
    message = report.summary(store.person)
    return {"systemMessage": message} if message else {}
