#!/usr/bin/env python3
"""Refresh exact LFS patch context without changing any added/deleted code.

The original patches remain separate, approved lower-assurance source inputs.
This transformation is bound to their exact digests. Coreutils has an uneven
three-line/two-line context hunk; add the next unchanged source line. Two kbd
maps renamed Shift-Tab to Backtab; retain that newer unchanged context.
"""
import hashlib
from pathlib import Path
import sys


PINS = {
    "coreutils-9.11-i18n-1.patch": "7c2aecf9ae24b87b019595e382b9f41d2c96de7f95abe95ad8cacc7e2ce1bbcc",
    "kbd-2.10.0-backspace-1.patch": "8be28dcb11420624a500f2ea4fe975f771174bffee50e54ec8cd295a2dec104e",
}


def adapt(name, data):
    if name not in PINS or hashlib.sha256(data).hexdigest() != PINS[name]:
        raise ValueError("unreviewed patch context input")
    if name.startswith("coreutils-"):
        header = b"@@ -4483,5 +5127,28 @@\n"
        following = b"@@ -4729,13 +5396,34 @@\n"
        start, end = data.index(header), data.index(following)
        old = data[start:end]
        tail = b"   inittables ();\n \n"
        if not old.endswith(tail):
            raise ValueError("unreviewed coreutils hunk layout")
        new = old.replace(header, b"@@ -4483,6 +5127,29 @@\n", 1)
        new = new[:-len(tail)] + b"   inittables ();\n \n   {\n"
        return data[:start] + new + data[end:]
    # Two exact context lines differ only in the existing Shift-Tab name.
    replacements = (
        (b" keycode  15 = Tab              Meta_Tab             \n", b" keycode  15 = Tab              Backtab             \n"),
        (b" keycode  15 = Tab              Meta_Tab\n", b" keycode  15 = Tab              Backtab\n"),
    )
    for old, new in replacements:
        if data.count(old) != 1:
            raise ValueError("unreviewed kbd context occurrence")
        data = data.replace(old, new, 1)
    return data


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("expected original patch and new adapted output")
    source, output = map(Path, sys.argv[1:])
    if source.is_symlink() or output.exists() or output.is_symlink():
        raise SystemExit("refusing redirected input or existing output")
    with output.open("xb") as stream:
        stream.write(adapt(source.name, source.read_bytes()))
