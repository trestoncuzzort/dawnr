#!/usr/bin/env python3
"""Build locallm.app, so macOS has something to double-click.

    python3 locallm/make_mac_app.py                  onto the Desktop
    python3 locallm/make_mac_app.py --to /Applications

WHY A BUNDLE AND NOT A .command FILE. A .command opens a Terminal window and
leaves it sitting behind the program, and it cannot carry a name. A bundle is a
directory macOS treats as an application: it can be dragged to the Dock, it
launches with no terminal, and its Info.plist CFBundleName is what the macOS menu
bar reads. Without it the menu bar says "Python", because that is the executable's
name and the window title has no bearing on it.

The bundle holds a launcher script, not a copy of the program. A copy would go
stale the moment the repository moved on, and the whole point of the window is
that it reloads its own source.
"""
from __future__ import annotations

import argparse
import os
import plistlib
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = "0.2.0"

LAUNCHER = """#!/bin/bash
# Bundle executable. Finder runs this; it must not depend on a login shell's PATH
# or on the working directory, because a double-click supplies neither.
APP="__APP__"
cd "$APP" || { /usr/bin/osascript -e 'display alert "locallm" message "locallm is not at __APP__ any more."'; exit 1; }
PY=""
for c in /usr/local/bin/python3 /opt/homebrew/bin/python3 /usr/bin/python3 python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$(command -v "$c")"; break; fi
done
[ -n "$PY" ] || { /usr/bin/osascript -e 'display alert "locallm" message "Python 3 is not installed. Get it from python.org."'; exit 1; }
if ! "$PY" -c 'import tkinter' 2>/dev/null; then
  /usr/bin/osascript -e 'display alert "locallm" message "This Python has no Tk. The installer from python.org includes it."'
  exit 1
fi
exec "$PY" home.py
"""


def build(into: Path, app_dir: Path) -> Path:
    bundle = into / "locallm.app"
    macos = bundle / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    (bundle / "Contents" / "Resources").mkdir(exist_ok=True)

    # plistlib rather than a heredoc: it is in the standard library and it cannot
    # emit a plist macOS will refuse to parse, which a hand-written one can.
    (bundle / "Contents" / "Info.plist").write_bytes(plistlib.dumps({
        "CFBundleName": "locallm",
        "CFBundleDisplayName": "locallm",
        "CFBundleIdentifier": "org.locallm.app",
        "CFBundleVersion": VERSION,
        "CFBundleShortVersionString": VERSION,
        "CFBundleExecutable": "locallm",
        "CFBundlePackageType": "APPL",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.developer-tools",
    }))
    run = macos / "locallm"
    run.write_text(LAUNCHER.replace("__APP__", str(app_dir)))
    run.chmod(run.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bundle


def main() -> int:
    ap = argparse.ArgumentParser(description="build locallm.app for macOS")
    ap.add_argument("--to", type=Path, default=Path.home() / "Desktop",
                    help="where to put it; the Desktop by default")
    ap.add_argument("--app", type=Path, default=HERE,
                    help="the folder holding home.py; this one by default")
    a = ap.parse_args()
    if sys.platform != "darwin":
        print("make_mac_app: this builds a macOS bundle and this is not macOS.\n"
              "It will still write one, which is useful for checking the layout.",
              file=sys.stderr)
    if not (a.app / "home.py").is_file():
        print(f"make_mac_app: no home.py in {a.app}", file=sys.stderr)
        return 2
    a.to.mkdir(parents=True, exist_ok=True)
    bundle = build(a.to, a.app.resolve())
    print(f"{bundle}\n  runs {a.app.resolve()}/home.py\n"
          f"  double-click it, or drag it to the Dock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
