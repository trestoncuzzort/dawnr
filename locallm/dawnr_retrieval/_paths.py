"""_paths.py: put locallm/ and t/ on sys.path, the way every script in this repository already does
(chat_data.py, dawnr_pipeline.py: `sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / "t"))`).

Needed because sources.py and dense.py reach for locallm/checkpoint.py and t/loop_filter.py through
plain top-level imports, not package-relative ones (those two are not part of the dawnr_retrieval or
dawnr_harness packages), and dawnr_retrieval can be imported from places that never did this setup.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent      # locallm/dawnr_retrieval
LOCALLM = HERE.parent                       # locallm/
ROOT = LOCALLM.parent                       # repository root


def ensure_repo_paths() -> None:
    for p in (str(LOCALLM), str(ROOT / "t")):
        if p not in sys.path:
            sys.path.insert(0, p)
