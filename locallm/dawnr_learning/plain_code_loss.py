"""plain_code_loss.py: each checkpoint's loss on the same fixed windows of held-out plain source code.

    python3 locallm/dawnr_learning/plain_code_loss.py --text <held-out source text> <checkpoint dir> ...

The sleep's plain-code guard (sleep.GuardWindows: the first 400,000 characters,
16 windows of 512 tokens drawn with seed 12345) applied to whole checkpoints, so
two models can be compared on exactly the windows a sleep compares an adapter
with its base. DAWNR-LEARNING.md uses it to show what chat mid-training did to
the core's plain-code loss. CPU by default; nothing is trained.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for p in (str(HERE.parent), str(HERE.parent.parent / "t")):
    if p not in sys.path:
        sys.path.insert(0, p)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--text", type=Path, required=True, help="held-out plain source text (never trained on)")
    ap.add_argument("--chars", type=int, default=400_000)
    ap.add_argument("--block", type=int, default=512)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("checkpoints", type=Path, nargs="+")
    a = ap.parse_args(argv)
    from checkpoint import load_checkpoint
    from dawnr_learning.sleep import GuardWindows
    with a.text.open(encoding="utf-8") as f:
        text = f.read(a.chars)
    out = {}
    for path in a.checkpoints:
        model, tok, _ = load_checkpoint(path, a.device)
        out[str(path)] = GuardWindows(tok, text, min(a.block, model.config.block_size)).loss(model, a.device)
        print(json.dumps({"checkpoint": str(path), "plain_code_loss": out[str(path)]}), flush=True)
        del model
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
