"""dawnr_persona.py: a persona per person, learned from interactions, visible and editable.

AMBITION.md, "dawnr grows with the person using it": *a personality that grows
per person: a persona per person (tone, detail, interests, how they like to
work) learned from interactions, visible and editable.* This module is that
row. It answers three questions:

1. **What is a persona?** `PersonaRecord`: tone, a detail level, an
   explanation depth, a list of interests and a dict of working preferences
   (such as `{"show_proof_first": True}`), plus an append-only history of how
   it got that way.
2. **How does it change?** Never silently. Every field the rule engine or a
   person touches goes through one function, `_apply`, which is the only
   place a `Change` is appended to the history: a rule name (or `None` for a
   person's own correction), the field, the old and new value, and a reason
   in plain words. `observe()` runs the rule table over one message from the
   person and returns whatever it changed; `correct()`, `add_interest()`,
   `remove_interest()`, `set_preference()` and `unset_preference()` are the
   same choke point for a direct, person-driven edit. Nothing else in this
   module mutates a `PersonaRecord`'s fields.
3. **Who can see and undo it?** `render_persona_preamble()` turns a persona
   into the few lines a fresh person's history has never made it write; a
   default persona (nothing learned yet) renders to the empty string, so a
   brand-new session carries no persona text at all. `undo_last()` reverts
   the most recent entry by appending its inverse (history is never edited or
   shortened, only ever added to, so the record of what happened is never
   lost). `PersonaStore.delete()` is full erasure: the file is gone and
   `get()` on that person afterwards returns a fresh default, same as someone
   dawnr has never met.

Where this sits in the chat format (DAWNR-HARNESS.md section 1): dawnr has no
system message, and the harness's tool index is composed into the head of the
first user turn as plain trusted text (`Harness.index()`, prepended by the
caller, e.g. `chat_cli.py`'s `user = harness.index() + "\n\n" + user`), never
as a tool output and never marked `<|untrusted|>`. A persona preamble follows
the identical shape and the identical trust level: it is the person's own
words about themselves, reflected back, composed the same way by the same
kind of caller (`with_persona_preamble`), not read from outside and not
supervised any differently from the rest of the user turn. This module does
not import chat.py and does not know about tokens; it only ever hands back
plain strings for a caller to fold into a user turn the way it already folds
in the harness index.

Storage is one small interface, `PersonaStore`, so the memory track's store
(AMBITION.md's "long-term memory per person: what happened, what is true
about them ... recalled into each new session; they can read, correct,
export and erase it") can back the same four methods (`get`, `save`,
`delete`, `list_people`) with whatever it ends up keeping episodes in,
without this module or its callers changing. `JSONFilePersonaStore` is the
default until that exists: one human-readable JSON file per person, offline,
no network, atomic writes (chat_pane.py's own `save_harness_config` pattern:
write a `.tmp` file, then `Path.replace`, so a partial write is never read).

Design followed, and where it differs: Ramos et al., "Transparent and
Scrutable Recommendations Using Natural Language User Profiles" (ACL 2024,
arXiv:2402.05810) represents a user's preferences as a natural-language
profile instead of an opaque embedding, so the person can read it and edit it
directly, and shows that editing that profile changes the system's behaviour
(their scrutability evaluation). `PersonaRecord` follows the same idea: a
handful of plain fields rendered as a short block of text, not a vector, so
the person can read exactly what is stored and correct it directly. Where
this differs, and why: their profile is generated and updated by an LLM
summarising past reviews, an opaque step even though its output is legible;
dawnr's rule is that nothing is trusted without evidence and every change
must carry a reason a person (or a reviewer) can audit line by line, so here
a persona changes only through the small, fixed, named rules in `RULES` and
`INTEREST_PATTERNS`, matched by plain substring and regex over the person's
own words, with no model call, no summarisation and no network involved.

What this module does not do, plainly: it does not understand negation,
sarcasm or context ("not shorter, please" still contains "shorter" and will
fire the same rule as a plain request for shorter answers), and the interest
patterns only catch a few fixed phrasings, not everything a person might mean
by mentioning a topic. That is the trade this design makes on purpose (a
rule a person can read and predict beats a classifier that is right more
often but cannot be audited); `correct()` and the CLI below are how a person
fixes whatever the rules got wrong, and every such fix is itself a logged,
reversible change like any other.

CLI (standard library only, no torch):

    python3 locallm/dawnr_persona.py show --person alice
    python3 locallm/dawnr_persona.py set --person alice --tone "warm and direct" --detail brief
    python3 locallm/dawnr_persona.py interest add --person alice "embedded systems"
    python3 locallm/dawnr_persona.py interest remove --person alice "embedded systems"
    python3 locallm/dawnr_persona.py preference set --person alice show_proof_first true
    python3 locallm/dawnr_persona.py preference unset --person alice show_proof_first
    python3 locallm/dawnr_persona.py observe --person alice "could you give me shorter answers"
    python3 locallm/dawnr_persona.py history --person alice
    python3 locallm/dawnr_persona.py undo --person alice
    python3 locallm/dawnr_persona.py export --person alice
    python3 locallm/dawnr_persona.py erase --person alice
    python3 locallm/dawnr_persona.py list

Tests: `locallm/test_dawnr_persona.py` (standard library only, no torch, no
display).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------- the record

#: Ordered so a rule can step one notch up or down and clamp at either end.
DETAIL_LEVELS = ("brief", "normal", "detailed")
DEPTH_LEVELS = ("surface", "normal", "deep")
DEFAULT_TONE = "plain"
DEFAULT_PERSON = "default"

#: MCP's rule for a tool name (DAWNR-HARNESS.md section 2): 1 to 128 of
#: A-Za-z0-9_.-. Reused here for a person id for the same reason it works
#: there: no path separator can reach the filesystem through it. Matched with
#: fullmatch, not match: `$` alone accepts a string with a trailing newline
#: (it is allowed to match just before one), so `match` would let
#: "alice\n" through as if it were "alice"; fullmatch requires the match to
#: reach the literal end of the string.
PERSON_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
MAX_TONE = 60
MAX_INTEREST = 60
MAX_REASON = 500


class PersonaError(ValueError):
    """A person id, field, or value this module refuses, with why."""


def _check_person_id(person_id: str) -> str:
    if (not isinstance(person_id, str) or not PERSON_ID.fullmatch(person_id)
            or person_id in (".", "..")):
        raise PersonaError(
            f"person id must be 1 to 128 of A-Za-z0-9_.- (and not '.' or '..'), not {person_id!r}")
    return person_id


@dataclass(frozen=True)
class Change:
    """One logged, append-only entry: what changed, from what, to what, and why.

    `rule` is the name of the `RULES`/`INTEREST_PATTERNS` entry that fired,
    `"person_correction"` for a direct edit, `"undo"` for the reversal of an
    earlier entry, or `None` only for a change made before this field
    existed (reading an older file). `old`/`new` are already JSON-safe
    (str, bool, int, float, list, dict or None), the same shape `field`
    names in `PersonaRecord`.
    """
    when: float
    field: str
    old: object
    new: object
    reason: str
    rule: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Change":
        return cls(when=float(d["when"]), field=str(d["field"]), old=d.get("old"),
                   new=d.get("new"), reason=str(d.get("reason", "")), rule=d.get("rule"))


@dataclass
class PersonaRecord:
    """Everything dawnr has learned about how one person likes to work.

    A fresh record (`PersonaRecord(person_id)`) is the same as dawnr knowing
    nothing about someone yet: default tone, "normal" detail and depth, no
    interests, no preferences, `is_default()` true, and `render_persona_preamble`
    of it is the empty string. Nothing here is ever set except through
    `_apply` (this module's functions and the rule engine), so `history` is a
    complete account of how the record reached its current values.
    """
    person_id: str
    tone: str = DEFAULT_TONE
    detail_level: str = "normal"
    explanation_depth: str = "normal"
    interests: list[str] = field(default_factory=list)
    preferences: dict[str, object] = field(default_factory=dict)
    history: list[Change] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    def is_default(self) -> bool:
        return (self.tone == DEFAULT_TONE and self.detail_level == "normal"
                and self.explanation_depth == "normal" and not self.interests
                and not self.preferences)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["history"] = [c.to_dict() for c in self.history]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PersonaRecord":
        rec = cls(
            person_id=str(d["person_id"]), tone=str(d.get("tone", DEFAULT_TONE)),
            detail_level=str(d.get("detail_level", "normal")),
            explanation_depth=str(d.get("explanation_depth", "normal")),
            interests=list(d.get("interests", [])), preferences=dict(d.get("preferences", {})),
            created=float(d.get("created", time.time())), updated=float(d.get("updated", time.time())))
        rec.history = [Change.from_dict(c) for c in d.get("history", [])]
        return rec


# ------------------------------------------------------------- the interface

class PersonaStore(ABC):
    """How a persona is kept. The memory track's store backs the same four methods.

    `get` never raises for a person dawnr has not met: it returns a fresh
    default `PersonaRecord`, the same object a first session would build,
    without writing anything. Only `save` persists, so opening a chat with a
    new person leaves no trace until something about them is actually
    learned or set. `delete` is the erase half of "read, correct, erase"
    (AMBITION.md): afterwards `get` of that person id is indistinguishable
    from one dawnr has never met.
    """

    @abstractmethod
    def get(self, person_id: str) -> PersonaRecord: ...

    @abstractmethod
    def save(self, record: PersonaRecord) -> None: ...

    @abstractmethod
    def delete(self, person_id: str) -> None: ...

    @abstractmethod
    def list_people(self) -> list[str]: ...


def default_persona_dir() -> Path:
    """$DAWNR_PERSONA_DIR, else ~/.dawnr/personas.

    Both sides are resolved at run time (`os.environ`, `Path.home()`); no
    particular account or machine is written into this file (AGENTS.md rule
    7), the same way `${DAWNR_HARNESS_DIR}` is a run-time substitution in
    DAWNR-HARNESS.md's hook configuration, not a literal path.
    """
    env = os.environ.get("DAWNR_PERSONA_DIR")
    return Path(env) if env else Path.home() / ".dawnr" / "personas"


class JSONFilePersonaStore(PersonaStore):
    """One `<person_id>.json` file per person under `root`. Offline; no network.

    Matches chat_pane.py's `load_harness_config`/`save_harness_config`: a
    missing or unreadable file is treated as "nothing here yet" rather than
    raised, and a write goes to a `.tmp` file and is then swapped into place
    (`Path.replace`) so a reader never sees a half-written record.
    """

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root is not None else default_persona_dir()

    def _path(self, person_id: str) -> Path:
        return self.root / f"{_check_person_id(person_id)}.json"

    def get(self, person_id: str) -> PersonaRecord:
        path = self._path(person_id)
        if not path.is_file():
            return PersonaRecord(person_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return PersonaRecord(person_id)
        if not isinstance(data, dict):
            return PersonaRecord(person_id)
        try:
            return PersonaRecord.from_dict(data)
        except (KeyError, TypeError, ValueError):
            return PersonaRecord(person_id)

    def save(self, record: PersonaRecord) -> None:
        path = self._path(record.person_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    def delete(self, person_id: str) -> None:
        self._path(person_id).unlink(missing_ok=True)

    def list_people(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.stem for p in self.root.glob("*.json"))


# ---------------------------------------------------------------- the choke

def _field_get(record: PersonaRecord, field_path: str) -> object:
    if field_path == "tone":
        return record.tone
    if field_path == "detail_level":
        return record.detail_level
    if field_path == "explanation_depth":
        return record.explanation_depth
    if field_path == "interests":
        return list(record.interests)
    if field_path.startswith("preferences."):
        return record.preferences.get(field_path[len("preferences."):])
    raise PersonaError(f"not an editable field: {field_path!r}")


def _field_set(record: PersonaRecord, field_path: str, value: object) -> None:
    if field_path == "tone":
        record.tone = value
    elif field_path == "detail_level":
        record.detail_level = value
    elif field_path == "explanation_depth":
        record.explanation_depth = value
    elif field_path == "interests":
        record.interests = list(value)
    elif field_path.startswith("preferences."):
        key = field_path[len("preferences."):]
        if value is None:
            record.preferences.pop(key, None)
        else:
            record.preferences[key] = value
    else:
        raise PersonaError(f"not an editable field: {field_path!r}")


def _apply(record: PersonaRecord, field_path: str, new_value: object, reason: str,
          rule: str | None = None) -> Change | None:
    """The one place a `PersonaRecord` is mutated and logged. A no-op change (new == old) logs nothing.

    Validates the reason before touching anything: a rejected change must
    leave the record exactly as it was, never mutated with nothing to show
    for it in the history.
    """
    if not reason or not reason.strip():
        raise PersonaError("a change needs a reason")
    old_value = _field_get(record, field_path)
    if old_value == new_value:
        return None
    _field_set(record, field_path, new_value)
    change = Change(time.time(), field_path, old_value, new_value, reason.strip()[:MAX_REASON], rule)
    record.history.append(change)
    record.updated = change.when
    return change


# ------------------------------------------------------------- corrections
# The person's own edits: still funnelled through `_apply`, still logged and
# reversible, `rule="person_correction"` unless the caller names its own
# (e.g. a chat_pane.py settings dialog can pass a rule of its own choosing).

def correct(record: PersonaRecord, field_path: str, value: object,
           reason: str = "the person set this directly",
           rule: str = "person_correction") -> Change | None:
    """Set one of the three scalar fields directly (tone, detail_level, explanation_depth).

    Interests and preferences are refused here, not merely unvalidated: each
    has its own function (`add_interest`/`remove_interest`,
    `set_preference`/`unset_preference`) that checks the value's shape before
    `_apply` ever sees it, and routing them through this function too would
    let a caller skip that check by construction.
    """
    if field_path == "tone":
        value = _valid_tone(value)
    elif field_path == "detail_level":
        value = _valid_level(value, DETAIL_LEVELS, "detail_level")
    elif field_path == "explanation_depth":
        value = _valid_level(value, DEPTH_LEVELS, "explanation_depth")
    elif field_path == "interests":
        raise PersonaError("use add_interest/remove_interest, not correct(), for interests")
    elif field_path.startswith("preferences."):
        raise PersonaError("use set_preference/unset_preference, not correct(), for a preference")
    else:
        raise PersonaError(f"not an editable field: {field_path!r}")
    return _apply(record, field_path, value, reason, rule)


def _valid_tone(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonaError("tone must be a non-empty string")
    value = " ".join(value.split())[:MAX_TONE]
    return value


def _valid_level(value: object, levels: tuple[str, ...], name: str) -> str:
    if value not in levels:
        raise PersonaError(f"{name} must be one of {levels}, not {value!r}")
    return value


def _norm_interest(text: str) -> str:
    return " ".join(text.split()).strip().lower()[:MAX_INTEREST]


def add_interest(record: PersonaRecord, interest: str,
                 reason: str = "the person added this interest",
                 rule: str = "person_correction") -> Change | None:
    interest = _norm_interest(interest)
    if not interest:
        raise PersonaError("an interest cannot be empty")
    if interest in record.interests:
        return None
    return _apply(record, "interests", record.interests + [interest], reason, rule)


def remove_interest(record: PersonaRecord, interest: str,
                    reason: str = "the person removed this interest",
                    rule: str = "person_correction") -> Change | None:
    interest = _norm_interest(interest)
    if interest not in record.interests:
        return None
    kept = [i for i in record.interests if i != interest]
    return _apply(record, "interests", kept, reason, rule)


def set_preference(record: PersonaRecord, key: str, value: bool | str | int | float,
                   reason: str = "the person set this directly",
                   rule: str = "person_correction") -> Change | None:
    if not isinstance(key, str) or not key.strip():
        raise PersonaError("a preference key cannot be empty")
    if not isinstance(value, (bool, str, int, float)):
        raise PersonaError(f"a preference value must be a bool, string or number, not {type(value).__name__}")
    return _apply(record, f"preferences.{key.strip()}", value, reason, rule)


def unset_preference(record: PersonaRecord, key: str,
                     reason: str = "the person removed this preference",
                     rule: str = "person_correction") -> Change | None:
    return _apply(record, f"preferences.{key.strip()}", None, reason, rule)


def undo_last(record: PersonaRecord, reason: str | None = None) -> Change | None:
    """Revert the most recent history entry by appending its inverse.

    History is never edited or shortened: undoing is one more logged change
    (`rule="undo"`), so the record of what happened, and that it was later
    undone, both survive. Returns None with an empty history or a history
    that is nothing but undos of everything already reverted to the start
    (nothing left whose current value still matches its `new`).
    """
    for entry in reversed(record.history):
        if entry.rule in ("undo", "note"):
            continue
        try:
            current = _field_get(record, entry.field)
        except PersonaError:
            continue  # not a revertible field (e.g. a future entry kind this version does not know)
        if current != entry.new:
            continue  # already superseded by a later change; nothing to revert here
        why = reason or f"undo: reverting {entry.reason!r}"
        return _apply(record, entry.field, entry.old, why, "undo")
    return None


# ------------------------------------------------------------- the rule table
# Deterministic, named, and literal on purpose (module docstring: a rule a
# person can read and predict beats a classifier that cannot be audited).
# Each rule fires independently; several may fire on one message.

@dataclass(frozen=True)
class InteractionRule:
    name: str
    triggers: tuple[str, ...]
    field: str
    step: Callable[[PersonaRecord], object]
    reason: str

    def matches(self, text: str) -> bool:
        low = text.lower()
        return any(t in low for t in self.triggers)


def _step_level(levels: tuple[str, ...], current: str, delta: int) -> str:
    i = levels.index(current) if current in levels else levels.index("normal")
    return levels[max(0, min(len(levels) - 1, i + delta))]


RULES: tuple[InteractionRule, ...] = (
    InteractionRule(
        "shorter_answers",
        ("shorter answer", "shorter answers", "too long", "less detail", "be more concise",
         "more concise", "keep it brief", "tl;dr", "tldr"),
        "detail_level", lambda p: _step_level(DETAIL_LEVELS, p.detail_level, -1),
        "the message asked for shorter or less detailed answers"),
    InteractionRule(
        "more_detail",
        ("more detail", "more details", "more depth", "go deeper", "in more detail", "elaborate more"),
        "detail_level", lambda p: _step_level(DETAIL_LEVELS, p.detail_level, +1),
        "the message asked for more detail"),
    InteractionRule(
        "explain_reasoning",
        ("explain your reasoning", "show your work", "walk me through", "explain why", "explain the reasoning"),
        "explanation_depth", lambda p: _step_level(DEPTH_LEVELS, p.explanation_depth, +1),
        "the message asked for the reasoning behind an answer"),
    InteractionRule(
        "just_the_answer",
        ("just the answer", "just give me the answer", "skip the explanation", "no explanation",
         "don't explain", "do not explain"),
        "explanation_depth", lambda p: _step_level(DEPTH_LEVELS, p.explanation_depth, -1),
        "the message asked to skip the explanation"),
    InteractionRule(
        "show_proof_first",
        ("show the proof first", "proof first", "lead with the proof", "put the proof first"),
        "preferences.show_proof_first", lambda p: True,
        "the message asked to see the proof before the rest of the answer"),
    InteractionRule(
        "proof_last",
        ("proof last", "answer first then proof", "explanation before the proof", "proof at the end"),
        "preferences.show_proof_first", lambda p: False,
        "the message asked for the proof after the explanation, not before it"),
    InteractionRule(
        "more_casual",
        ("be more casual", "less formal", "loosen up a bit", "talk casually"),
        "tone", lambda p: "casual",
        "the message asked for a more casual tone"),
    InteractionRule(
        "more_formal",
        ("be more formal", "more professional", "less casual", "keep it formal"),
        "tone", lambda p: "formal",
        "the message asked for a more formal tone"),
)

#: A fixed set of literal templates, not free-form extraction (module
#: docstring: this catches a few phrasings, not everything a person might
#: mean). Each pattern's one group is the interest text.
INTEREST_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\bi(?:'m| am) (?:really |also |quite )?interested in ([a-z0-9][a-z0-9 /_+-]{1,58}?)(?:[.!?,]|$)", re.I),
    re.compile(r"\badd (?:that )?interest:? +([a-z0-9][a-z0-9 /_+-]{1,58}?)(?:[.!?,]|$)", re.I),
    re.compile(r"\bi work on ([a-z0-9][a-z0-9 /_+-]{1,58}?)(?:[.!?,]|$)", re.I),
)


def observe(record: PersonaRecord, message: str) -> list[Change]:
    """Run the rule table over one message from the person; return whatever it changed.

    Every rule is checked (several can fire on one message); a rule whose
    step would not move the field (already at the floor or ceiling, or
    already at the value it would set) applies nothing and logs nothing, so
    the history holds only real changes. Call this on the person's raw text
    before it is used for anything else; it never raises on ordinary text.
    """
    changes: list[Change] = []
    if not isinstance(message, str) or not message.strip():
        return changes
    for rule in RULES:
        if not rule.matches(message):
            continue
        new_value = rule.step(record)
        change = _apply(record, rule.field, new_value, rule.reason, rule.name)
        if change is not None:
            changes.append(change)
    for pattern in INTEREST_PATTERNS:
        for m in pattern.finditer(message):
            interest = _norm_interest(m.group(1))
            if not interest:
                continue
            change = _apply(record, "interests",
                            record.interests + [interest] if interest not in record.interests else record.interests,
                            f"the message said they are interested in {interest!r}", "interest_mention")
            if change is not None:
                changes.append(change)
    return changes


# ---------------------------------------------------------------- rendering

def render_persona_preamble(record: PersonaRecord) -> str:
    """A short block for the head of the first user turn; "" for a still-default persona.

    Composed the same way `Harness.index()` is (DAWNR-HARNESS.md section 1):
    plain text a caller folds into the user's own turn, trusted, never a
    tool output, never marked `<|untrusted|>`. "Persona:" parallels that
    index's "Tools:"/"Skills:" lines. A brand-new person (nothing learned
    yet) gets no preamble at all, not an empty one describing defaults, so a
    fresh session never spends tokens on what has not been learned.
    """
    if record.is_default():
        return ""
    lines = ["Persona:", f"Tone: {record.tone}. Detail: {record.detail_level}. "
                         f"Explanations: {record.explanation_depth}."]
    if record.interests:
        lines.append("Interested in: " + ", ".join(record.interests) + ".")
    if record.preferences:
        prefs = "; ".join(f"{k}: {v}" for k, v in sorted(record.preferences.items()))
        lines.append("Working preferences: " + prefs + ".")
    return "\n".join(lines)


def with_persona_preamble(text: str, record: PersonaRecord) -> str:
    """`text`, with the persona preamble folded onto its head; `text` unchanged if there is none yet."""
    preamble = render_persona_preamble(record)
    return f"{preamble}\n\n{text}" if preamble else text


# --------------------------------------------------------------------- CLI

def _print_record(record: PersonaRecord) -> None:
    print(f"person: {record.person_id}")
    print(f"tone: {record.tone}")
    print(f"detail_level: {record.detail_level}")
    print(f"explanation_depth: {record.explanation_depth}")
    print(f"interests: {', '.join(record.interests) if record.interests else '(none)'}")
    if record.preferences:
        for k, v in sorted(record.preferences.items()):
            print(f"preference {k}: {v}")
    else:
        print("preferences: (none)")
    print(f"history entries: {len(record.history)}")
    preamble = render_persona_preamble(record)
    print("preamble: " + (preamble.replace(chr(10), " / ") if preamble else "(none yet)"))


def _parse_pref_value(raw: str) -> bool | str | int | float:
    low = raw.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="dawnr_persona.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=None,
                    help="persona store directory (default: $DAWNR_PERSONA_DIR or ~/.dawnr/personas)")
    sub = ap.add_subparsers(dest="command", required=True)

    def person_arg(p):
        p.add_argument("--person", default=DEFAULT_PERSON, help="person id (default: %(default)s)")

    person_arg(sub.add_parser("show", help="print the persona"))
    person_arg(sub.add_parser("export", help="print the full record as JSON"))
    person_arg(sub.add_parser("history", help="print the change log"))
    person_arg(sub.add_parser("undo", help="revert the most recent change"))
    person_arg(sub.add_parser("erase", help="forget this person completely"))
    sub.add_parser("list", help="list every person id with a stored record")

    p_set = sub.add_parser("set", help="set tone, detail level or explanation depth directly")
    person_arg(p_set)
    p_set.add_argument("--tone")
    p_set.add_argument("--detail", choices=DETAIL_LEVELS)
    p_set.add_argument("--depth", choices=DEPTH_LEVELS)
    p_set.add_argument("--reason", default="the person set this directly")

    p_obs = sub.add_parser("observe", help="run the rule table over one message")
    person_arg(p_obs)
    p_obs.add_argument("message")

    p_note = sub.add_parser("note", help="log a reason with no field change, for the record")
    person_arg(p_note)
    p_note.add_argument("text")

    p_int = sub.add_parser("interest", help="add or remove an interest")
    p_int.add_argument("action", choices=("add", "remove"))
    person_arg(p_int)
    p_int.add_argument("interest")
    p_int.add_argument("--reason")

    p_pref = sub.add_parser("preference", help="set or unset a working preference")
    p_pref.add_argument("action", choices=("set", "unset"))
    person_arg(p_pref)
    p_pref.add_argument("key")
    p_pref.add_argument("value", nargs="?", help="required for 'set'; a bool ('true'/'false'), number or string")
    p_pref.add_argument("--reason")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    store = JSONFilePersonaStore(args.root)

    if args.command == "list":
        people = store.list_people()
        print("\n".join(people) if people else "(no one dawnr has learned anything about yet)")
        return 0

    if args.command == "erase":
        store.delete(args.person)
        print(f"erased everything stored about {args.person!r}")
        return 0

    record = store.get(args.person)

    if args.command == "show":
        _print_record(record)
        return 0
    if args.command == "export":
        print(json.dumps(record.to_dict(), indent=2, sort_keys=True))
        return 0
    if args.command == "history":
        if not record.history:
            print("(no changes yet)")
        for c in record.history:
            tag = c.rule or "?"
            print(f"[{tag}] {c.field}: {c.old!r} -> {c.new!r} ({c.reason})")
        return 0

    history_before = len(record.history)
    try:
        if args.command == "set":
            if args.tone is not None:
                correct(record, "tone", args.tone, args.reason)
            if args.detail is not None:
                correct(record, "detail_level", args.detail, args.reason)
            if args.depth is not None:
                correct(record, "explanation_depth", args.depth, args.reason)
        elif args.command == "observe":
            changes = observe(record, args.message)
            for c in changes:
                print(f"[{c.rule}] {c.field}: {c.old!r} -> {c.new!r} ({c.reason})")
            if not changes:
                print("(no rule matched; nothing changed)")
        elif args.command == "note":
            record.history.append(Change(time.time(), "(note)", None, None, args.text[:MAX_REASON], "note"))
            record.updated = time.time()
        elif args.command == "interest":
            reason = args.reason or ("the person added this interest" if args.action == "add"
                                     else "the person removed this interest")
            (add_interest if args.action == "add" else remove_interest)(record, args.interest, reason)
        elif args.command == "preference":
            if args.action == "set":
                if args.value is None:
                    raise PersonaError("preference set needs a value")
                reason = args.reason or "the person set this directly"
                set_preference(record, args.key, _parse_pref_value(args.value), reason)
            else:
                reason = args.reason or "the person removed this preference"
                unset_preference(record, args.key, reason)
        elif args.command == "undo":
            change = undo_last(record)
            if change is None:
                print("(nothing to undo)")
            else:
                print(f"undid: {change.field} -> {change.new!r} ({change.reason})")
    except PersonaError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1

    if len(record.history) > history_before:      # only a real change touches disk
        store.save(record)
    if args.command not in ("undo",):
        _print_record(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
