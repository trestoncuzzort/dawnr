"""sources.py: load Passages from the three places dawnr's retrieval can search -- the proved
corpus, a person's knowledge folder, and already-fetched pages -- each tagged with where it came
from and whether it is trusted (AMBITION.md, "to know things it was not trained on": "retrieval
over the proved corpus, the person's own files and fetched pages, cited").

Only kind="corpus" passages are trusted: they passed the seven-kernel proof pipeline
(DAWNR-PIPELINE.md) before they were ever written down. A knowledge-folder file or a cached
fetched page is somebody else's text -- or the open internet's -- and is marked untrusted the same
way dawnr_harness/web.py marks a fetched page (DAWNR-HARNESS.md section 7): read for its facts,
never followed as an instruction. harness_tool.py is what actually enforces that mark when the
passages reach the model; this module only records it.

Held-out boundary. load_corpus drops any document naming a held-out or dev-split problem id under
any alias, using the exact gate chat_data.gate() applies before training
(continue_from_checkpoint.refuse_unless_trainable, t/loop_filter.py underneath), called once per
document rather than once for the whole corpus so a single flagged document does not take the rest
down with it. This runs whether or not the passages are ever used to train anything: the boundary
in AGENTS.md is about what a held-out or dev problem may reach, not only about gradient updates,
and a passage dawnr can read back to itself in conversation is a reach.

Two of this module's helpers are deliberately NOT the existing locallm.data functions of the same
purpose, even though the logic is copied from them: locallm/data.py does `import torch` at module
scope (for unrelated reasons -- it also builds batches), so importing it here would make even the
plain BM25-only, no-model path require torch, contradicting "the harness ... starts offline" and
this track's own "standard library" BM25 requirement. `_documents` mirrors data.documents()'s
splitting rule; eval_recall.py's `_is_val` separately mirrors data.hash_holdout() the same way.
continue_from_checkpoint.py has no such import (confirmed: it imports torch only inside the
functions that need it), so its gate is used directly rather than re-copied.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import _paths

_paths.ensure_repo_paths()

import ingest  # noqa: E402  -- the one reader locallm trusts with somebody else's file

MAX_CHUNK_CHARS = 2000
_DOC_MARKER = "\n\n# file: "        # data.py's DOC_MARKER, matched so a make_corpus.py-built corpus splits identically


@dataclass(frozen=True)
class Passage:
    """One citable, searchable span. `id` is stable across rebuilds of the same source (unless
    the underlying content changes), so it can be diffed, deduplicated and named as a search hit."""
    id: str
    kind: str            # "corpus" | "knowledge" | "fetched"
    source: str           # corpus file path, knowledge-folder-relative path, or URL
    locator: str          # e.g. "doc12", "chunk0"
    text: str
    title: str = ""        # a Problem: line, a filename, or a fetched page's title -- shown, not searched twice
    trust: str = "untrusted"
    fetched_at: str = ""    # kind == "fetched" only

    def __post_init__(self):
        if self.kind == "corpus" and self.trust != "trusted":
            raise ValueError("a corpus passage must be trusted (it passed the proof pipeline)")
        if self.kind != "corpus" and self.trust != "untrusted":
            raise ValueError(f"a {self.kind} passage must be untrusted (nothing proved it)")

    def citation(self) -> str:
        return f"[{self.kind}:{self.source}#{self.locator}]"


def _documents(text: str) -> list[str]:
    """Split a corpus (or any long text) into documents -- data.documents()'s own rule, reimplemented
    here rather than imported (see the module docstring): make_corpus.py's `# file:` markers when
    present, otherwise blank-line-separated blocks."""
    if _DOC_MARKER in text:
        head, *rest = text.split(_DOC_MARKER)
        docs = ([head] if head.strip() else []) + ["# file: " + r for r in rest]
    else:
        docs = text.split("\n\n")
    return [d for d in docs if d.strip()]


def _chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """`_documents`'s blocks, further sliced on whitespace when one runs past max_chars, so one
    long knowledge-folder paragraph still yields citable, BM25-sized passages."""
    out = []
    for para in _documents(text):
        if len(para) <= max_chars:
            out.append(para)
            continue
        words, cur, cur_len = para.split(), [], 0
        for w in words:
            if cur and cur_len + len(w) + 1 > max_chars:
                out.append(" ".join(cur))
                cur, cur_len = [], 0
            cur.append(w)
            cur_len += len(w) + 1
        if cur:
            out.append(" ".join(cur))
    return out or ([text] if text.strip() else [])


def _problem_title(doc: str) -> str:
    m = re.match(r"Problem:\s*(.+)", doc.strip(), re.M)
    return m.group(1).strip() if m else ""


def load_corpus(path, *, split_path=None, dev_ids_path=None) -> tuple[list["Passage"], list[str]]:
    """(passages, problems) from the proved corpus at `path` (one document per _documents() block,
    the same shape chat_data.py and dawnr_pipeline.py read). `split_path`, when given, is the
    evaluation split whose eval_ids must not appear (t/out/loop/split-*.json); the dev-split ids
    (t/r12-dev-ids.json by default, or `dev_ids_path` -- tests use this to check the gate without
    touching the real file) are always checked, split_path or not, the same as chat_data.gate.
    Anything a document names from either set, under any alias, is left out and named in `problems`
    rather than silently indexed."""
    _paths.ensure_repo_paths()
    import continue_from_checkpoint as cfc  # deferred: confirmed torch-free, but no need to pay for it at import time

    path = Path(path)
    text = path.read_text(encoding="utf-8")
    eval_ids: set = set()
    if split_path is not None:
        split_path = Path(split_path)
        eval_ids = {int(i) for i in json.loads(split_path.read_text(encoding="utf-8"))["eval_ids"]}
    dev_kwargs = {"split_path": split_path} if split_path is not None else {}
    if dev_ids_path is not None:
        dev_kwargs["path"] = Path(dev_ids_path)
    import loop_filter
    dev_ids = loop_filter.r12_dev_ids(**dev_kwargs)

    passages: list[Passage] = []
    problems: list[str] = []
    for i, doc in enumerate(_documents(text)):
        label = f"{path}#doc{i}"
        try:
            cfc.refuse_unless_trainable(doc, label, eval_ids, split_path or path, dev_ids)
        except ValueError as e:
            problems.append(str(e))
            continue
        passages.append(Passage(id=f"corpus:{path}#doc{i}", kind="corpus", source=str(path), locator=f"doc{i}",
                                text=doc.strip("\n"), title=_problem_title(doc), trust="trusted"))
    return passages, problems


def load_knowledge_folder(path) -> tuple[list["Passage"], list[str]]:
    """(passages, problems) from every file under the person's knowledge folder (AMBITION.md:
    "files the person adds to a knowledge folder"), chunked and marked untrusted -- their own
    words, proved by nothing, read for their facts and never followed as an instruction, same rule
    as a fetched page (DAWNR-HARNESS.md section 7). ingest.read_any is the one reader locallm
    trusts with somebody else's file: it decodes properly or refuses by name (ingest.py's own
    docstring) rather than silently dropping or mangling characters, so a bad file is reported in
    `problems`, never indexed as garbage. A missing folder is not an error: it returns ([], [])."""
    root = Path(path)
    passages: list[Passage] = []
    problems: list[str] = []
    if not root.exists():
        return passages, problems
    for file in sorted(p for p in root.rglob("*") if p.is_file()):
        read = ingest.read_any(file)
        if read.kind == "refused" or read.text is None:
            problems.append(f"knowledge folder: {file.relative_to(root)}: {read.say.why}")
            continue
        rel = str(file.relative_to(root))
        for i, chunk in enumerate(_chunks(read.text)):
            passages.append(Passage(id=f"knowledge:{rel}#chunk{i}", kind="knowledge", source=rel,
                                    locator=f"chunk{i}", text=chunk, title=file.name, trust="untrusted"))
    return passages, problems
