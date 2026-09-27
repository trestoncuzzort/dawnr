"""bm25.py: Okapi BM25 ranking over an in-memory document set. Standard library only (re, math,
collections) -- this is the index dawnr_retrieval always has, offline, with no torch and no
third-party package (DAWNR-HARNESS.md: "the harness is standard-library Python 3.10+ ... starts
offline").

Formula and both constants from Perez-Iglesias, Perez-Aguera, Fresno & Feinstein, "Integrating the
Probabilistic Models BM25/BM25F into Lucene" (arXiv:0911.5046):

    idf(t)      = log((N - df(t) + 0.5) / (df(t) + 0.5))
    score(d, q) = sum over t in q of idf(t) * f(t, d) * (k1 + 1)
                  / (f(t, d) + k1 * (1 - b + b * |d| / avgdl))

f(t, d) is t's term frequency in document d, |d| the document's token count, avgdl the corpus's
mean token count, N the number of documents, df(t) the number of documents containing t. k1 and b
are the paper's own free parameters (it reports typical values k1~2, b~0.75); this module defaults
to k1=1.5 (the commonly deployed middle value between the paper's 2 and Lucene/Elasticsearch's
shipped 1.2) and b=0.75 (the paper's own number), both overridable per index. idf can go slightly
negative for a term appearing in more than half the documents -- the formula above, unmodified, not
a bug -- so such a term simply pulls a document's score down rather than up.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

_TOKEN = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word/identifier tokens. Keeps an identifier like square_nums as one token and
    splits on everything else, which suits this corpus's mix of English prose and t/code text
    equally without a language-specific stemmer or stopword list (neither of which the small,
    largely-technical vocabulary here needs: t/loop_filter.py's own name matching makes the same
    choice, token = `[A-Za-z_][A-Za-z0-9_]*`)."""
    return _TOKEN.findall((text or "").lower())


@dataclass
class BM25Index:
    """Add every document, then build() once before search(). Adding after build() is allowed but
    invalidates cached statistics until the next build()."""
    k1: float = 1.5
    b: float = 0.75
    _tokens: dict = field(default_factory=dict)          # doc_id -> list[str]
    _postings: dict = field(default_factory=dict)        # token -> {doc_id: term frequency}
    _doc_len: dict = field(default_factory=dict)         # doc_id -> token count
    _avgdl: float = 0.0
    _built: bool = False

    def __len__(self) -> int:
        return len(self._tokens)

    def add(self, doc_id, text: str) -> None:
        if doc_id in self._tokens:
            raise ValueError(f"duplicate document id {doc_id!r}")
        tokens = tokenize(text)
        self._tokens[doc_id] = tokens
        self._doc_len[doc_id] = len(tokens)
        for term, count in Counter(tokens).items():
            self._postings.setdefault(term, {})[doc_id] = count
        self._built = False

    def build(self) -> "BM25Index":
        self._avgdl = (sum(self._doc_len.values()) / len(self._tokens)) if self._tokens else 0.0
        self._built = True
        return self

    def _idf(self, term: str) -> float:
        n = len(self._tokens)
        df = len(self._postings.get(term, ()))
        return math.log((n - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int = 5) -> list[tuple]:
        """[(doc_id, score), ...], best first, for documents sharing at least one query token.
        An empty query or an index with nothing added yet returns []."""
        if not self._built:
            self.build()
        terms = tokenize(query)
        if not terms or not self._tokens:
            return []
        scores: dict = {}
        for term in set(terms):
            posting = self._postings.get(term)
            if not posting:
                continue
            idf = self._idf(term)
            for doc_id, f in posting.items():
                denom = f + self.k1 * (1 - self.b + self.b * self._doc_len[doc_id] / (self._avgdl or 1.0))
                scores[doc_id] = scores.get(doc_id, 0.0) + idf * f * (self.k1 + 1) / denom
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], str(kv[0])))
        return ranked[:k]
