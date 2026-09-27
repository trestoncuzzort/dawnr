"""heldout_gate.py: the trainers' held-out gate, shipped, so app code never imports a research script for it.

`refuse_unless_trainable` lived in continue_from_checkpoint.py (the r12 fine-tune, a research script
release.py keeps out of the zip); dawnr_retrieval/sources.py imported the script for this one function,
which pulled the research record into the shipped app's closure (found 2026-09-27). The gate now lives
here, in the standard library, and the script re-exports it.

It needs t/'s loop_filter (the held-out, same-task and dev policy), which the release does not carry
either: a release without t/ beside it therefore refuses everything (fail-safe, DAWNR-LEARNING.md
section 8), because passing text ungated could mean training or indexing a held-out problem.
"""
from __future__ import annotations

import sys
from pathlib import Path

_T_DIR = Path(__file__).resolve().parent.parent / "t"


def _loop_filter():
    t_dir = str(_T_DIR)
    if t_dir not in sys.path:
        sys.path.insert(0, t_dir)
    import loop_filter  # t/'s own module; a deferred cross-repo import (release.py CROSS_REPO_OPTIONAL)
    return loop_filter


def refuse_unless_trainable(text: str, label: str, eval_ids, split, dev_ids=frozenset()) -> None:
    """Refuse, by name, text that names a held-out id under any alias, a
    same-task exclusion, or a dev-split id; nothing is dropped quietly.
    Without t/'s loop_filter beside this file, every text is refused."""
    try:
        loop_filter = _loop_filter()
    except ImportError as e:
        raise ValueError(f"cannot train: {label}: held-out gate unavailable ({e}); nothing is trainable "
                         f"without it") from e
    validation = loop_filter.validate_training_data(text, eval_ids)
    dev = loop_filter.held_out_ids_in(text, set(dev_ids))
    if validation.ok and not dev:
        return
    reasons = []
    if validation.held_out:
        reasons.append(f"contains held-out ids from {split}: {loop_filter.held_out_detail(validation.held_out)}")
    if validation.same_task_names or validation.same_task_ids:
        reasons.append(loop_filter.same_task_detail(validation))
    if dev:
        reasons.append(f"contains dev-split ids: {loop_filter.held_out_detail(dev)}")
    raise ValueError(f"cannot train: {label}: " + "; ".join(reasons))
