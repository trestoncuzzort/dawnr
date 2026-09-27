"""extract.py: what a finished session adds to a person's memory, and the gate every addition passes.

Mem0 (Chhikara et al., arXiv:2504.19413) splits long-term memory into extraction (candidate memories from the
conversation) and update (each candidate against what is stored: ADD, UPDATE, DELETE or NONE), and its
user-memory prompt tells the extracting model to "GENERATE FACTS SOLELY BASED ON THE USER'S MESSAGES"
(github.com/mem0ai/mem0, mem0/configs/prompts.py, USER_MEMORY_EXTRACTION_PROMPT, read 2026-09-27). dawnr keeps
the split, and turns that sentence from an instruction a model may ignore into a rule the code enforces, because
it is the rule an attacker needs broken: SpAIware (embracethered.com, 2024) put instructions from a web page into
ChatGPT's long-term memory through its memory tool, and they ran in every later chat; MINJA (Dong et al.,
arXiv:2503.03704) plants records in an agent's memory through queries alone. Mem0's own later "additive" prompt
extracts from assistant messages and from documents the user shares; that is the channel refused here.

Who proposes. RuleProposer now: deterministic patterns over the person's own sentences ("my name is", "I live in",
"I prefer", "remember that", "from now on", ...). A model later: anything with propose(view) -> [Proposal], or
proposals_from_json() over a model's {"memories": [...]} output. Nothing a proposer returns is stored until it
passes admit():

1. its evidence is the person's own words, verbatim (whitespace and case aside), in a message they typed this
   session -- and in the part of it that is them speaking, not a fenced block, a quoted line, text in quotation
   marks, a t program, an Example line or a paste longer than MAX_MESSAGE characters;
2. in at least one message where they said it, nothing that did not come from the person had said it before:
   tool and harness outputs, trusted or not, recalled memory, the assistant's own words, the harness's index,
   the pasted parts of their own messages. A sentence the person copied from a page, or typed because the
   assistant told them to, is the page's sentence; an assistant repeating the person afterwards changes nothing;
3. the statement is one the enumerated patterns make, read whole from the person's own words, and it fails
   closed: a sentence of theirs that holds the evidence must be read to its end by the patterns, every clause of
   it, with no question mark and no negation outside the patterns' own words; one of those clauses, inside the
   evidence, must make exactly this statement (the same relation and polarity, the same object word for word and
   in order); a model's kind and slot must be the pattern's. Anything else is refused as "cannot ground: <why>",
   true statements in phrasing no pattern reads included (grounded(); the person can still pin a note). And it is
   decided over everything the person said in the session, never one clause: when any two statements the patterns
   read anywhere in it are about the same thing and are not the same statement, nothing about that thing is
   admitted, and the report names it ("contradiction: <thing>", with the two readings);
4. it is not a secret or an identifier (passwords, keys, card and account numbers, long digit strings, e-mail
   addresses, links), which dawnr does not remember on its own; the person can still pin a note;
5. a model's proposal in a session that read outside text is refused outright: once untrusted text is in the
   context, what the model proposes may be the page speaking (Beurer-Kellner et al., arXiv:2506.08837, as the
   harness's taint rule reads it), and writing lasting memory is a consequential act.

What passes is then set against what is stored (_apply): the same statement again is heard again, and one that
disagrees with a stored record about the same thing does not replace it; it waits as a pending question for the
person (store kind "pending", never recalled), unless they said "forget that ..." or used correct.

The episode, a dated summary of the session, is built from counts and a fixed vocabulary plus keywords from the
person's own speech, never from a sentence of anyone's: a tool's output cannot reach it at all, and neither the
assistant's words nor a tool name the model made up (only names the harness's registry holds are kept).
"""
from __future__ import annotations

import functools
import json
import re
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Iterable

from .retrieval import STOP_WORDS, confidence_of, s_stem, terms
from .store import MAX_EVIDENCE, MAX_SESSIONS, MAX_TEXT, SESSION, MemoryStore, clean_text, fmt_time

MAX_MESSAGE = 2000            # a longer message is taken as a paste, not as the person speaking
MAX_CLAUSE = 240
MAX_OBJECT_WORDS = 8
MAX_KEYWORDS = 8
MAX_PROPOSALS = 64

FENCE = re.compile(r"```.*?(?:```|\Z)", re.S)
QUOTED = re.compile(r"\"[^\"\n]{0,2000}\"|“[^”\n]{0,2000}”|«[^»\n]{0,2000}»")
LINE_OUT = re.compile(r"^(?:\s*>|\s*t\s+\d+\s*$|\s*example:| {4}|\t)", re.I)
CODEISH = re.compile(r"[{}]|:=|==|->|=>|</?[A-Za-z][\w-]*>")
SENTENCE_END = re.compile(r"[.!?;]+(?=\s|$)|\n")      # a stop inside "example.org" or "3.5" ends nothing
# where a sentence ends for grounding, and so how far a negation reaches: not at a comma, a colon, a semicolon or
# the dots of an ellipsis ("I like cats... not." is one sentence)
SENTENCE_STOP = re.compile(r"(?<!\.)\.(?=\s|$)|[!?]+(?=\s|$)|\n")
JOIN = re.compile(r",?\s+(?:and|but|also)\s+(?=(?:i|i'm|im|i've|i'd|my|please|remember|don'?t|do not|keep in mind|"
                  r"call me|from now on|always|never)\b)", re.I)
FILLER = re.compile(r"^(?:(?:hi|hello|hey|well|also|oh|ok|okay|so|btw|by the way|actually|anyway|and|but|fyi|"
                    r"yes|yeah|yep|sure|right|no|just so you know|for the record|to be clear|dawnr)\b[\s,!:-]*)+",
                    re.I)
OFF_RECORD = re.compile(r"\b(?:off the record|(?:don'?t|do not) (?:remember|save|store|keep|record) (?:this|any of "
                        r"this|anything|this conversation|this session|this chat)\b)", re.I)
SENSITIVE = re.compile(r"\b(?:pass(?:word|phrase|code)s?|pins?|pin (?:code|number)|social security|ssn|credit card|"
                       r"debit card|card number|cvv|cvc|iban|routing number|account number|sort code|api[ _-]?keys?|"
                       r"secrets?|tokens?|private keys?|seed phrase|recovery (?:phrase|code)s?|2fa|otp|"
                       r"one[- ]time code)\b", re.I)
LONG_NUMBER = re.compile(r"(?:\d[\s.-]?){7,}\d")
EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}")
LINKISH = re.compile(r"https?:|www\.|\b[\w-]+\.(?:com|org|net|io|dev|ai|co|app|xyz|ru|cn|uk|de)\b|[/\\]{2}", re.I)
NAME = re.compile(r"[^\W\d_][\w'.-]*(?:\s+[^\W\d_][\w'.-]*){0,3}")
TOOL_NAME = re.compile(r"\s*([A-Za-z0-9_.-]{1,128})")
WORD = re.compile(r"[^\W\d_]{3,24}")              # letters only: no digits, so no codes or numbers
CUT = re.compile(r"\s+(?:because|since|so that|so|but|which|who|although|though|when|whenever|if|unless|"
                 r"and then)\b|[,:(]", re.I)
TRAILING = re.compile(r"(?:\s+(?:now|currently|these days|nowadays|at the moment|right now|anymore|any more|too|"
                      r"as well|again|actually|though))+$", re.I)

SHIFT = [(re.compile(p, re.I), r) for p, r in (
    (r"\bi am\b", "they are"), (r"\bi'm\b", "they're"), (r"\bim\b", "they're"), (r"\bi've\b", "they've"),
    (r"\bi'd\b", "they'd"), (r"\bi'll\b", "they'll"), (r"\bi was\b", "they were"), (r"\bi\b", "they"),
    (r"\bmyself\b", "themselves"), (r"\bmine\b", "theirs"), (r"\bmy\b", "their"), (r"\bme\b", "them"),
    (r"\byourself\b", "dawnr"), (r"\byours\b", "dawnr's"), (r"\byour\b", "dawnr's"), (r"\byou\b", "dawnr"))]

# the only words a statement may carry that its evidence does not: the rules' own phrasing and the pronoun shift
# (grounding now compares a statement with the patterns' own, word for word; this names that vocabulary for tests)
TEMPLATE = frozenset(terms(
    "name is are wants want to be called lives live from works work learning working building likes like dislikes "
    "dislike prefers prefer would rather favorite favourite fan their they them theirs themselves they're they've "
    "they'd they'll were dawnr dawnr's asked remember now always never"))
PRONOUNS = frozenset(terms(
    "i me my mine myself you your yours yourself we us our ours im i'm i've i'd i'll am was about all everything "
    "anything what said told again please"))
HEDGES = frozenset("bit little lot tad while moment second sec minute fan big huge great sure".split())
KEYWORD_STOP = STOP_WORDS | frozenset("""
    i me my mine myself you your yours yourself we us our ours he him his she her hers they them their theirs what
    which who whom whose when where why how can could would should will shall may might must do does did done doing
    have has had having am is are was were be been being get gets got make makes made want wants wanted need needs
    needed please thanks thank hello hey okay yes yeah also just like know think let lets write writes wrote
    written tell told give gave show help try tried use using used one two three some any all more most much many
    very really thing things something anything everything nothing way ways here now then than there about above
    after again against because before below between both down during each few from further off once only other
    out over own same too under until while dawnr going gonna wanna sure actually maybe bit little lot tad""".split())


# ----------------------------------------------------------------- what was said --

def norm(text) -> str:
    """For comparing words as said: case folded, curly apostrophes straightened, whitespace runs one space."""
    return " ".join(str(text or "").replace("’", "'").casefold().split())


def split_speech(message: str) -> tuple[str, list[str]]:
    """(the part of a person's message that is them speaking, the parts that are not).

    Not speaking: a message longer than MAX_MESSAGE (a paste), fenced blocks, quoted lines, indented lines, t
    program heads, Example lines, lines that look like code, and text in quotation marks. What is cut out is
    returned, because it is outside text: a sentence the person pasted is the source's sentence, not theirs."""
    if len(message) > MAX_MESSAGE:
        return "", [message]
    removed: list[str] = []

    def cut(m) -> str:
        removed.append(m.group(0))
        return "\n"
    text = FENCE.sub(cut, message)
    kept = []
    for ln in text.split("\n"):
        if LINE_OUT.match(ln) or CODEISH.search(ln):
            removed.append(ln)
        else:
            kept.append(ln)
    text = QUOTED.sub(lambda m: (removed.append(m.group(0)), " ")[1], "\n".join(kept))
    return text.replace("’", "'"), [r for r in removed if r.strip()]


def clauses(text: str) -> list[str]:
    """Sentences, split again before "and I" / "but my", with leading fillers ("hi,", "btw") removed."""
    out = []
    for sentence in SENTENCE_END.split(text):
        for piece in JOIN.split(sentence):
            piece = FILLER.sub("", piece.strip()).strip(" ,:-")
            if 2 <= len(piece) <= MAX_CLAUSE:
                out.append(piece)
    return out


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) of each sentence of `text`, its end mark included (SENTENCE_STOP)."""
    spans, start = [], 0
    for m in SENTENCE_STOP.finditer(text):
        spans.append((start, m.end()))
        start = m.end()
    spans.append((start, len(text)))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def third_person(text: str) -> str:
    for pattern, replacement in SHIFT:
        text = pattern.sub(replacement, text)
    return text


def sensitive(text: str) -> bool:
    return bool(SENSITIVE.search(text) or LONG_NUMBER.search(text) or EMAIL.search(text) or LINKISH.search(text))


def _failing(verdict: str) -> bool:
    """A t tool verdict with a failing line (dawnr_harness/checker.py's failing(), restated to keep this module
    free of the harness)."""
    for ln in verdict.splitlines():
        ln = ln.strip()
        if ln.startswith(("parses: no", "well formed: no")):
            return True
        if ln.startswith("example ") and not ln.endswith(": pass"):
            return True
    return False


@dataclass
class SessionView:
    """A finished session as extraction reads it: the person's words apart from everyone else's."""
    person: list[str] = field(default_factory=list)       # each message the person typed (the index removed)
    speakable: list[str] = field(default_factory=list)    # the part of each that is them speaking
    outside: list[str] = field(default_factory=list)      # every text that did not come from the person, in order
    before: list[int] = field(default_factory=list)       # per message: how much of `outside` came before it
    calls: list[str] = field(default_factory=list)        # the tools called, in order ("t" for the t tool)
    last_check: bool | None = None                        # did the last t verdict pass (None: no t call)
    tainted: bool = False                                 # outside text entered the session

    @classmethod
    def of(cls, transcript, *, index: str = "", tainted: bool = False) -> "SessionView":
        messages = transcript.get("messages") if isinstance(transcript, dict) else transcript
        view = cls(tainted=bool(tainted))
        if index:
            view.outside.append(index)
        for message in messages or []:
            if not isinstance(message, dict):
                continue
            role, content = message.get("role"), message.get("content")
            if role == "user" and isinstance(content, str):
                text = content
                if index and text.startswith(index):
                    text = text[len(index):]
                elif text.startswith("Tools:\n"):              # an index the caller did not name
                    head, _, text = text.partition("\n\n")
                    view.outside.append(head)
                said, removed = split_speech(text)
                view.outside.extend(removed)                   # a paste precedes the words around it
                view.person.append(text)
                view.speakable.append(said)
                view.before.append(len(view.outside))
            elif role == "assistant" and isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict) or not isinstance(part.get("text"), str):
                        continue
                    view.outside.append(part["text"])
                    kind = part.get("type")
                    if kind == "t":
                        view.calls.append("t")
                    elif kind == "tool":
                        m = TOOL_NAME.match(part["text"])
                        view.calls.append(m.group(1) if m else "?")
                    elif kind == "t_output":
                        view.last_check = not _failing(part["text"])
                    if part.get("untrusted"):
                        view.tainted = True
            elif isinstance(content, str):
                view.outside.append(content)                   # the assistant's words, or anything else
        return view

    def _normed(self) -> tuple[list[str], list[str], list[str]]:
        if getattr(self, "_norms", None) is None:
            self._norms = ([norm(s) for s in self.speakable], [norm(p) for p in self.person],
                           [norm(o) for o in self.outside])
        return self._norms

    def _theirs(self, ev: str) -> list[int]:
        """The messages in whose speaking part the person said `ev` (normalised) before anything else in the
        session had said it. Linear in the transcript: outside text only grows, so it is enough to find where it
        first held `ev`."""
        speakable, person, outside = self._normed()
        first = next((k for k, o in enumerate(outside) if ev in o), len(outside) + 1)
        return [i for i, (said, typed, before) in enumerate(zip(speakable, person, self.before))
                if before <= first and ev in said and ev in typed]

    def said_first(self, evidence: str) -> bool:
        """The person said `evidence` (in the speaking part of a message they typed) before anything else in the
        session had said it."""
        ev = norm(evidence)
        return bool(ev) and bool(self._theirs(ev))

    def contexts(self, evidence: str) -> list[str]:
        """Each whole sentence of the person's own speech that holds `evidence`, in the messages where they said it
        first: what grounding reads, so that a quote cannot leave out the words around it ("I like cats" out of "I
        never said I like cats."). A quote the person's text does not hold word for word has no context."""
        ev = norm(evidence)
        if not ev:
            return []
        find = re.compile(r"\s+".join(map(re.escape, ev.split())), re.I)
        out = []
        for i in self._theirs(ev):
            text = self.speakable[i]
            spans = sentence_spans(text)
            for m in find.finditer(text):
                out.extend(text[a:b] for a, b in spans if a < m.end() and m.start() < b)
        return out

    def says(self, evidence: str) -> bool:
        ev = norm(evidence)
        return bool(ev) and any(ev in s for s in self._normed()[0])

    def claims(self) -> list:
        """Every statement the patterns read anywhere in what the person said this session (read_claims)."""
        if getattr(self, "_claims", None) is None:
            self._claims = read_claims(self.speakable)
        return self._claims

    def contradictions(self) -> list:
        """Every two of those that disagree about one thing (find_contradictions): grounding's whole utterance."""
        if getattr(self, "_contradictions", None) is None:
            self._contradictions = find_contradictions(self.claims())
        return self._contradictions


# ------------------------------------------------------------- proposals --

@dataclass
class Proposal:
    kind: str                       # "fact" or "preference"
    text: str                       # the statement, about the person in the third person ("lives in Lisbon")
    evidence: str                   # the person's own words that establish it, verbatim
    slot: str | None = None         # what it is about; a newer statement in the same slot replaces an older one
    confidence: float = 0.5
    origin: str = "rules"           # "rules" or "model"


@dataclass
class ForgetRequest:
    words: list                     # the content words of what to forget
    evidence: str
    origin: str = "rules"


@dataclass(frozen=True)
class Reading:
    """What one clause says under the enumerated pattern that read it (_read)."""
    kind: str
    text: str                       # the statement: the pattern's template with its {k} and {x} filled in
    slot: str | None
    confidence: float
    template: str                   # "likes {x}", "wants dawnr to {k} {x}", ...
    k: str                          # the pattern's own choice word ("always", "at", "a"), or ""
    x: str                          # the object, in the third person, word for word
    whole: bool                     # the pattern read the clause to its end: nothing after the object was cut off
                                    # but end marks and the trailing words the rules drop ("now", "too", ...)


def _object(x: str) -> str | None:
    """The object of a pattern, cut at the clause's first conjunction or comma, or None when it is not crisp."""
    x = TRAILING.sub("", CUT.split(x, 1)[0].strip(" .!?'\"()[]"))
    words = x.split()
    if not words or len(words) > MAX_OBJECT_WORDS:
        return None
    if len(words) == 1 and words[0].lower() in {"it", "this", "that", "them", "these", "those", "something",
                                                  "anything", "everything", "nothing", "stuff", "things"}:
        return None
    return x


def _key(x: str) -> str:
    return " ".join(sorted({t for t in terms(x) if t not in PRONOUNS}))[:60]


# (pattern, what it makes, statement, slot, confidence, how the object is checked)
_RULES = [(re.compile(p, re.I), make, statement, slot, conf, check) for p, make, statement, slot, conf, check in (
    (r"^(?:please\s+)?forget\s+(?:that\s+|about\s+|what\s+i\s+said\s+about\s+)?(?P<x>.+)$",
     "forget", "", None, 0.0, "raw"),
    (r"^(?:please\s+remember(?:\s+that)?|(?:please\s+)?(?:don'?t forget|do not forget|keep in mind)\s+that)"
     r"\s+(?P<x>.+)$",
     "remember", "asked dawnr to remember: {x}", None, 0.85, "raw"),
    (r"^remember\s+that\s+(?P<x>.+)$", "remember", "asked dawnr to remember: {x}", None, 0.6, "raw"),
    (r"^my name(?:'s|\s+is)\s+(?P<x>.+)$", "fact", "name is {x}", "name", 0.9, "name"),
    (r"^(?:i am|i'm|im)\s+called\s+(?P<x>.+)$", "fact", "name is {x}", "name", 0.9, "name"),
    (r"^(?:please\s+)?call me\s+(?P<x>.+)$", "fact", "wants to be called {x}", "called", 0.9, "name"),
    (r"^(?:i|we)\s+(?:currently\s+|now\s+)?live\s+in\s+(?P<x>.+)$", "fact", "lives in {x}", "location", 0.8, "object"),
    (r"^(?:i am|i'm|im)\s+(?:currently\s+|now\s+)?(?:based|living)\s+in\s+(?P<x>.+)$",
     "fact", "lives in {x}", "location", 0.8, "object"),
    (r"^(?:i am|i'm|im|i come)\s+from\s+(?P<x>.+)$", "fact", "is from {x}", "from", 0.7, "object"),
    (r"^i\s+(?:currently\s+|now\s+)?work\s+(?P<k>as|at|for|on|in|with)\s+(?P<x>.+)$",
     "fact", "works {k} {x}", "work {k}", 0.75, "object"),
    (r"^(?:i am|i'm|im)\s+(?:a\s+)?(?:big\s+|huge\s+|great\s+)?fan\s+of\s+(?P<x>.+)$",
     "preference", "is a fan of {x}", "like {key}", 0.6, "object"),
    (r"^(?:i am|i'm|im)\s+(?:currently\s+|now\s+)?(?:learning|studying)\s+(?P<x>.+)$",
     "fact", "is learning {x}", "learning {key}", 0.7, "object"),
    (r"^(?:i am|i'm|im)\s+(?:currently\s+|now\s+)?(?:working on|building)\s+(?P<x>.+)$",
     "fact", "is working on {x}", "project {key}", 0.5, "object"),
    (r"^(?:i am|i'm|im)\s+(?P<k>a|an)\s+(?P<x>.+)$", "fact", "is {k} {x}", None, 0.5, "identity"),
    (r"^i\s+(?:really\s+|just\s+)?(?:don'?t|do not|dont)\s+(?:really\s+)?(?:like|enjoy|love)\s+(?P<x>.+)$",
     "preference", "dislikes {x}", "like {key}", 0.6, "object"),
    (r"^i\s+(?:really\s+)?(?:hate|dislike|detest|can'?t stand|cannot stand)\s+(?P<x>.+)$",
     "preference", "dislikes {x}", "like {key}", 0.6, "object"),
    (r"^i\s+(?:really\s+|also\s+|just\s+|do\s+)?(?:like|love|enjoy|adore)\s+(?P<x>.+)$",
     "preference", "likes {x}", "like {key}", 0.6, "object"),
    (r"^i(?:'d|\s+would)?\s+(?:really\s+)?prefer\s+(?P<x>.+)$", "preference", "prefers {x}", "prefer {key}", 0.7,
     "object"),
    (r"^i(?:'d|\s+would)\s+rather\s+(?P<x>.+)$", "preference", "would rather {x}", "rather {key}", 0.6, "object"),
    (r"^my\s+(?:favorite|favourite)\s+(?P<k>[a-z][a-z ]{0,30}?)\s+(?:is|are)\s+(?P<x>.+)$",
     "preference", "their favorite {k} is {x}", "favorite {k}", 0.8, "object"),
    (r"^(?:from now on|going forward|in (?:the )?future),?\s+(?P<x>.+)$",
     "preference", "from now on: {x}", "style {key}", 0.75, "object"),
    (r"^(?:please\s+)?(?P<k>always|never)\s+(?P<x>(?:answer|reply|respond|write|use|explain|give|show|keep|call|"
     r"talk|be|put|include|add|format|comment|ask|check|prove|test)\b.*)$",
     "preference", "wants dawnr to {k} {x}", "style {key}", 0.7, "object"),
    (r"^my\s+(?P<k>timezone|time zone|pronouns|native language|first language|mother tongue|job title|job|role|"
     r"title|occupation|profession|hometown|home town|team|editor|operating system|os|shell|major|field|main goal|"
     r"goal|birthday|level)\s+(?:is|are)\s+(?P<x>.+)$", "fact", "their {k} is {x}", "my {k}", 0.7, "object"),
)]
# Relations grounding can read that the rules do not propose on their own (so "I want a function that sorts" is
# not made a memory), because a model's proposal may state them.
_GROUNDING_ONLY = [(re.compile(p, re.I), make, statement, slot, conf, check) for p, make, statement, slot, conf, check
                   in ((r"^i\s+(?:really\s+|also\s+|just\s+|do\s+)?want\s+(?P<x>.+)$",
                        "preference", "wants {x}", "want {key}", 0.6, "object"),
                       (r"^i\s+(?:really\s+|also\s+|just\s+|do\s+)?avoid\s+(?P<x>.+)$",
                        "preference", "avoids {x}", "want {key}", 0.6, "object"))]
_READS = _RULES + _GROUNDING_ONLY


def _reading(clause: str, rules=_RULES):
    """(what `clause` says under the first pattern of `rules` that matches it, where its object lies in `clause`):
    (a Reading or a ForgetRequest, (start, end)), or None when none matches or the first that does finds no crisp
    object."""
    for pattern, make, statement, slot, conf, check in rules:
        m = pattern.match(clause)
        if not m:
            continue
        raw = m.group("x")
        x, k = raw.strip(), (m.groupdict().get("k") or "").lower().strip()
        at = m.start("x") + len(raw) - len(raw.lstrip())
        if make == "forget":
            words = [t for t in terms(x) if t not in PRONOUNS]
            return (ForgetRequest(words, clause), (at, at + len(x))) if words else None
        if check == "raw":
            obj = x.strip(" .!?")
            if not obj or len(obj.split()) > 24:
                return None
            whole = True
        else:
            obj = _object(x)
            if obj is None:
                return None
            if check == "name" and not NAME.fullmatch(obj):
                return None
            if check == "identity" and obj.split()[0].lower() in HEDGES:
                return None
            whole = obj == TRAILING.sub("", x.strip(" .!?'\"()[]"))     # _object cut nothing but what is dropped
        kind = make
        if make == "remember":
            kind = "preference" if obj.lower().startswith("to ") else "fact"
        said = third_person(obj)
        start = at + x.find(obj)                  # obj is x trimmed and cut: it begins at x's first kept character
        return (Reading(kind, statement.format(x=said, k=k), slot.format(k=k, key=_key(obj)) if slot else None,
                        conf, statement, k, said, whole), (start, start + len(obj)))
    return None


def _read(clause: str, rules=_RULES):
    """What `clause` says under the first pattern of `rules` that matches it: a Reading, a ForgetRequest, or None
    when none matches or the first that does finds no crisp object."""
    got = _reading(clause, rules)
    return got[0] if got else None


class RuleProposer:
    """Deterministic rules over the part of the person's own messages that is them speaking."""
    origin = "rules"

    def propose(self, view: SessionView) -> list:
        out: list = []
        for said in view.speakable:
            for clause in clauses(said):
                item = self._one(clause)
                if item is not None:
                    out.append(item)
        return out[:MAX_PROPOSALS]

    @staticmethod
    def _one(clause: str):
        got = _read(clause)
        if isinstance(got, Reading):
            return Proposal(got.kind, got.text, clause, got.slot, got.confidence, "rules")
        return got


def proposals_from_json(text: str, origin: str = "model") -> tuple[list[Proposal], list[str]]:
    """A model's proposed memories, from {"memories": [{"kind", "text", "evidence", "slot"?, "confidence"?}]} (Mem0's
    {"facts": [...]} with the evidence each must carry); what cannot be read is named, not guessed at."""
    errors: list[str] = []
    try:
        data = json.loads(text)
    except ValueError as e:
        return [], [f"not JSON: {e}"]
    items = data.get("memories") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return [], ['expected {"memories": [...]}']
    out = []
    for i, item in enumerate(items[:MAX_PROPOSALS]):
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) for k in ("kind", "text", "evidence")):
            errors.append(f"memory {i}: needs string kind, text and evidence")
            continue
        slot = item.get("slot") if isinstance(item.get("slot"), str) else None
        try:
            conf = min(0.7, max(0.0, float(item.get("confidence", 0.5))))
        except (TypeError, ValueError):
            conf = 0.5
        out.append(Proposal(item["kind"], item["text"], item["evidence"], slot, conf, origin))
    if len(items) > MAX_PROPOSALS:
        errors.append(f"only the first {MAX_PROPOSALS} proposals were read")
    return out, errors


# --------------------------------------------------------- grounding: read whole, or refuse --

# Round 1 named the relations it knew (like/dislike, want/avoid, an ordered "A over B"), checked their polarity with
# a negation's reach cut at the next comma, and let every other phrasing fall through to a bag-of-words check. So a
# phrasing its lists missed was admitted: "I don't, honestly, like cats." grounded "likes cats", and "I prefer tea
# above coffee." grounded "prefers coffee above tea". That is the failure Saltzer and Schroeder's fail-safe defaults
# warn of ("The Protection of Information in Computer Systems", 1975, sec. I.A.3(b),
# web.mit.edu/Saltzer/www/publications/protection/Basic.html, read 2026-09-27): "a design or implementation mistake
# in a mechanism that explicitly excludes access tends to fail by allowing access, a failure which may go unnoticed
# in normal use". Grounding is now allowlist validation as OWASP's Input Validation Cheat Sheet puts it
# (cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html, read 2026-09-27): "defining exactly
# what IS authorized, and by definition, everything else is not authorized", each pattern "covering the whole input
# string (^...$)", a denylist only ever a supplement. The allowlist is the rules' own patterns plus want and avoid
# (_READS). A statement is admitted only when
#   1. it is in one of the patterns' statement forms ("likes {x}", "prefers {x}", "lives in {x}", ...);
#   2. a sentence of the person's own that holds the evidence reads whole: no question mark in it, every clause of
#      it read by a pattern to its end (nothing cut off after an object but end marks and the trailing words the
#      rules drop, "now", "too", ...), and no negation in a filler before a clause ("No, I like cats"), the one
#      place a negation word could stand outside the patterns' own words. A negation therefore reaches its whole
#      sentence, never stopping at a comma: a sentence with any clause the patterns cannot read grounds nothing;
#   3. one of those clauses lies inside the quoted evidence and makes exactly this statement: the same pattern, so
#      the same relation and polarity ("likes" is not "dislikes", "always" is not "never"), and the same object word
#      for word and in order, so no list of order words ("over", "above", "more than", ...) is needed or can be
#      incomplete: "prefers tea above coffee" is admitted from "I prefer tea above coffee" and its swap is not.
# Anything else is "cannot ground: <why>", true statements in phrasing no pattern reads included; the person can
# pin those as notes. A reason never holds the proposal's words, which may be a refused secret.
NEGATION = re.compile(r"\b(?:not|never|no|none|without|"
                      r"don'?t|do\s+not|dont|doesn'?t|does\s+not|doesnt|didn'?t|did\s+not|didnt|"
                      r"isn'?t|is\s+not|isnt|aren'?t|are\s+not|arent|wasn'?t|was\s+not|wasnt|"
                      r"weren'?t|were\s+not|werent|won'?t|will\s+not|wont|"
                      r"can'?t|cannot|can\s+not|cant|couldn'?t|could\s+not|couldnt|"
                      r"wouldn'?t|would\s+not|wouldnt|shouldn'?t|should\s+not|shouldnt)\b", re.I)


def _form(template: str) -> re.Pattern:
    """A statement template as a pattern over whole statements: its own words exactly, {k} and {x} any words."""
    return re.compile("".join({"{k}": r"(?P<k>.+?)", "{x}": r"(?P<x>.+)"}.get(part, re.escape(part))
                              for part in re.split(r"(\{[kx]\})", template)), re.I)


_FORMS = [(_form(t), t) for t in dict.fromkeys(statement for _p, make, statement, *_rest in _READS
                                                if make != "forget")]
_OPPOSITE = {"likes {x}": "dislikes {x}", "is a fan of {x}": "dislikes {x}", "dislikes {x}": "likes {x}",
             "wants {x}": "avoids {x}", "avoids {x}": "wants {x}"}


def _canonical(statement: str) -> str:
    return norm(statement).rstrip(".").rstrip()


def _opposite(r: Reading) -> str:
    """The statement with the other polarity, if the reading's pattern has one ("likes x" / "dislikes x")."""
    if r.template == "wants dawnr to {k} {x}":
        return r.template.format(k="never" if r.k == "always" else "always", x=r.x)
    flip = _OPPOSITE.get(r.template)
    return flip.format(x=r.x) if flip else ""


def _read_sentence(sentence: str) -> tuple[list, str]:
    """([(clause, Reading), ...], "") when the patterns read all of one sentence, else ([], why not)."""
    if "?" in sentence:
        return [], "the person's sentence is a question"
    got = []
    for part in SENTENCE_END.split(sentence):
        for piece in JOIN.split(part):
            piece = piece.strip()
            filler = FILLER.match(piece)
            lead = filler.group(0) if filler else ""
            if NEGATION.search(lead):
                return [], "a negation in the person's sentence is outside the patterns' words"
            clause = piece[len(lead):].strip(" ,:-")
            if not clause:
                continue
            reading = _read(clause, _READS) if len(clause) <= MAX_CLAUSE else None
            if not isinstance(reading, Reading) or not reading.whole:
                return [], "the person's sentence has words no pattern reads"
            got.append((clause, reading))
    return got, ""


def _slot(slot) -> str | None:
    return clean_text(slot or "", 80).lower() or None          # as the store keeps it


# ------------------------------------------------------- the whole utterance: contradictions --

# Round 3. grounded() read each clause on its own, so an utterance that says two things about one object grounded
# either of them cleanly: "I like cats, and I don't like cats." admitted "likes cats" and "dislikes cats" alike (and
# end_session kept the last one and said nothing), and "I prefer tea, and I prefer coffee over tea." brought the
# order swap back through a second clause. Grounding is now decided over everything the person said in the session,
# every sentence and every clause of every message. The statements the patterns read anywhere in it are collected
# -- at every word, so a clause after a comma or an "although" counts, and so does one in a sentence the gate would
# not admit ("No, I like cats") -- and two of them about the same thing that are not the same statement are a
# contradiction: nothing about that thing is admitted from the session, and the report names it.
#
# "The same thing" follows de Marneffe, Rafferty and Manning ("Finding Contradictions in Text", ACL 2008,
# aclanthology.org/P08-1118, read 2026-09-27): two texts contradict only when they are about the same event, and
# "compatible noun phrases between sentences are assumed to be coreferent in the absence of clear countervailing
# evidence". Two statements are about the same thing when their objects share a word, word for word (not a stem, not
# a synonym; stop words and pronouns aside), when they fill the same slot (the person's location, their name, "like
# cat"), or when their slots name the same object as the rules key it ("cat" in "want cat" and "like cat", so a
# plural does not hide it). Their typology also says why every difference counts: antonymy and negation come from
# closed sets of words, but a contradiction of structure ("Jacques Santer succeeded Jacques Delors" / "Delors
# succeeded Santer") or of lexical content needs a model of what sentences mean, which word patterns are not. So the
# gate does not try to tell a contradiction from a compatible pair: two different statements about one thing are a
# contradiction unless they are a pair on _COMPATIBLE. The opposite-pair table (_OPPOSITE) only labels a polarity
# conflict in the report; it decides nothing, so a pair missing from it cannot let a contradiction through, and a
# pair missing from _COMPATIBLE costs a true memory, never a false one. A statement also says what is said inside its
# object ("Remember that I like cats" says "likes cats", so it agrees with "I like cats" anywhere in the session),
# and a statement inside what the person asks to forget is not one they make.

_SHIFTED = frozenset(w for _pattern, replacement in SHIFT for w in replacement.split())
_OWN = frozenset("i me my mine myself you your yours yourself we us our ours im i'm i've i'd i'll am".split())
_NOT_A_TOPIC = STOP_WORDS | _OWN | _SHIFTED        # words that name nothing: Lucene's stop set and the pronouns
_TOPIC_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*")
_WORD_START = re.compile(r"(?<![\w'])\w")
_COMPATIBLE = (frozenset({("likes {x}", ""), ("is a fan of {x}", "")}),
               frozenset({("lives in {x}", ""), ("is from {x}", "")}),
               frozenset({("from now on: {x}", ""), ("wants dawnr to {k} {x}", "always")}))
_KEYED = tuple(sorted({slot[:-len("{key}")] for _p, _m, _s, slot, _c, _k in _READS if slot and slot.endswith(" {key}")},
                      key=len, reverse=True))      # "like ", "prefer ", ...: a slot named by its object's words
_SPECIFIC = sorted(_FORMS, key=lambda form: -len(re.sub(r"\{[kx]\}", "", form[1])))


@dataclass(frozen=True)
class Claim:
    """A statement the patterns read somewhere in what the person said (read_claims)."""
    reading: Reading
    message: int                    # which of the person's messages
    start: int                      # where its clause starts in that message's speaking part
    topics: frozenset               # what it is about (_topics), and what the statements inside its object are about
    says: frozenset                 # its class (_class) and those of the statements said inside its object: "Remember
    #                                 that I like cats" says "likes cats" too, and is about what that is about


@dataclass(frozen=True)
class Contradiction:
    """Two statements the person made about one thing that are not the same statement."""
    object: str                     # the thing, as the reason names it: "cats", "answer briefly", "location"
    first: Reading
    second: Reading
    kind: str                       # "polarity" (_OPPOSITE), "order" (the same words), else "relation"
    topics: frozenset               # what the two share


def _topics(x: str, slot) -> frozenset:
    """What a statement is about: each word of its object, word for word, less the words that name nothing (the
    whole object when that leaves none); its slot; and, for a slot named by its object ("like cat", "want cat"),
    that object as the rules key it, so "wants a cat" and "dislikes cats" are about one thing across relations."""
    said = norm(x)
    got = {("word", w) for w in _TOPIC_WORD.findall(said) if w not in _NOT_A_TOPIC} or {("object", said)}
    slot = _slot(slot)
    if slot:
        got.add(("slot", slot))
        family = next((f for f in _KEYED if slot.startswith(f)), None)
        if family and slot[len(family):]:
            got.add(("key", slot[len(family):]))
    return frozenset(got)


def _pieces(text: str) -> list[tuple[int, int]]:
    """(start, end) of each clause of `text` as grounding splits it: sentences (SENTENCE_END), then "and I", "but
    my", ... (JOIN)."""
    out, start = [], 0
    for end, after in [(m.start(), m.end()) for m in SENTENCE_END.finditer(text)] + [(len(text), len(text))]:
        a = start
        for m in JOIN.finditer(text, start, end):
            out.append((a, m.start()))
            a = m.end()
        out.append((a, end))
        start = after
    return [(a, b) for a, b in out if text[a:b].strip()]


def _read_everywhere(text: str) -> list[tuple[int, Reading, tuple]]:
    """(where its clause starts, the Reading, where its object lies) for every statement a pattern reads beginning
    at any word of `text`, except one inside the object of a "forget that ...": the person asks to drop that, they do
    not say it is so."""
    found, dropped = [], []
    for a, b in _pieces(text):
        piece = text[a:b]
        for m in _WORD_START.finditer(piece):
            got = _reading(piece[m.start():], _READS)
            if got is not None:
                item, (s, e) = got
                at = a + m.start()
                (dropped if isinstance(item, ForgetRequest) else found).append((at, item, (at + s, at + e)))
    return [f for f in found if not any(s <= f[0] < e for _at, _item, (s, e) in dropped)]


def _class(r: Reading) -> tuple:
    """Statements of one class say one thing: the same statement, or a pair on _COMPATIBLE about the same object."""
    for n, pair in enumerate(_COMPATIBLE):
        if (r.template, r.k) in pair:
            return ("pair", n, norm(r.x))
    return ("statement", _canonical(r.text))


def read_claims(texts: Iterable[str]) -> list[Claim]:
    """Every statement the patterns read anywhere in `texts` (the person's messages, their speaking parts), in the
    order said. One that looks like a secret is left out: it is refused as a secret whatever else is said, and a
    reason must never name its words."""
    out = []
    for i, text in enumerate(texts):
        found = [f for f in _read_everywhere(text) if not sensitive(f[1].text)]
        for start, reading, (s, e) in found:
            inside = [inner for at, inner, _where in found if s <= at < e]
            out.append(Claim(reading, i, start, _topics(reading.x, reading.slot).union(
                *(_topics(r.x, r.slot) for r in inside)), frozenset(map(_class, [reading] + inside))))
    return out


def _conflict(a: Reading, b: Reading) -> str:
    """How two statements about one thing disagree, for the report; it decides nothing."""
    if _canonical(b.text) == _canonical(_opposite(a)) or _canonical(a.text) == _canonical(_opposite(b)):
        return "polarity"
    if (a.template, a.k) == (b.template, b.k) and sorted(norm(a.x).split()) == sorted(norm(b.x).split()):
        return "order"
    return "relation"


def _named(shared: frozenset, r: Reading) -> str:
    """The thing two statements share, as a reason names it: the shared words in the order `r` says them, else the
    whole object, the object as the rules key it ("cat"), or the slot ("location")."""
    words = list(dict.fromkeys(w for w in _TOPIC_WORD.findall(norm(r.x)) if ("word", w) in shared))
    if words:
        return " ".join(words)
    for kind in ("object", "key", "slot"):
        values = sorted(value for k, value in shared if k == kind)
        if values:
            return values[0]
    return norm(r.x)


def find_contradictions(claims: list[Claim]) -> list[Contradiction]:
    """For each thing the person said something about, the first two statements about it (in the order said) that
    say nothing in common (_class, with what each says inside its object), in the order said. That is enough to know
    every thing contradicted -- two statements that disagree about a thing are in its list, so its list holds a pair
    that disagrees -- and to name each, and it costs a long session what it says about each thing, not the square of
    everything it says."""
    by_topic: dict = {}
    for i, claim in enumerate(claims):
        for topic in claim.topics:
            by_topic.setdefault(topic, []).append(i)
    pairs = set()
    for held in by_topic.values():
        if len(held) < 2 or frozenset.intersection(*(claims[i].says for i in held)):
            continue                                # said one way throughout: nothing disagrees
        pair = next(((i, j) for n, i in enumerate(held) for j in held[n + 1:]
                     if not claims[i].says & claims[j].says), None)
        if pair is not None:
            pairs.add(pair)
    out = []
    for i, j in sorted(pairs):
        a, b = claims[i].reading, claims[j].reading
        shared = claims[i].topics & claims[j].topics
        out.append(Contradiction(_named(shared, a), a, b, _conflict(a, b), shared))
    return out


_UNSHIFT = [(re.compile(p, re.I), r) for p, r in (           # SHIFT backwards, to read a stored object again
    (r"\bthey are\b", "I am"), (r"\bthey're\b", "I'm"), (r"\bthey've\b", "I've"), (r"\bthey'd\b", "I'd"),
    (r"\bthey'll\b", "I'll"), (r"\bthey were\b", "I was"), (r"\bthemselves\b", "myself"), (r"\btheirs\b", "mine"),
    (r"\btheir\b", "my"), (r"\bthem\b", "me"), (r"\bthey\b", "I"), (r"\bdawnr's\b", "your"), (r"\bdawnr\b", "you"))]


def _as_reading(text: str, slot=None) -> Reading:
    """A stored statement as the pattern that most narrowly makes it would have read it; one no pattern makes (a
    person's own correction) is about every word in it."""
    statement = _canonical(text)
    for form, template in _SPECIFIC:
        m = form.fullmatch(statement)
        if m:
            return Reading("", text, slot, 0.0, template, m.groupdict().get("k") or "", m.group("x"), True)
    return Reading("", text, slot, 0.0, "", "", text, True)


def _inside(reading: Reading) -> list[Reading]:
    """The statements said inside a statement's object, read back in the first person ("asked dawnr to remember:
    their birthday is May 3" holds "their birthday is May 3")."""
    inner = reading.x
    for pattern, replacement in _UNSHIFT:
        inner = pattern.sub(replacement, inner)
    return [r for _at, r, _where in _read_everywhere(inner)]


def _about(reading: Reading) -> frozenset:
    """What a statement is about, the statements inside its object included (a Claim's topics)."""
    return _topics(reading.x, reading.slot).union(*(_topics(r.x, r.slot) for r in _inside(reading)))


@functools.lru_cache(maxsize=4096)          # a pure function of its arguments, asked once per stored record per item
def _stated(text: str, slot=None) -> tuple[Reading, frozenset, frozenset]:
    """A stored or proposed statement as the contradiction rule reads it, like a Claim: its Reading, what it is about,
    and what it says. Reading its object back in the first person can only add to both, and it adds only statements
    its own words make: a wrong guess (a "they" that meant other people) asks about more, and lets through unasked
    only a statement those words already hold."""
    reading = _as_reading(text, slot)
    inside = _inside(reading)
    return (reading, _about(reading), frozenset(map(_class, [reading] + inside)))


def _disagree(a: tuple, b: tuple) -> bool:
    """The contradiction rule for two statements (_stated): about the same thing, and saying nothing in common."""
    return bool(a[1] & b[1]) and not a[2] & b[2]


def grounded(text: str, evidence: str, contexts: Iterable[str] | None = None,
             conflicts: list[Contradiction] | None = None) -> tuple[Reading | None, str]:
    """(the Reading that grounds the statement `text`, "") or (None, why not): the rules in the two comments above.
    `contexts` are the person's own sentences holding `evidence` (SessionView.contexts); without them the evidence's
    own sentences are read, which is only as good as the quote. `conflicts` are the contradictions in everything the
    person said (SessionView.contradictions); without them, those in the contexts."""
    statement = _canonical(text)
    if not any(form.fullmatch(statement) for form, _template in _FORMS):
        return None, "cannot ground: the statement is not in a form the patterns make"
    contexts = list(contexts) if contexts is not None else [evidence[a:b] for a, b in sentence_spans(evidence)]
    quoted, readings, trouble = norm(evidence), [], ""
    for sentence in contexts:
        got, why = _read_sentence(sentence)
        trouble = trouble or why
        readings += [r for clause, r in got                      # a whole clause of the quote, not "cats" in "catsup"
                     if re.search(r"(?<!\w)" + re.escape(norm(clause)) + r"(?!\w)", quoted)]
    match = next((r for r in readings if _canonical(r.text) == statement), None)
    if match is None:
        if not readings:
            return None, "cannot ground: " + (trouble or "the quoted words hold no whole clause a pattern reads")
        if any(_canonical(_opposite(r)) == statement for r in readings):
            differs = "it reverses what they said"
        elif any(form.fullmatch(statement) for form, template in _FORMS
                 if template in {r.template for r in readings}):
            differs = "its words or their order are not theirs"
        else:
            differs = "they said something else"
        return None, f"cannot ground: the statement says more than the person's words ({differs})"
    about = _about(match)
    for c in (conflicts if conflicts is not None else find_contradictions(read_claims(contexts))):
        if c.topics & about:
            return None, f"contradiction: {c.object}"
    return match, ""


def admit(p: Proposal, view: SessionView) -> tuple[bool, str]:
    """(stored?, why not): the gate in the module docstring, rule by rule."""
    ok, why, _reading = _admit(p, view)
    return ok, why


def _admit(p: Proposal, view: SessionView) -> tuple[bool, str, Reading | None]:
    """admit(), and the Reading that grounds what it admits."""
    if p.kind not in ("fact", "preference"):
        return False, f"a session can add facts and preferences, not {p.kind!r}", None
    if p.origin not in ("rules", "model"):
        return False, f"proposals come from rules or a model, not {p.origin!r}", None
    text, evidence = clean_text(p.text, 10_000), clean_text(p.evidence, 10_000)
    if not text or len(text) > MAX_TEXT[p.kind]:
        return False, "the statement is empty or too long", None
    if not evidence or len(evidence) > MAX_EVIDENCE:
        return False, "the evidence is empty or too long", None
    if p.origin == "model" and view.tainted:
        return False, "this session read outside text, so a model's proposal waits for the person to make it", None
    if not view.says(evidence):
        return False, "the evidence is not the person's own words in this session", None
    if not view.said_first(evidence):
        return False, "the evidence was in text that did not come from the person before they said it", None
    reading, why = grounded(text, evidence, view.contexts(evidence), view.contradictions())
    if reading is None:
        return False, why, None
    if p.kind != reading.kind:
        return False, f"cannot ground: the person's words make it a {reading.kind}, not a {p.kind}", None
    if p.slot is not None and _slot(p.slot) != _slot(reading.slot):
        return False, "cannot ground: the person's words give it another slot", None
    if sensitive(text) or sensitive(evidence):
        return False, "it looks like a secret, an identifier or a link, which dawnr does not remember on its own", None
    return True, "", reading


# ---------------------------------------------------------------- update --

# A statement that disagrees with what is stored about the same thing (the contradiction rule above: a shared object
# word or slot, and neither the same statement nor a compatible pair) does not replace it. Zep invalidates the older
# fact and "consistently prioritizes new information" (Rasmussen et al., arXiv:2501.13956, sec. 2.2.3), and Mem0's
# update prompt deletes a contradicted memory ("If the retrieved facts contain information that contradicts the
# information present in the memory, then you have to delete it", mem0/configs/prompts.py,
# DEFAULT_UPDATE_MEMORY_PROMPT, read 2026-09-27): in both the newer statement wins, judged by a model. dawnr has no
# model to judge with, and a newer statement can be a misreading or words the person was steered into, so it takes
# the shape of Wikidata's single-value constraint instead (wikidata.org/wiki/Help:Property_constraints_portal/
# Single_value, read 2026-09-27): values that disagree "should not be removed", and a person decides. The stored
# record stays as it is, and the new statement is kept as a pending question (store kind "pending": never recalled,
# not a fact) that the person answers in the Memory window or with `python locallm/dawnr_memory answer`. They can
# also say it explicitly: "forget that ..." in the session removes the stored record first, and correct rewrites it.


class Rejected(tuple):
    """One refused proposal as (statement, why), which is how report.rejected is read. A contradiction or a conflict
    with a stored record also carries the statements that disagree (`readings`) and how they do (`kind`)."""

    def __new__(cls, statement: str, why: str, readings=(), kind: str = ""):
        self = super().__new__(cls, (statement, why))
        self.readings, self.kind = tuple(readings), kind
        return self


@dataclass
class Report:
    session: str = ""
    added: list = field(default_factory=list)        # records added
    updated: list = field(default_factory=list)      # records a compatible newer statement in their slot reworded
    reinforced: list = field(default_factory=list)   # ids said again in a later session
    forgotten: list = field(default_factory=list)    # ids the person asked, in the session, to forget
    rejected: list = field(default_factory=list)     # Rejected (statement, why): every proposal the gate or the
    #                                                  update refused, and every contradiction in what was said
    asked: list = field(default_factory=list)        # pending questions: statements that disagree with a record
    episode: dict | None = None
    episode_new: bool = False                        # False when a checkpoint only brought the episode up to date
    skipped: str = ""                                # why nothing at all was remembered

    def summary(self, person: str = "") -> str:
        """What happened, for the person (never for the model)."""
        who = f" for {person}" if person else ""
        if self.skipped:
            return f"memory{who}: nothing kept from this session ({self.skipped})"
        bits = []
        if self.added:
            bits.append("remembered " + "; ".join(f"{r['id']} {r['kind']}: {r['text']}" for r in self.added))
        if self.updated:
            bits.append("updated " + "; ".join(f"{r['id']}: {r['text']}" for r in self.updated))
        if self.reinforced:
            bits.append(f"heard again {len(self.reinforced)}")
        if self.forgotten:
            bits.append("forgot " + ", ".join(self.forgotten) + " as asked")
        if self.rejected:
            bits.append(f"did not keep {len(self.rejected)} ({'; '.join(sorted({w for _t, w in self.rejected}))})")
        if self.asked:
            bits.append("asks which is right: " + "; ".join(f"{q['id']} {q['text']}" for q in self.asked)
                        + " (the Memory window, or python locallm/dawnr_memory pending)")
        if self.episode and self.episode_new:
            bits.append(f"session noted as {self.episode['id']}")
        return f"memory{who}: " + "; ".join(bits) if bits else ""


def _sessions(record: dict) -> list[str]:
    """A record's sessions; a hand-edited record may hold anything in the field, so it is read defensively."""
    sessions = record.get("sessions")
    return [s for s in sessions if isinstance(s, str)] if isinstance(sessions, list) else []


def _apply(store: MemoryStore, p: Proposal, session_id: str, now: float | None, report: Report,
           current: dict[str, list]) -> None:
    """Mem0's update step, keyed by slot, less its newer-wins: the same statement again is NONE (heard again, once
    per session); one that disagrees with a stored record about the same thing waits as a pending question and
    changes nothing (the comment above); a compatible one in a stored slot is UPDATE ("is a fan of jazz" rewords
    "likes jazz"); anything else is ADD. `current` holds the person's facts, preferences and pending questions,
    read once per session and kept up to date here."""
    stamp = fmt_time(now)
    same_kind = current[p.kind]
    target = next((r for r in same_kind if norm(r["text"]) == norm(p.text)), None)
    if target is not None:
        sessions = _sessions(target)
        if session_id not in sessions and target.get("source_session") != session_id:
            seen = target.get("seen") if isinstance(target.get("seen"), int) else 1
            target.update(sessions=(sessions + [session_id])[-MAX_SESSIONS:], seen=seen + 1, last_seen=stamp,
                          updated=stamp)
            if target.get("origin") != "person":
                target["confidence"] = round(min(0.99, 1.0 - (1.0 - confidence_of(target)) * 0.5), 3)
            store.put(target)
            report.reinforced.append(target["id"])
        return
    new = _stated(p.text, _slot(p.slot))
    against = [r for r in current["fact"] + current["preference"]
               if _disagree(new, _stated(r["text"], _slot(r.get("slot"))))]         # a hand-edited slot is text
    if against and p.origin == "model" and any(r.get("origin") == "person" for r in against):
        report.rejected.append(Rejected(p.text, "the person wrote this one themselves; a model does not overwrite it"))
        return
    if against:
        ids = [r["id"] for r in against]
        report.rejected.append(Rejected(p.text, "conflicts with stored record " + ", ".join(ids),
                                        (p.text, *(r["text"] for r in against)),
                                        _conflict(new[0], _as_reading(against[0]["text"], against[0].get("slot")))))
        _ask(store, p, ids, session_id, now, report, current["pending"])
        return
    target = next((r for r in same_kind if p.slot and r.get("slot") == _slot(p.slot)), None)
    if target is None:
        record = store.add(p.kind, p.text, origin=p.origin, confidence=p.confidence, now=now, slot=p.slot,
                           evidence=p.evidence, source_session=session_id)
        same_kind.append(record)
        report.added.append(record)
        return
    if target.get("origin") == "person" and p.origin == "model":
        report.rejected.append(Rejected(p.text, "the person wrote this one themselves; a model does not overwrite it"))
        return
    target.update(text=clean_text(p.text, MAX_TEXT[p.kind]), evidence=clean_text(p.evidence, MAX_EVIDENCE),
                  source_session=session_id, sessions=[session_id], confidence=round(float(p.confidence), 3),
                  origin=p.origin, last_seen=stamp, updated=stamp, seen=1)
    store.put(target)
    report.updated.append(target)


def _ask(store: MemoryStore, p: Proposal, ids: list[str], session_id: str, now: float | None, report: Report,
         questions: list[dict]) -> None:
    """Keep `p` as a pending question for the person, one per statement however often it is said: a later session
    saying it again adds itself to the question, a checkpoint of the same session changes nothing."""
    same = next((q for q in questions if norm(q["text"]) == norm(p.text) and q.get("becomes") == p.kind), None)
    if same is None:
        question = store.add("pending", p.text, origin=p.origin, confidence=p.confidence, now=now, slot=p.slot,
                             evidence=p.evidence, source_session=session_id, becomes=p.kind, conflicts_with=ids)
        questions.append(question)
        report.asked.append(question)
        return
    sessions, stamp = _sessions(same), fmt_time(now)
    fresh = session_id not in sessions and same.get("source_session") != session_id
    if fresh:
        seen = same.get("seen") if isinstance(same.get("seen"), int) else 1
        same.update(sessions=(sessions + [session_id])[-MAX_SESSIONS:], seen=seen + 1, last_seen=stamp,
                    evidence=clean_text(p.evidence, MAX_EVIDENCE))
        report.asked.append(same)
    if fresh or same.get("conflicts_with") != ids:
        same.update(conflicts_with=ids, updated=stamp)
        store.put(same)


def _names(request: ForgetRequest, text: str, slot: str | None) -> bool:
    """Does a "forget that ..." name this statement: are all its words in the statement or its slot?"""
    return set(request.words) <= set(terms(text)) | set(terms(slot or ""))


def _forget(store: MemoryStore, request: ForgetRequest, report: Report, existing: dict[str, list]) -> None:
    """The person asked, in their own words, to forget something: every fact, preference or pending question
    holding all its words."""
    for records in existing.values():
        for record in list(records):
            if _names(request, record["text"], record.get("slot")):
                records.remove(record)
                if store.forget(record["id"]):
                    report.forgotten.append(record["id"])


def keywords(texts: Iterable[str], limit: int = MAX_KEYWORDS, skip: Iterable[str] = (),
             theirs=lambda clause: True) -> list[str]:
    """The person's most used content words, most frequent first (ties: first said first). Clauses in `skip`
    (those the rules made facts of), clauses that look like a secret and clauses that are not `theirs` (outside
    text said them first: the person retyped a page) are not counted at all."""
    skip = {norm(c) for c in skip}
    counts: Counter = Counter()
    first: dict[str, int] = {}
    forms: dict[str, str] = {}
    position = 0
    for clause in (c for text in texts for c in clauses(text)):
        if norm(clause) in skip or sensitive(clause) or not theirs(clause):
            continue
        for word in WORD.findall(clause):
            low = word.lower()
            if low in KEYWORD_STOP or sensitive(low):
                continue
            stem = s_stem(low)
            counts[stem] += 1
            if stem not in first:
                first[stem], forms[stem] = position, low
            position += 1
    return [forms[s] for s in sorted(counts, key=lambda s: (-counts[s], first[s]))[:limit]]


def episode_text(view: SessionView, known_tools: Iterable[str] = (), skip: Iterable[str] = ()) -> tuple[str, dict]:
    """The episode's words and its tool counts: counts, a fixed vocabulary and the person's keywords only."""
    known = set(known_tools) | {"t"}
    tools = Counter(name if name in known else "another tool" for name in view.calls)
    n = len(view.person)
    parts = [f"{n} message{'s' if n != 1 else ''} from the person"]
    topics = keywords(view.speakable, skip=skip, theirs=view.said_first)
    if topics:
        parts.append("topics " + ", ".join(topics))
    if tools:
        parts.append("tools " + ", ".join(f"{name} x{count}" for name, count in tools.items()))
    if view.last_check is not None:
        parts.append(f"the last t check {'passed' if view.last_check else 'failed'}")
    if view.tainted:
        parts.append("outside text was read")
    return "; ".join(parts), dict(tools)


def _episode(store: MemoryStore, view: SessionView, session_id: str, known_tools, now, report: Report,
             skip: Iterable[str] = ()) -> None:
    text, tools = episode_text(view, known_tools, skip)
    check = None if view.last_check is None else ("passed" if view.last_check else "failed")
    for record in store.records(("episode",)):
        if record.get("session") == session_id:              # a checkpoint of a session already noted
            record.update(text=clean_text(text, MAX_TEXT["episode"]), turns=len(view.person), tools=tools,
                          check=check, tainted=view.tainted, updated=fmt_time(now))
            report.episode = store.put(record)
            return
    report.episode = store.add("episode", text, origin="rules", confidence=0.3, now=now, session=session_id,
                               date=fmt_time(now)[:10], turns=len(view.person), tools=tools, check=check,
                               tainted=view.tainted)
    report.episode_new = True


def end_session(store: MemoryStore, transcript, *, session_id: str, index: str = "", tainted: bool = False,
                known_tools: Iterable[str] = (), proposers=None, proposals: Iterable = (),
                now: float | None = None) -> Report:
    """Add what a finished session says about the person to their memory; the report says what and why not.

    Idempotent per session: running it again on the same session (a client that saves after every reply) updates
    that session's episode and hears nothing twice."""
    session_id = str(session_id or "")
    if not SESSION.fullmatch(session_id):
        raise ValueError(f"a session id is 1 to 64 of A-Za-z0-9_.-, not {session_id!r}")
    report = Report(session=session_id)
    if not store.settings()["remember"]:
        report.skipped = "remembering is switched off for this person"
        return report
    view = SessionView.of(transcript, index=index, tainted=tainted)
    if not any(p.strip() for p in view.person):
        report.skipped = "the person said nothing"
        return report
    if any(OFF_RECORD.search(s) for s in view.speakable):
        report.skipped = "the person asked for this session not to be remembered"
        return report
    items: list = []
    for proposer in (proposers if proposers is not None else (RuleProposer(),)):
        items.extend(proposer.propose(view))
    items.extend(proposals)
    # In the order said: a "forget that" drops what this session said before it, and the same words said after it
    # withdraw the forgetting. Two statements about one thing that disagree never both reach here (the gate refuses
    # everything about a thing the session contradicts), so the last word per slot is a rewording, not a reversal.
    chosen: dict = {}
    forgets: list[ForgetRequest] = []
    for item in items:
        if isinstance(item, ForgetRequest):
            if item.origin != "rules":
                report.rejected.append(Rejected("forget " + " ".join(item.words),
                                                "only the person's own words ask to forget"))
            elif not view.said_first(item.evidence):
                report.rejected.append(Rejected("forget " + " ".join(item.words), "not the person's own words"))
            else:
                chosen = {k: p for k, p in chosen.items() if not _names(item, p.text, p.slot)}
                forgets.append(item)
            continue
        if not isinstance(item, Proposal):
            continue
        ok, why, reading = _admit(item, view)
        if not ok:
            report.rejected.append(_refused(item.text, why, view))
            continue
        if item.slot is None and reading.slot is not None:
            item = replace(item, slot=reading.slot)          # a model that named no slot gets the pattern's
        if item.origin != "rules" and any(_names(f, item.text, item.slot) for f in forgets):
            # a model's proposals come after all the person's words, so one naming what the person asked to forget
            # (and did not say again after) is what they took back; it must not withdraw their forgetting
            report.rejected.append(Rejected(item.text, "the person asked, in this session, to forget it"))
            continue
        forgets = [f for f in forgets if not _names(f, item.text, None)]
        key = (item.kind, item.slot) if item.slot else (item.kind, norm(item.text))
        chosen.pop(key, None)
        chosen[key] = item
    _report_contradictions(view, report)
    current = {kind: store.records((kind,)) for kind in ("fact", "preference", "pending")}
    for request in forgets:             # first: what the person asked to forget is not current, so it asks nothing
        _forget(store, request, report, current)
    for item in chosen.values():
        _apply(store, item, session_id, now, report, current)
    said = [i.evidence for i in items if isinstance(i, (Proposal, ForgetRequest))]
    _episode(store, view, session_id, known_tools, now, report, skip=said)
    return report


def _refused(statement: str, why: str, view: SessionView) -> Rejected:
    """A refusal as the report keeps it; a contradiction carries its two readings."""
    c = next((c for c in view.contradictions() if why == f"contradiction: {c.object}"), None)
    return Rejected(statement, why, (c.first.text, c.second.text), c.kind) if c else Rejected(statement, why)


def _report_contradictions(view: SessionView, report: Report) -> None:
    """A contradiction is never silent: each thing the person said two things about is in report.rejected, even
    when nothing proposed a statement about it."""
    named = {why for _statement, why in report.rejected}
    for c in view.contradictions():
        why = f"contradiction: {c.object}"
        if why not in named:
            named.add(why)
            report.rejected.append(Rejected(c.first.text, why, (c.first.text, c.second.text), c.kind))
