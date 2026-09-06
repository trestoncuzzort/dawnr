#!/usr/bin/env python3
"""corpora.py -- find the lifter's data checkouts without hardcoding one machine.

The same bug `verifiers/discover.py` fixed for kernel binaries, fixed for
corpora. Five modules named one box's `/home/<user>/t-corpora/...` as plain absolute
constants, which made the whole lifter test suite unrunnable anywhere but one
Ubuntu box: `test_lift_front.py` read a file at import time, and
`test_lifter.py`'s dispatcher catches only ImportError, so a missing corpus
took down the run instead of skipping it.

The location was never meant to be machine-specific. `t/lifter-design/README.md`
already documents it as `~/t-corpora/lifter-design-2026-09-05/`, home-relative;
the absolute path was one box's instantiation of that.

Resolution, most explicit first, matching discover.py's shape:

  1. $T_CORPORA, if set. Points at the data checkout wherever it lives.
  2. ~/t-corpora, the location the design docs already name.

Nothing here touches the filesystem at import: these are `Path` objects, not
reads. Ask `available()` before using one, and skip with a named reason when it
says no, so a machine without the checkout reports "skipped" rather than a
traceback. The corpora are deliberately NOT in the repo (they are a 785-program
third-party checkout plus a scratch bank), so absence is normal, not an error.
"""
from __future__ import annotations

import os
from pathlib import Path

# The data checkout root. Everything below hangs off it.
ROOT = Path(os.environ.get("T_CORPORA", Path.home() / "t-corpora"))

# DafnyBench, cloned from github.com/sun-wendy/DafnyBench (Apache-2.0). The
# doubled directory name is upstream's own layout, not a mistake here.
DAFNYBENCH = ROOT / "DafnyBench"
CORPUS_DIR = DAFNYBENCH / "DafnyBench" / "dataset" / "ground_truth"

# The 2026-09-05 lifter design bank: census, in-fragment list, the rprint
# corpus, and the hand-lifted seed pairs. Regenerable except for `inventory`,
# which a person wrote by hand.
BANK = ROOT / "lifter-design-2026-09-05"
CENSUS_JSON = BANK / "census.json"
INFRAGMENT_TXT = BANK / "infragment.txt"
CORPUS_RPRINT = BANK / "dpn" / "corpus_rprint"
INVENTORY_DIR = BANK / "inventory"


def available(*paths: Path) -> bool:
    """True when every path given exists. Call before reading, never inside a
    module-level expression: the point of this module is that importing it can
    never fail on a machine that has no checkout."""
    return all(p.exists() for p in paths)


def why_missing(*paths: Path) -> str:
    """A skip message naming what is absent and how to point at it, in the same
    spirit as discover.missing() for binaries."""
    absent = [str(p) for p in paths if not p.exists()]
    return ("corpus not available (%s). Set $T_CORPORA to the data checkout, "
            "or clone DafnyBench to %s"
            % (", ".join(absent), DAFNYBENCH))
