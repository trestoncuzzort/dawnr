"""dawnr's memory: what dawnr remembers of each person across sessions (DAWNR-MEMORY.md).

Standard-library Python 3.10+. A folder per person in the app's data folder, owner-only where the OS supports it
(store.py); episodes, facts and preferences extracted from the person's own words at the end of a session, through
a gate nothing from outside can pass (extract.py); the person's own pinned notes; recall at the start of a session
inside a token budget, by recency, importance and BM25 relevance to their first message (retrieval.py), rendered as a
<|output_start|><|memory|> ... span (span.py); wired into dawnr's harness as the SessionStart and SessionEnd hooks
(harness_hooks.py). The person's controls, list, show, correct, pin, forget, forget a session, export and forget
everything, are MemoryStore's methods and `python locallm/dawnr_memory --help`.

The harness imports harness_hooks only when its configuration has a "memory" key; nothing here imports it.
"""
from .extract import (ForgetRequest, Proposal, Report, RuleProposer, SessionView, admit, end_session,  # noqa: F401
                      proposals_from_json)
from .retrieval import BM25, Recall, byte_count, fit_lines, rank, recall  # noqa: F401
from .store import (KINDS, MemoryStore, StoreError, data_root, memory_root, normalize_person)  # noqa: F401
