"""retrieval.py: what dawnr is told about a person when a session starts, inside a token budget.

Generative Agents (Park et al., arXiv:2304.03442, section 4.1, read 2026-09-27) retrieve from a memory stream by
recency (an exponential decay), importance and relevance to the current situation, each min-max scaled to [0, 1]
and summed with every weight 1, and put "the top-ranked memories that fit within the language model's context
window" into the prompt. That is taken as it is, with three substitutions, each for a stated reason:

* relevance is Okapi BM25 against the person's first message, not embedding cosine similarity: it runs offline,
  in the standard library, with no model to embed with, and it explains itself (shared words). The scorer is
  rank_bm25's shape (github.com/dorianbrown/rank_bm25) with Lucene's BM25Similarity defaults and its idf, which
  never goes negative (k1 1.2, b 0.75, idf = ln(1 + (N - n + 0.5) / (n + 0.5)); lucene.apache.org,
  BM25Similarity), words are Lucene's EnglishAnalyzer stop set removed and its minimal plural stemmer
  (Harman's S-stemmer, EnglishMinimalStemmer) applied;
* importance is the confidence extraction gave the record (a person's own note or correction is 1.0), not a
  model's 1-to-10 rating: there is no model in the loop yet;
* recency decays from when the person last said it (last_seen), not from when it was last retrieved: recalling a
  memory must not keep it fresh on its own, or whatever was recalled once is recalled forever.

Pinned notes, which the person wrote, come first in the order they were written; the ranked records follow.
Packing is first fit in rank order: a record that does not fit is skipped and smaller ones after it may still
enter, and a record that fits is never displaced by a lower one. The budget covers the whole span, header and
the three chat tokens that frame it (<|output_start|><|memory|> ... <|output_end|>) included.

The default counter is the UTF-8 byte length. Under byte-level BPE every token covers at least one byte, and under
a character tokenizer every token is one character of at least one byte, so a span within B bytes is within B
tokens for either: a hook that does not know the model's tokenizer still keeps the budget. The engine, which
knows it, counts exactly when it renders the span (span.fit_lines).
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Callable

from .store import MemoryStore, clean_text, parse_time

TOKEN = re.compile(r"\w+")
# Lucene's EnglishAnalyzer.ENGLISH_STOP_WORDS_SET, word for word
STOP_WORDS = frozenset(("a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if", "in", "into", "is",
                        "it", "no", "not", "of", "on", "or", "such", "that", "the", "their", "then", "there",
                        "these", "they", "this", "to", "was", "will", "with"))
K1, B = 1.2, 0.75
HALF_LIFE_DAYS = 30.0
HEADER = "dawnr remembers from earlier sessions with this person:"
SPAN_TOKENS = 3                  # <|output_start|> <|memory|> ... <|output_end|>
MAX_LINE = 700


def s_stem(word: str) -> str:
    """Harman's S-stemmer as Lucene's EnglishMinimalStemmer writes it: plural endings only."""
    n = len(word)
    if n < 3 or word[-1] != "s":
        return word
    if word[-2] in "us":
        return word
    if word[-2] == "e":
        if n > 3 and word[-3] == "i" and word[-4] not in "ae":
            return word[:-3] + "y"
        if word[-3] in "iaoe":
            return word
    return word[:-1]


def terms(text) -> list[str]:
    """Lowercased word characters, stop words out, plurals folded: what BM25 compares."""
    return [s_stem(w) for w in TOKEN.findall(str(text or "").lower()) if w not in STOP_WORDS]


class BM25:
    """Okapi BM25 over a fixed list of tokenised documents."""

    def __init__(self, documents: list[list[str]], k1: float = K1, b: float = B):
        self.k1, self.b = k1, b
        self.freqs: list[dict[str, int]] = []
        df: dict[str, int] = {}
        for doc in documents:
            tf: dict[str, int] = {}
            for t in doc:
                tf[t] = tf.get(t, 0) + 1
            self.freqs.append(tf)
            for t in tf:
                df[t] = df.get(t, 0) + 1
        self.lengths = [len(d) for d in documents]
        self.n = len(documents)
        self.avgdl = sum(self.lengths) / self.n if self.n else 0.0
        self.idf = {t: math.log(1.0 + (self.n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        query = list(dict.fromkeys(query))          # a repeated word counts once
        out = []
        for tf, dl in zip(self.freqs, self.lengths):
            norm = self.k1 * (1.0 - self.b + self.b * (dl / self.avgdl if self.avgdl else 0.0))
            s = 0.0
            for q in query:
                f = tf.get(q)
                if f:
                    s += self.idf[q] * f * (self.k1 + 1.0) / (f + norm)
            out.append(s)
        return out


def byte_count(text: str) -> int:
    """UTF-8 bytes: never fewer than the tokens of byte-level BPE or a character tokenizer (module docstring)."""
    return len(text.encode("utf-8"))


@dataclass
class Recall:
    text: str = ""                                  # the span's text; "" when nothing is recalled
    ids: list = field(default_factory=list)         # the records in it, in order
    cost: int = 0                                   # tokens the span costs as counted, its three chat tokens included
    considered: int = 0                             # records there were
    left_out: int = 0                               # records that did not fit or were not asked for


def _seen(record: dict) -> float:
    for key in ("last_seen", "updated", "created"):
        t = parse_time(record.get(key))
        if t is not None:
            return t
    return 0.0


def _minmax(xs: list[float]) -> list[float]:
    lo, hi = min(xs), max(xs)
    if hi - lo <= 1e-12:
        return [0.0] * len(xs)
    return [(x - lo) / (hi - lo) for x in xs]


def rank(records: list[dict], query: str = "", *, now: float | None = None, half_life_days: float = HALF_LIFE_DAYS,
         weights=(1.0, 1.0, 1.0)) -> list[dict]:
    """Records in recall order: recency + importance + relevance, each min-max scaled (Generative Agents)."""
    records = list(records)
    if not records:
        return []
    now = time.time() if now is None else now
    relevance = BM25([terms(r.get("text", "")) for r in records]).scores(terms(query))
    recency = [0.5 ** (max(0.0, now - _seen(r)) / 86400.0 / max(half_life_days, 1e-9)) for r in records]
    importance = [float(r.get("confidence", 0.5) or 0.0) for r in records]
    w_rec, w_imp, w_rel = weights
    score = [w_rec * a + w_imp * b + w_rel * c
             for a, b, c in zip(_minmax(recency), _minmax(importance), _minmax(relevance))]
    order = sorted(range(len(records)), key=lambda i: (-score[i], -_seen(records[i]), records[i]["id"]))
    return [records[i] for i in order]


def line(record: dict) -> str:
    """One record as a line of the span. Every line starts with "- ", so none can begin like an Example line or
    any other line a tool reads by its start, and the record's text is one line by construction (clean_text)."""
    text = clean_text(record.get("text", ""), MAX_LINE)
    kind = record.get("kind")
    if kind == "note":
        return f"- note: {text}"
    if kind == "episode":
        return f"- session {str(record.get('date') or record.get('created') or '')[:10]}: {text}"
    said = str(record.get("last_seen") or record.get("updated") or record.get("created") or "")[:10]
    return f"- {kind} ({said}): {text}"


def recall(source, query: str = "", *, budget: int, count: Callable[[str], int] = byte_count,
           now: float | None = None, half_life_days: float = HALF_LIFE_DAYS, weights=(1.0, 1.0, 1.0)) -> Recall:
    """What to tell dawnr about a person at the start of a session, within `budget` tokens as `count` counts them.

    `source` is the person's MemoryStore (whose recall switch is honoured) or their records."""
    if isinstance(source, MemoryStore):
        if not source.settings()["recall"]:
            records = source.records()
            return Recall(considered=len(records), left_out=len(records))
        records = source.records()
    else:
        records = list(source)
    result = Recall(considered=len(records))
    notes = sorted((r for r in records if r.get("kind") == "note"), key=lambda r: (str(r.get("created", "")), r["id"]))
    others = rank([r for r in records if r.get("kind") != "note"], query, now=now, half_life_days=half_life_days,
                  weights=weights)
    lines = [HEADER]
    if budget > SPAN_TOKENS and count(HEADER) + SPAN_TOKENS <= budget:
        for record in notes + others:
            candidate = line(record)
            if count("\n".join(lines + [candidate])) + SPAN_TOKENS <= budget:
                lines.append(candidate)
                result.ids.append(record["id"])
    if result.ids:
        result.text = "\n".join(lines)
        result.cost = count(result.text) + SPAN_TOKENS
    result.left_out = len(records) - len(result.ids)
    return result


def fit_lines(text: str, budget: int, count: Callable[[str], int] = byte_count) -> str:
    """The longest run of whole lines from the start of `text` whose span fits `budget` as `count` counts it.

    How any SessionStart context (dawnr's recall, or what an operator's hook added) is held to the budget with the
    model's own tokenizer: recall puts lines in priority order, so dropping from the end drops the least wanted."""
    kept: list[str] = []
    for raw in str(text or "").splitlines():
        ln = clean_text(raw, MAX_LINE)
        if not ln:
            continue
        if count("\n".join(kept + [ln])) + SPAN_TOKENS > budget:
            break
        kept.append(ln)
    return "" if kept == [HEADER] else "\n".join(kept)       # a header with nothing under it says nothing
