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
3. the statement says nothing the evidence does not: every content word of it is a word of the evidence, or one
   of the fixed template words the rules phrase statements with ("likes", "lives", "their", ...); and, when the
   statement asserts a relation the rules can name -- like/dislike, want/avoid, an ordered "A over B" -- the
   evidence must carry that same polarity and order, not just its nouns, a negation word's reach running to the
   next punctuation mark as in Pang, Lee & Vaithyanathan's negation tagging for sentiment words (arXiv:cs/0205070,
   sec. 6.1); a relation the rules cannot confirm this way is refused, never admitted;
4. it is not a secret or an identifier (passwords, keys, card and account numbers, long digit strings, e-mail
   addresses, links), which dawnr does not remember on its own; the person can still pin a note;
5. a model's proposal in a session that read outside text is refused outright: once untrusted text is in the
   context, what the model proposes may be the page speaking (Beurer-Kellner et al., arXiv:2506.08837, as the
   harness's taint rule reads it), and writing lasting memory is a consequential act.

The episode, a dated summary of the session, is built from counts and a fixed vocabulary plus keywords from the
person's own speech, never from a sentence of anyone's: a tool's output cannot reach it at all, and neither the
assistant's words nor a tool name the model made up (only names the harness's registry holds are kept).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
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

    def said_first(self, evidence: str) -> bool:
        """The person said `evidence` (in the speaking part of a message they typed) before anything else in the
        session had said it. Linear in the transcript: outside text only grows, so it is enough to find where it
        first held the evidence."""
        ev = norm(evidence)
        if not ev:
            return False
        speakable, person, outside = self._normed()
        first = next((k for k, o in enumerate(outside) if ev in o), len(outside) + 1)
        return any(before <= first and ev in said and ev in typed
                   for said, typed, before in zip(speakable, person, self.before))

    def says(self, evidence: str) -> bool:
        ev = norm(evidence)
        return bool(ev) and any(ev in s for s in self._normed()[0])


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
        for pattern, make, statement, slot, conf, check in _RULES:
            m = pattern.match(clause)
            if not m:
                continue
            x, k = m.group("x").strip(), (m.groupdict().get("k") or "").lower().strip()
            if make == "forget":
                words = [t for t in terms(x) if t not in PRONOUNS]
                return ForgetRequest(words, clause) if words else None
            if check == "raw":
                obj = x.strip(" .!?")
                if not obj or len(obj.split()) > 24:
                    return None
            else:
                obj = _object(x)
                if obj is None:
                    return None
                if check == "name" and not NAME.fullmatch(obj):
                    return None
                if check == "identity" and obj.split()[0].lower() in HEDGES:
                    return None
            kind = make
            if make == "remember":
                kind = "preference" if obj.lower().startswith("to ") else "fact"
            text = statement.format(x=third_person(obj), k=k)
            slot_name = slot.format(k=k, key=_key(obj)) if slot else None
            return Proposal(kind, text, clause, slot_name, conf, "rules")
        return None


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


# ---------------------------------------------------- grounding: the relation, not only its nouns --

# A shared noun is not a shared claim: "I like cats" and "I dislike cats" (or a proposal that swaps "prefers tea
# over coffee" to "prefers coffee over tea") share every content word once "likes"/"dislikes"/"prefers" are
# dropped as the rules' own phrasing, so a bag-of-words check alone admits the opposite of what was said. Pang,
# Lee & Vaithyanathan (arXiv:cs/0205070, sec. 6.1, read 2026-09-27) tag every word from a negation cue ("not",
# "isn't", "didn't", ...) up to the next punctuation mark, because a cue's reach is the clause, not the next
# token ("don't even slightly like" still negates "like"); that scope rule is reused here for a narrower,
# deterministic question than their trained classifier answered: for the small set of relations the rules phrase
# statements with, does the evidence carry the same polarity, and, for an ordered "A over B", the same order.
# Nothing here resolves a relation it cannot name: a family whose cue is absent, or whose polarity or order
# cannot be confirmed on the evidence side, makes grounded() refuse rather than guess (fail closed).
NEGATION = re.compile(r"\b(?:not|never|no|none|without|"
                      r"don'?t|do\s+not|dont|doesn'?t|does\s+not|doesnt|didn'?t|did\s+not|didnt|"
                      r"isn'?t|is\s+not|isnt|aren'?t|are\s+not|arent|wasn'?t|was\s+not|wasnt|"
                      r"weren'?t|were\s+not|werent|won'?t|will\s+not|wont|"
                      r"can'?t|cannot|can\s+not|cant|couldn'?t|could\s+not|couldnt|"
                      r"wouldn'?t|would\s+not|wouldnt|shouldn'?t|should\s+not|shouldnt)\b", re.I)
CLAUSE_END = re.compile(r"[.!?;,:]")
PREFER_ORDER = re.compile(
    r"\b(?:prefers?\s+(?P<a1>.+?)|(?:would\s+)?rather\s+(?P<a2>.+?))\s+"
    r"\b(?:over|to|than|instead\s+of|ahead\s+of|before)\b\s+(?P<b>.+)$", re.I)

# (positive cue, negative cue) per polarity-bearing family. "want" excludes the two fixed templates that use the
# bare word without expressing a want/avoid preference ("wants to be called {x}", "wants dawnr to {k} {x}"), so
# it only fires on a preference phrased this way, rule-based or a model's.
_POLARITY_RULES = (
    (re.compile(r"\b(?:likes?|liked|liking|loves?|loved|loving|enjoys?|enjoyed|enjoying|adores?|adored|adoring|"
               r"fond|fan)\b", re.I),
     re.compile(r"\b(?:dislikes?|disliked|disliking|hates?|hated|hating|detests?|detested|detesting|"
               r"can(?:'|no)?t stand|cannot stand|couldn'?t stand)\b", re.I)),
    (re.compile(r"\b(?:wants?|wanted|wanting)\b(?!\s+(?:to\s+be\s+called|dawnr)\b)", re.I),
     re.compile(r"\b(?:avoids?|avoided|avoiding)\b", re.I)),
)


def _negation_scopes(text: str) -> list[tuple[int, int]]:
    """Spans a negation cue covers: from just after the cue to the next punctuation mark, or the end of `text`
    when there is none (Pang, Lee & Vaithyanathan, arXiv:cs/0205070, sec. 6.1)."""
    scopes = []
    for m in NEGATION.finditer(text):
        stop = CLAUSE_END.search(text, m.end())
        scopes.append((m.end(), stop.start() if stop else len(text)))
    return scopes


def _side_polarity(text: str, pos_re: re.Pattern, neg_re: re.Pattern) -> bool | None:
    """True/False: `text` asserts this family's positive/negative sense once negation is accounted for. None:
    neither cue occurs, or the occurrences disagree (a plain cue and a negated one for the same family) -- either
    way this is not a sense the caller may treat as settled."""
    scopes = _negation_scopes(text)
    senses = {sense != any(a <= m.start() < b for a, b in scopes)
              for sense, pattern in ((True, pos_re), (False, neg_re)) for m in pattern.finditer(text)}
    return senses.pop() if len(senses) == 1 else None


def _ordered(text: str, evidence: str) -> bool | None:
    """None: `text` makes no ordered preference claim (no "A over/to/than B" shape). True/False: whether
    `evidence` has the same shape with the statement's A-words on its A side and B-words on its B side -- not
    just present somewhere in it, so a swapped "coffee over tea" cannot borrow a real "tea over coffee"'s shared
    nouns."""
    tm = PREFER_ORDER.search(text)
    if not tm:
        return None
    em = PREFER_ORDER.search(evidence)
    if not em:
        return False
    ta = {t for t in terms(tm.group("a1") or tm.group("a2")) if t not in PRONOUNS}
    tb = {t for t in terms(tm.group("b")) if t not in PRONOUNS}
    ea = {t for t in terms(em.group("a1") or em.group("a2")) if t not in PRONOUNS}
    eb = {t for t in terms(em.group("b")) if t not in PRONOUNS}
    return bool(ta) and bool(tb) and ta <= ea and tb <= eb


def _relation_ok(text: str, evidence: str) -> bool:
    """The statement's own relation -- an order, and each family's polarity -- is the one the evidence gives,
    for every relation `text` asserts that this module can name."""
    if _ordered(text, evidence) is False:
        return False
    for pos_re, neg_re in _POLARITY_RULES:
        want = _side_polarity(text, pos_re, neg_re)
        if want is not None and _side_polarity(evidence, pos_re, neg_re) != want:
            return False
    return True


def grounded(text: str, evidence: str) -> bool:
    """Every content word of the statement is a word of the evidence or of the rules' own phrasing, and, for
    every relation this module can name (like/dislike, want/avoid, an ordered "A over B"), the evidence's own
    polarity and order agree with the statement's: shared nouns are necessary, never sufficient."""
    if not set(terms(text)) - TEMPLATE <= set(terms(evidence)):
        return False
    return _relation_ok(text, evidence)


def admit(p: Proposal, view: SessionView) -> tuple[bool, str]:
    """(stored?, why not): the gate in the module docstring, rule by rule."""
    if p.kind not in ("fact", "preference"):
        return False, f"a session can add facts and preferences, not {p.kind!r}"
    if p.origin not in ("rules", "model"):
        return False, f"proposals come from rules or a model, not {p.origin!r}"
    text, evidence = clean_text(p.text, 10_000), clean_text(p.evidence, 10_000)
    if not text or len(text) > MAX_TEXT[p.kind]:
        return False, "the statement is empty or too long"
    if not evidence or len(evidence) > MAX_EVIDENCE:
        return False, "the evidence is empty or too long"
    if p.origin == "model" and view.tainted:
        return False, "this session read outside text, so a model's proposal waits for the person to make it"
    if not view.says(evidence):
        return False, "the evidence is not the person's own words in this session"
    if not view.said_first(evidence):
        return False, "the evidence was in text that did not come from the person before they said it"
    if not grounded(text, evidence):
        return False, "the statement says more than the person's words"
    if sensitive(text) or sensitive(evidence):
        return False, "it looks like a secret, an identifier or a link, which dawnr does not remember on its own"
    return True, ""


# ---------------------------------------------------------------- update --

@dataclass
class Report:
    session: str = ""
    added: list = field(default_factory=list)        # records added
    updated: list = field(default_factory=list)      # records whose statement a newer one in its slot replaced
    reinforced: list = field(default_factory=list)   # ids said again in a later session
    forgotten: list = field(default_factory=list)    # ids the person asked, in the session, to forget
    rejected: list = field(default_factory=list)     # (statement, why) for every proposal the gate refused
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
        if self.episode and self.episode_new:
            bits.append(f"session noted as {self.episode['id']}")
        return f"memory{who}: " + "; ".join(bits) if bits else ""


def _apply(store: MemoryStore, p: Proposal, session_id: str, now: float | None, report: Report,
           same_kind: list[dict]) -> None:
    """Mem0's update step, keyed by slot: the same statement again is NONE (heard again, once per session), a
    new statement in a stored slot is UPDATE (the newer words win), anything else is ADD. `same_kind` is the
    person's records of this kind, read once per session and kept up to date here."""
    stamp = fmt_time(now)
    target = next((r for r in same_kind if norm(r["text"]) == norm(p.text)), None)
    if target is None and p.slot:
        target = next((r for r in same_kind if r.get("slot") == p.slot), None)
    if target is None:
        record = store.add(p.kind, p.text, origin=p.origin, confidence=p.confidence, now=now, slot=p.slot,
                           evidence=p.evidence, source_session=session_id)
        same_kind.append(record)
        report.added.append(record)
        return
    if norm(target["text"]) == norm(p.text):
        # a hand-edited record may hold anything in these fields: read them defensively
        sessions = [s for s in target.get("sessions") or [] if isinstance(s, str)] \
            if isinstance(target.get("sessions"), list) else []
        if session_id not in sessions and target.get("source_session") != session_id:
            seen = target.get("seen") if isinstance(target.get("seen"), int) else 1
            target.update(sessions=(sessions + [session_id])[-MAX_SESSIONS:], seen=seen + 1, last_seen=stamp,
                          updated=stamp)
            if target.get("origin") != "person":
                target["confidence"] = round(min(0.99, 1.0 - (1.0 - confidence_of(target)) * 0.5), 3)
            store.put(target)
            report.reinforced.append(target["id"])
        return
    if target.get("origin") == "person" and p.origin == "model":
        report.rejected.append((p.text, "the person wrote this one themselves; a model does not overwrite it"))
        return
    target.update(text=clean_text(p.text, MAX_TEXT[p.kind]), evidence=clean_text(p.evidence, MAX_EVIDENCE),
                  source_session=session_id, sessions=[session_id], confidence=round(float(p.confidence), 3),
                  origin=p.origin, last_seen=stamp, updated=stamp, seen=1)
    store.put(target)
    report.updated.append(target)


def _names(request: ForgetRequest, text: str, slot: str | None) -> bool:
    """Does a "forget that ..." name this statement: are all its words in the statement or its slot?"""
    return set(request.words) <= set(terms(text)) | set(terms(slot or ""))


def _forget(store: MemoryStore, request: ForgetRequest, report: Report, existing: dict[str, list]) -> None:
    """The person asked, in their own words, to forget something: every fact or preference holding all its words."""
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
    # In the order said: the person's last word per slot (or per statement) wins, a "forget that" drops what this
    # session said before it, and a statement after a "forget that" naming it withdraws the forgetting.
    chosen: dict = {}
    forgets: list[ForgetRequest] = []
    for item in items:
        if isinstance(item, ForgetRequest):
            if item.origin != "rules":
                report.rejected.append(("forget " + " ".join(item.words), "only the person's own words ask to forget"))
            elif not view.said_first(item.evidence):
                report.rejected.append(("forget " + " ".join(item.words), "not the person's own words"))
            else:
                chosen = {k: p for k, p in chosen.items() if not _names(item, p.text, p.slot)}
                forgets.append(item)
            continue
        if not isinstance(item, Proposal):
            continue
        ok, why = admit(item, view)
        if not ok:
            report.rejected.append((item.text, why))
            continue
        forgets = [f for f in forgets if not _names(f, item.text, item.slot)]
        key = (item.kind, item.slot) if item.slot else (item.kind, norm(item.text))
        chosen.pop(key, None)
        chosen[key] = item
    existing = {kind: store.records((kind,)) for kind in ("fact", "preference")}
    for item in chosen.values():
        _apply(store, item, session_id, now, report, existing[item.kind])
    for request in forgets:
        _forget(store, request, report, existing)
    said = [i.evidence for i in items if isinstance(i, (Proposal, ForgetRequest))]
    _episode(store, view, session_id, known_tools, now, report, skip=said)
    return report
