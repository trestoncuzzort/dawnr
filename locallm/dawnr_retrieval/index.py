"""index.py: one searchable index over the proved corpus, the knowledge folder and cached fetched
pages. BM25 (bm25.py) always runs; a dense pass (dense.py) is added only when the operator's config
turns it on, and the two rankings are merged with Reciprocal Rank Fusion rather than a raw score
blend, because BM25 scores and cosine similarities are not on comparable scales (Microsoft Learn,
"Relevance scoring in hybrid search using Reciprocal Rank Fusion (RRF)",
learn.microsoft.com/en-us/azure/search/hybrid-search-ranking): each ranked list contributes
1/(rank + k) per document (k a small constant, 60 by default, the value that source's own
experiments recommend), summed across lists, re-sorted. BM25-alone search needs no fusion and pays
no RRF cost.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .bm25 import BM25Index
from .cache import load_fetched_cache
from .sources import Passage, load_corpus, load_knowledge_folder

DEFAULT_RRF_K = 60


@dataclass
class KnowledgeIndex:
    bm25: BM25Index = field(default_factory=BM25Index)
    dense: object = None                    # a dense.DenseIndex, or None (off by default)
    rrf_k: int = DEFAULT_RRF_K
    problems: list = field(default_factory=list)
    _passages: dict = field(default_factory=dict)   # id -> Passage

    def add_all(self, passages) -> None:
        for p in passages:
            if p.id in self._passages:
                continue          # the same file or page indexed twice (e.g. two sources overlap); first copy wins
            self._passages[p.id] = p
            self.bm25.add(p.id, (p.title + "\n" + p.text) if p.title else p.text)

    def build(self) -> "KnowledgeIndex":
        self.bm25.build()
        return self

    def count(self) -> int:
        return len(self._passages)

    def passages(self) -> list:
        return list(self._passages.values())

    def search(self, query: str, k: int = 5) -> list[tuple]:
        """[(Passage, score), ...], best first. With no dense index, score is BM25's own; with one,
        score is the fused RRF score and BM25's own units no longer apply."""
        if self.dense is None:
            return [(self._passages[doc_id], score) for doc_id, score in self.bm25.search(query, k)]
        pool = max(k * 4, 20)          # widen each side before fusing, so a top-k dense hit BM25 ranked
        bm25_hits = self.bm25.search(query, pool)     # lower (or missed) still gets its dense-side credit
        dense_hits = self.dense.search(query, pool)
        return self._rrf(bm25_hits, dense_hits, k)

    def _rrf(self, bm25_hits, dense_hits, k: int) -> list[tuple]:
        scores: dict = {}
        for rank, (doc_id, _score) in enumerate(bm25_hits, 1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (self.rrf_k + rank)
        for rank, (doc_id, _score) in enumerate(dense_hits, 1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (self.rrf_k + rank)
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], str(kv[0])))[:k]
        return [(self._passages[doc_id], score) for doc_id, score in ranked]


def build_index(cfg: dict) -> "KnowledgeIndex":
    """The index an operator's `retrieval` configuration describes (DAWNR-RETRIEVAL.md has the
    shape). Every key is optional; an empty {} builds an index with nothing in it rather than
    erroring, since the harness itself must start with no configuration at all."""
    cfg = dict(cfg or {})
    index = KnowledgeIndex(rrf_k=int(cfg.get("rrf_k", DEFAULT_RRF_K)))
    if cfg.get("corpus"):
        passages, problems = load_corpus(cfg["corpus"], split_path=cfg.get("split"))
        index.add_all(passages)
        index.problems += problems
    if cfg.get("knowledge_folder"):
        passages, problems = load_knowledge_folder(cfg["knowledge_folder"])
        index.add_all(passages)
        index.problems += problems
    if cfg.get("fetched_cache"):
        passages, problems = load_fetched_cache(cfg["fetched_cache"])
        index.add_all(passages)
        index.problems += problems
    index.build()
    dense_cfg = cfg.get("dense")
    if dense_cfg:
        from .dense import DenseIndex
        index.dense = DenseIndex.build(index.passages(), **dense_cfg)
    return index
