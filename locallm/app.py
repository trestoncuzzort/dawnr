#!/usr/bin/env python3
"""locallm -- one window: train a model, watch seven checkers judge it, read why.

    python3 locallm/app.py              opens on Home
    python3 locallm/app.py --page "Live checks"

This is a launcher, not a third application. The window is t/lab.py's shell and the
Train page is locallm/studio.py's training surface embedded in it, so there is one
of each and neither was copied.

WHY IT IS ONE WINDOW. The two halves were built separately and answered different
halves of the same question. studio.py trains a model from your own text with no
jargon on screen. lab.py watches the seven proof checkers judge what a model wrote
and explains every verdict in words. A person doing this work does both in one
sitting, and having to quit one program to see the result of the other is the seam
this removes.

ONE Tk ROOT. The shell owns it. Two tk.Tk() roots in a process is undefined
behaviour rather than untidy -- the first mainloop() opens both windows and blocks
until both close (stackoverflow.com/q/39417091, read 2026-09-20). Studio is a
ttk.Frame and takes a parent, so it embeds without a second root, and it is
imported lazily inside the Train page because it imports torch at module scope and
everything else in the window works without torch.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent / "t" / "lab.py"


def main() -> int:
    if not LAB.exists():
        print(f"locallm: the window lives in {LAB} and it is not there", file=sys.stderr)
        return 2
    if "--page" not in sys.argv[1:]:
        sys.argv += ["--page", "Home"]
    # run_path rather than import: lab.py is a script with its own main() and its
    # own sys.path setup, and running it as __main__ is exactly what it expects.
    runpy.run_path(str(LAB), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
