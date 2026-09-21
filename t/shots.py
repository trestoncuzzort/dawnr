#!/usr/bin/env python3
"""Save one PNG per locallm page, for the README, on a machine with no desktop.

    python3 t/shots.py                       writes docs/img/<page>.png
    python3 t/shots.py --pages Results AI    only those
    python3 t/shots.py --settle 8            wait longer before each grab

WHY THIS EXISTS RATHER THAN A SCREENSHOT KEY. This desktop is Wayland, and an
XWayland window is redirected, so XGetImage against it fails: Pillow reports
"X get_image failed: error 8", which is BadMatch, measured 2026-09-20. Every
capture tool on the machine goes through that same call, so all of them fail the
same way. A private Xvfb server has no compositor, nothing is redirected, and the
identical grab succeeds. Taking a display of our own instead of fighting for the
real one is the trick in PyVirtualDisplay (github.com/ponty/pyvirtualdisplay,
release 3.0, read 2026-09-20), and so are two details worth copying: give Xvfb an
explicit depth, and poll for it rather than sleeping. The package itself is not
used, because locallm's dependencies are PyTorch and Tk and a screenshot is not a
reason to add a third.

Needs Xvfb, which is not a Python package:  sudo apt install xvfb
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "docs" / "img"
SIZE = (1400, 900)                    # the window's own default, from lab.py main()

# The pages are ASKED FOR, not listed here. A hardcoded list was here until
# 2026-09-21 and was stale within a day: the window gained Home and Proof and
# moved Live checks and Results behind the latter, and this tool would have
# happily photographed the five tabs that no longer existed while reporting
# success. The window knows its own pages, so ask it. Which pages exist depends
# on the machine anyway -- a lab-workstation.conf gives the remote variants of
# Collect data and AI, and Test a model needs torch.


def free_display() -> int:
    for n in range(99, 130):
        if not Path(f"/tmp/.X{n}-lock").exists() and not Path(f"/tmp/.X11-unix/X{n}").exists():
            return n
    raise SystemExit("shots: no free X display number between :99 and :129")


def start_xvfb(n: int, size: tuple[int, int]) -> subprocess.Popen:
    w, h = size
    # Depth 24 is not a default worth taking: at 16 the palette's five greys
    # (#0b0e14 through #262d3d) quantise into each other and the cards stop
    # reading as separate surfaces.
    return subprocess.Popen(["Xvfb", f":{n}", "-screen", "0", f"{w}x{h}x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_for(display: str, proc: subprocess.Popen, seconds: float = 15.0) -> None:
    """Poll until the server answers, because Xvfb returns from fork well before it
    accepts connections, so any fixed sleep is either a waste or a flake."""
    import tkinter as tk
    os.environ["DISPLAY"] = display
    deadline, last = time.monotonic() + seconds, None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"shots: Xvfb exited with {proc.returncode} before it was ready")
        try:
            probe = tk.Tk()
        except Exception as e:                      # TclError: not listening yet
            last = e
            time.sleep(0.2)
            continue
        probe.destroy()
        return
    raise SystemExit(f"shots: Xvfb on {display} never answered ({last})")


def pump(root, seconds: float) -> None:
    """Keep the event loop turning so after() callbacks land before the grab. The
    pages fill themselves from disk on a timer, so a grabbed frame that never ran
    the loop shows empty tables."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.02)


def colours(img) -> int:
    """How many distinct colours the capture holds. A flat image is the failure
    mode this whole file exists to avoid, and it is silent: BadMatch on a
    redirected window and a grab of an unmapped one both yield one colour, and
    both still write a perfectly valid PNG."""
    got = img.convert("RGB").getcolors(maxcolors=1 << 24)
    return len(got) if got else 1 << 24


def shoot(pages: list[str], settle: float, out: Path) -> list[tuple[Path, tuple, int]]:
    import tkinter as tk
    from PIL import ImageGrab

    sys.path.insert(0, str(HERE))
    import lab

    root = tk.Tk()
    root.title("locallm")
    root.geometry(f"{SIZE[0]}x{SIZE[1]}+0+0")       # fills the screen: no crop needed
    window = lab.Lab(root, start_page=pages[0]) if pages else lab.Lab(root)
    out.mkdir(parents=True, exist_ok=True)

    if not pages:                     # default: whatever this window actually has
        pages = list(window.pages)
        print(f"shots: this window has {len(pages)} pages -- {', '.join(pages)}")

    written = []
    for name in pages:
        if name not in window.pages:
            print(f"shots: skipping {name!r}, this machine's window has "
                  f"{', '.join(sorted(window.pages))}")
            continue
        window.show_page(name)
        pump(root, settle)
        img = ImageGrab.grab(xdisplay=os.environ["DISPLAY"])
        path = out / (name.lower().replace(" ", "-") + ".png")
        img.save(path)
        written.append((path, img.size, colours(img)))
    root.destroy()
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="save one PNG per locallm page")
    ap.add_argument("--pages", nargs="*", default=[],
                    help="which pages; default is every page the window has")
    ap.add_argument("--settle", type=float, default=3.0,
                    help="seconds to let a page finish drawing before the grab")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()

    if not shutil.which("Xvfb"):
        print("shots: Xvfb is missing, and it is the one thing this needs.\n"
              "    sudo apt install xvfb\n"
              "The running desktop is not an option: a Wayland session redirects the\n"
              "window, and XGetImage then returns BadMatch for every capture tool.",
              file=sys.stderr)
        return 2

    # lab.py reads and writes the window position under XDG_CACHE_HOME. A
    # documentation run must not move the operator's real window, so it gets a
    # cache of its own for the duration.
    cache = tempfile.mkdtemp(prefix="locallm-shots-")
    os.environ["XDG_CACHE_HOME"] = cache

    n = free_display()
    proc = start_xvfb(n, SIZE)
    try:
        wait_for(f":{n}", proc)
        written = shoot(list(a.pages), a.settle, a.out)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(cache, ignore_errors=True)

    if not written:
        print("shots: nothing was captured", file=sys.stderr)
        return 1
    flat = [p for p, _s, c in written if c < 16]
    for path, size, c in written:
        mark = "  FLAT, look at it" if c < 16 else ""
        print(f"  {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}"
              f"  {size[0]}x{size[1]}  {c} colours{mark}")
    if flat:
        print(f"shots: {len(flat)} capture(s) hold almost no colour, which is what a failed "
              f"grab looks like; they were still written so you can see for yourself",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
