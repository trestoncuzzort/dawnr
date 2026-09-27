"""feedback.py: what a person tells dawnr about its answers, kept per person, with where it came from.

Standard library only (the chat pane loads it with no torch). Every answer dawnr
gives in a conversation can become one record in the person's store; what the
person then does with it is the feedback:

    up       the answer is right as it is: it becomes a training example unchanged
    down     the answer is wrong or unwanted, and no better answer was given
    edit     the person rewrote the answer: their version is the training example
    wrong    a "that's wrong" turn (or the pane's own flag): with a program in the
             same message, that program is the correction and becomes the example

The two sources this follows, both read in full before this was written:
Hancock et al., "Learning from Dialogue after Deployment: Feed Yourself,
Chatbot!" (arXiv:1901.05415): a deployed bot keeps what the person says when an
answer went wrong as new training data, excludes the dissatisfied turns from
imitation, and gains most from feedback folded in between batches rather than
all at once. Gao et al., PRELUDE (arXiv:2404.15269): the person's edit of an
answer is the most natural feedback there is, and the edit distance between the
answer and the edit is the cost of a round, which is what a learner should
drive down over rounds.

The detector for a "that's wrong" turn is a regular expression, as Hancock et
al.'s first detector was; theirs measured precision 0.91 and recall 0.27. The
same trade is taken on purpose: a match must almost never be a false alarm,
since it marks an answer wrong, and the misses are carried by the explicit
buttons (up, down, edit) instead. It never trains on anything by itself.

What the person controls (AMBITION.md: they can read, correct, export and erase
what is remembered about them): `records()` and `export()` read everything,
`correct()` replaces an example's target, `erase()` deletes a record and keeps
only a tombstone of its id and time (never its content), `erase_all()` deletes
the person. An adapter records which examples (id and content hash) it was
trained on, so erasing or correcting one of them makes that adapter stale and
it is not used again until a sleep rebuilds it without them (adapters.py,
exact unlearning by retraining, SISA arXiv:1912.03817).

Outside content never becomes training data: a record whose answer carries a
tool output marked untrusted (a web page, an MCP result; DAWNR-HARNESS.md) is
kept for the person to read but excluded from training_examples(), counted
under its reason. Every target is checked by the t tool on the prompt's own
Example lines before it can be trained on (dawnr_harness.checker.check); a
target whose program fails is excluded and counted, never silently dropped.
Last, training_examples() gates every example against the held-out ids, the
same-task exclusions and the r12 dev ids (held_out_gate) before returning it,
by default and for every caller: nothing that reads a person's examples for
training, style or measurement sees an ungated one just because it did not
ask for the gate itself (DAWNR-LEARNING.md section 8).

Where the data lives: default_root(), the platform's per-user data directory
(platformdirs' user_data_dir: $XDG_DATA_HOME or ~/.local/share on Linux,
%LOCALAPPDATA% on Windows, ~/Library/Application Support on macOS;
github.com/tox-dev/platformdirs), never beside a checkpoint in this public
repository. DAWNR_PEOPLE_DIR overrides it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

SCHEMA = 1
FEEDBACK = ("up", "down", "edit", "wrong")
TRAINABLE = ("up", "edit", "wrong")          # "wrong" only when it carries a correction
PERSON_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

# A "that's wrong" turn: the person's message opens by saying the last answer was wrong. Anchored at the
# start on purpose (precision over recall, see the module docstring): "is it wrong to ...?" is a question,
# not a verdict, and does not match.
WRONG_TURN = re.compile(
    r"""^\s*(?:(?:no|nope|hm+|hmm+)\s*[,.!:;-]*\s*)?
        (?:(?:that|this|it|your\s+(?:answer|program|code))(?:'s|\s+is|\s+was)\s+
             (?:wrong|incorrect|not\s+(?:right|correct|what\s+i\s+(?:asked|wanted|meant)))
          |(?:wrong|incorrect)\b
          |(?:that|this|it)\s+(?:does(?:n't|\s+not)|did(?:n't|\s+not))\s+work
          |not\s+(?:right|correct)\b)""", re.I | re.X)


def default_root() -> Path:
    """Where people's records and adapters live on this machine (DAWNR_PEOPLE_DIR overrides it)."""
    env = os.environ.get("DAWNR_PEOPLE_DIR")
    if env:
        return Path(env)
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "dawnr" / "dawnr" / "people"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "dawnr" / "people"
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "dawnr" / "people"


def person_id(name: str) -> str:
    """A person's folder name: lowercase letters, digits, '-' and '_', 1 to 64 characters; anything else refused."""
    pid = str(name).strip().lower()
    if not PERSON_ID.match(pid):
        raise ValueError(f"a person's name for dawnr's memory is 1-64 of a-z, 0-9, '-' and '_', not {name!r}")
    return pid


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ------------------------------------------------------------- content --

def parts_of(content) -> list[dict]:
    """An assistant message's content as parts (a plain string is one text part)."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if not isinstance(content, list) or not all(isinstance(p, dict) for p in content):
        raise ValueError(f"an assistant message is a string or a list of parts, not {type(content).__name__}")
    return content


def content_text(content) -> str:
    """What the assistant itself wrote, as one string: its text and its tool calls, never a tool's output.

    The form used for edit distances and for comparing an answer with its edit;
    tool outputs are left out because the tool writes them, not the model."""
    out = []
    for part in parts_of(content):
        kind = part.get("type")
        if kind == "text":
            out.append(part.get("text", ""))
        elif kind == "t":
            out.append("<|t_start|>" + part.get("text", "") + "<|t_end|>")
        elif kind == "tool":
            out.append("<|tool_start|>" + part.get("text", "") + "<|tool_end|>")
    return "".join(out)


def has_untrusted(content) -> bool:
    return isinstance(content, list) and any(isinstance(p, dict) and p.get("untrusted") for p in content)


def final_program(content) -> str | None:
    """The program an answer stands on: the last t call, else the first t program in its text."""
    parts = parts_of(content)
    calls = [p.get("text", "") for p in parts if p.get("type") == "t"]
    if calls and calls[-1].strip():
        return calls[-1]
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    found = extract_programs(text)
    return found[0] if found else None


def extract_programs(text: str) -> list[str]:
    """Every t program in a piece of text (a `t N` line through the brace closing its body)."""
    from dawnr_harness.checker import find_programs
    return find_programs(text or "", limit=8)


def is_wrong_turn(text: str) -> bool:
    """True when a person's message opens by saying the last answer was wrong (high precision, low recall)."""
    return bool(WRONG_TURN.match(text or ""))


def check_target(messages: list[dict], target) -> dict:
    """The t tool's verdict on a target's program, on the Example lines of the prompt it answers.

    {"ok": bool, "verdict": str, "program": bool}. A target with no t program in
    it (a plain sentence) has nothing to check: ok, with program False."""
    from dawnr_harness.checker import check
    program = final_program(target)
    if program is None:
        return {"ok": True, "verdict": "", "program": False}
    context = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    ok, verdict = check(program, context if isinstance(context, str) else "")
    return {"ok": bool(ok), "verdict": verdict, "program": True}


def replace_program(content, program: str, context: str = ""):
    """The answer with its final program replaced by `program`, the t tool's real verdict after it.

    For a plain-text answer the result is the new program as plain text; for an
    answer with t calls, the text before the last call is kept, the call's
    program is replaced and its output recomputed by the tool (a tool output
    is never written by hand)."""
    import t_tool
    parts = parts_of(content)
    last = max((i for i, p in enumerate(parts) if p.get("type") == "t"), default=None)
    if last is None:
        return program
    kept = [dict(p) for p in parts[:last]]
    return kept + [{"type": "t", "text": program}, {"type": "t_output", "text": t_tool.call(program, context)}]


def example_hash(messages: list[dict], target) -> str:
    blob = json.dumps({"messages": messages, "target": target}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- gate --

_T_DIR = Path(__file__).resolve().parents[2] / "t"
DEFAULT_SPLIT = _T_DIR / "out" / "loop" / "split-v5.json"


def held_out_gate(examples: list[dict], split_path: Path | str | None = None) -> tuple[list[dict], list[dict]]:
    """(kept, refused): every trainer's own screen over each example's whole rendered text and its record
    id -- the evaluation ids of `split_path` (DEFAULT_SPLIT unless given), the checked-in same-task
    exclusions (loop_filter.decontamination) and the r12 dev ids (loop_filter.r12_dev_ids) -- whatever the
    person typed.

    This is the one gate every reader of a person's examples goes through: PersonStore.training_examples()
    calls it by default, so a sleep, the style profile and the measurement protocol cannot see an example
    the corpus itself would refuse just because a caller forgot a second step. It used to be sleep.py's
    alone (`sleep.gate_examples`, kept importable there under that name for callers who already spell it
    that way); moved here 2026-09-27 because style_profile.refresh read training_examples() directly and
    never applied it (DAWNR-LEARNING.md section 8): a person's feedback on a held-out or dev prompt could
    shape their style profile, and so dawnr's output, with no decontamination check at all.

    Needs t/ (loop_filter, and what it imports) on sys.path; finds it itself the same way t_tool.py and
    loop_filter.py find their own imports, so a gated read never depends on some other module having
    already added it."""
    t_dir = str(_T_DIR)
    if t_dir not in sys.path:
        sys.path.insert(0, t_dir)
    import loop_filter
    split_path = Path(split_path) if split_path is not None else DEFAULT_SPLIT
    eval_ids = {int(i) for i in json.loads(split_path.read_text(encoding="utf-8"))["eval_ids"]}
    dev = loop_filter.r12_dev_ids(split_path=split_path)
    policy = loop_filter.decontamination()
    kept, refused = [], []
    for ex in examples:
        text = json.dumps(ex["messages"], ensure_ascii=False)
        v = loop_filter.validate_training_data(text, eval_ids, policy=policy)
        dev_hit = loop_filter.held_out_ids_in(text, set(dev))
        if v.ok and not dev_hit:
            kept.append(ex)
        else:
            why = []
            if v.held_out:
                why.append(loop_filter.held_out_detail(v.held_out))
            if v.same_task_names or v.same_task_ids:
                why.append(loop_filter.same_task_detail(v))
            if dev_hit:
                why.append("dev-split " + loop_filter.held_out_detail(dev_hit))
            refused.append({"id": ex["id"], "why": "; ".join(why)})
    return kept, refused


# --------------------------------------------------------------- store --

class PersonStore:
    """One person's records: <root>/<person>/records.jsonl, rewritten atomically on every change."""

    def __init__(self, person: str, root: Path | str | None = None):
        self.person = person_id(person)
        self.root = Path(root) if root is not None else default_root()
        self.dir = self.root / self.person
        self.path = self.dir / "records.jsonl"
        self.tombstones = self.dir / "erased.jsonl"

    # ---- files
    def _ensure_dir(self) -> None:
        """Create the person's folder, private to this user (platformdirs' private=True); a folder that
        already existed keeps its permissions, so pointing DAWNR_PEOPLE_DIR somewhere never changes them."""
        fresh = [d for d in (self.root, self.dir) if not d.exists()]
        self.dir.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            for d in fresh:
                try:
                    os.chmod(d, 0o700)
                except OSError:
                    pass

    def records(self) -> list[dict]:
        if not self.path.is_file():
            return []
        out = []
        for n, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                row = json.loads(line)
                if row.get("schema") != SCHEMA:
                    raise ValueError(f"{self.path}:{n}: schema {row.get('schema')!r} is not {SCHEMA}")
                out.append(row)
        return out

    def _write(self, rows: list[dict]) -> None:
        self._ensure_dir()
        tmp = self.path.with_name(self.path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        tmp.replace(self.path)

    def get(self, record_id: str) -> dict:
        for row in self.records():
            if row["id"] == record_id:
                return row
        raise KeyError(f"{self.person} has no record {record_id!r}")

    def _update(self, record_id: str, change) -> dict:
        rows = self.records()
        for i, row in enumerate(rows):
            if row["id"] == record_id:
                change(row)
                row["updated"] = now()
                rows[i] = row
                self._write(rows)
                return row
        raise KeyError(f"{self.person} has no record {record_id!r}")

    # ---- recording
    def add_answer(self, messages: list[dict], answer, *, session: str = "", model: dict | None = None,
                   how: str = "chat") -> str:
        """Record one answer dawnr gave (no feedback yet); returns its id."""
        if not messages or messages[-1].get("role") != "user":
            raise ValueError("an answer answers a conversation that ends with the person's message")
        parts_of(answer)
        rid = uuid.uuid4().hex[:16]
        row = {"schema": SCHEMA, "id": rid, "person": self.person, "session": session, "created": now(),
               "updated": now(), "messages": messages, "answer": answer, "feedback": None, "target": None,
               "how": how, "note": None, "model": model or {}}
        rows = self.records()
        rows.append(row)
        self._write(rows)
        return rid

    def rate(self, record_id: str, up: bool, how: str = "button") -> dict:
        def change(row):
            row["feedback"] = "up" if up else "down"
            row["target"] = row["answer"] if up else None
            row["how"] = how
        return self._update(record_id, change)

    def edit(self, record_id: str, target, how: str = "edit", note: str | None = None) -> dict:
        parts_of(target)

        def change(row):
            row["feedback"], row["target"], row["how"] = "edit", target, how
            if note is not None:
                row["note"] = note
        return self._update(record_id, change)

    def wrong(self, record_id: str, *, note: str | None = None, correction=None, how: str = "detected") -> dict:
        if correction is not None:
            parts_of(correction)

        def change(row):
            row["feedback"], row["target"], row["how"], row["note"] = "wrong", correction, how, note
        return self._update(record_id, change)

    def correct(self, record_id: str, target) -> dict:
        """The person replaces what an example teaches; an adapter trained on the old version goes stale."""
        return self.edit(record_id, target, how="corrected")

    def erase(self, record_id: str) -> None:
        """Delete a record; only its id and the time it was erased are kept, never its content."""
        rows = self.records()
        kept = [r for r in rows if r["id"] != record_id]
        if len(kept) == len(rows):
            raise KeyError(f"{self.person} has no record {record_id!r}")
        self._write(kept)
        with self.tombstones.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"id": record_id, "erased": now()}) + "\n")

    def erase_all(self) -> int:
        """Delete everything dawnr keeps about this person: records, adapters, sleep records. Returns files removed."""
        import shutil
        count = sum(1 for p in self.dir.rglob("*") if p.is_file()) if self.dir.exists() else 0
        if self.dir.exists():
            shutil.rmtree(self.dir)
        return count

    def export(self) -> dict:
        """Everything kept about this person, in one JSON-ready object."""
        tomb = ([json.loads(x) for x in self.tombstones.read_text(encoding="utf-8").splitlines() if x.strip()]
                if self.tombstones.is_file() else [])
        return {"schema": SCHEMA, "person": self.person, "records": self.records(), "erased": tomb,
                "summary": self.summary()}

    # ---- reading for training
    def training_examples(self, check: bool = True, *, split_path: Path | str | None = None,
                          include_ungated: bool = False) -> tuple[list[dict], dict]:
        """(examples, excluded counts). An example is {"id", "hash", "feedback", "session", "created",
        "messages": [..., the assistant's target]} for every record whose target may be trained on.

        Gated by held_out_gate before it is returned: a held-out, same-task or dev-split example is
        dropped and counted here too, so every reader of a person's examples -- a sleep, the style
        profile, the measurement protocol -- sees the same screened set without a second call of its own
        (this used to be sleep.py's job alone; style_profile.refresh skipped it, DAWNR-LEARNING.md section
        8). Only what needs the person's own unscreened words -- export, and an adapter's erasure
        bookkeeping -- asks for that by name with include_ungated=True; nothing else should pass it."""
        examples, excluded = [], {}

        def skip(reason):
            excluded[reason] = excluded.get(reason, 0) + 1

        for row in self.records():
            if row.get("feedback") not in TRAINABLE or row.get("target") is None:
                skip("no target" if row.get("feedback") else "no feedback")
                continue
            if has_untrusted(row["target"]) or has_untrusted(row.get("answer")):
                skip("untrusted content")
                continue
            if check:
                verdict = check_target(row["messages"], row["target"])
                if not verdict["ok"]:
                    skip("target fails the t tool")
                    continue
            examples.append({"id": row["id"], "hash": example_hash(row["messages"], row["target"]),
                             "feedback": row["feedback"], "session": row.get("session", ""),
                             "created": row.get("created", ""),
                             "messages": list(row["messages"]) + [{"role": "assistant", "content": row["target"]}]})
        if include_ungated:
            return examples, excluded
        gated, refused = held_out_gate(examples, split_path)
        if refused:
            excluded["held-out, same-task or dev"] = len(refused)
        return gated, excluded

    def current_hashes(self) -> dict[str, str]:
        """{record id: content hash} for every record that has a target, checked or not."""
        return {r["id"]: example_hash(r["messages"], r["target"]) for r in self.records()
                if r.get("target") is not None}

    def summary(self) -> dict:
        rows = self.records()
        counts = {k: sum(r.get("feedback") == k for r in rows) for k in FEEDBACK}
        counts["unrated"] = sum(r.get("feedback") is None for r in rows)
        counts["records"] = len(rows)
        counts["sessions"] = len({r.get("session") for r in rows})
        return counts


# ------------------------------------------------------------- recorder --

class Recorder:
    """The chat pane's (and a CLI's) view of one person's store during one session.

    answered() after every reply; thumbs(), edit_program() when the person
    presses a button; user_turn() with every message the person sends, before
    it is answered, so a "that's wrong" turn marks the answer it is about. Every
    method returns a short sentence saying what was kept, for the window to
    show: nothing is remembered about a person silently."""

    def __init__(self, person: str, root: Path | str | None = None, model: dict | None = None,
                 session: str | None = None):
        self.store = PersonStore(person, root)
        self.model = dict(model or {})
        self.session = session or f"{now()}#{uuid.uuid4().hex[:6]}"
        self.last_id: str | None = None

    KEEP_MESSAGES = 7        # the prompt kept with an answer: the last user turn and up to three exchanges before it

    def answered(self, messages: list[dict]) -> str | None:
        """Record the conversation's last assistant message as an answer to what came before it.

        Only the last few turns are kept with it (a sleep drops the oldest turns
        of a conversation that does not fit the context anyway), so a long
        conversation does not store its whole history again with every answer."""
        if len(messages) < 2 or messages[-1].get("role") != "assistant":
            return None
        prompt = list(messages[:-1])[-self.KEEP_MESSAGES:]
        while prompt and prompt[0].get("role") != "user":
            prompt = prompt[1:]
        self.last_id = self.store.add_answer(prompt, messages[-1]["content"], session=self.session,
                                             model=self.model)
        return self.last_id

    def thumbs(self, up: bool) -> str:
        if self.last_id is None:
            return "There is no answer to rate yet."
        self.store.rate(self.last_id, up)
        return ("Kept: this answer is an example of what you want." if up else
                "Kept: this answer was not what you wanted. Edit it to show what you meant.")

    def edit_program(self, new_text: str) -> str:
        """The person's rewrite of the last answer: a t program replaces the answer's program (re-checked
        by the tool); anything else replaces the answer's text."""
        if self.last_id is None:
            return "There is no answer to correct yet."
        row = self.store.get(self.last_id)
        context = next((m["content"] for m in reversed(row["messages"]) if m.get("role") == "user"), "")
        programs = extract_programs(new_text)
        target = replace_program(row["answer"], programs[0], context) if programs else new_text.strip()
        self.store.edit(self.last_id, target)
        verdict = check_target(row["messages"], target)
        if verdict["program"] and not verdict["ok"]:
            return ("Kept your version, but the t tool fails it on the prompt's examples, so it will not be "
                    "learned from until it passes.")
        return "Kept your version: it will be learned from at the next sleep."

    def user_turn(self, text: str) -> str | None:
        """A message the person is about to send; if it says the last answer was wrong, mark that answer."""
        if self.last_id is None or not is_wrong_turn(text):
            return None
        row = self.store.get(self.last_id)
        if row.get("feedback") is not None:
            return None                     # the person already rated it; a later remark does not override that
        programs = extract_programs(text)
        context = next((m["content"] for m in reversed(row["messages"]) if m.get("role") == "user"), "")
        correction = replace_program(row["answer"], programs[0], context) if programs else None
        self.store.wrong(self.last_id, note=text[:500], correction=correction)
        return ("Marked the last answer wrong" + (", with your program as the correction." if programs else
                                                  ". Show the right program to have it learned."))
