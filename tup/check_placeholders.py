#!/usr/bin/env python3
"""check_placeholders.py: no book placeholder may reach the build unhandled.

    python3 tup/check_placeholders.py

The LFS book addresses a human, so its pages contain literal instructions in
angle brackets: <paper_size>, <xxx>, <Your Domain Name>, <locale name>,
<your name here>. Under a driver these are not instructions, they are shell,
and `PAGE=<paper_size> ./configure` dies trying to read a file called
paper_size, which is exactly how chapter 8 stopped at groff.

Every page containing a placeholder MUST have an override that fills it. This
fails loudly otherwise, listing the page and the line, so the gap is found
before a build cycle is spent on it rather than after.

It also caught its own author: the first scan for placeholders used a regex
without underscores, so <paper_size> slipped through while <xxx> and
<Your Domain Name> were caught. The pattern here allows underscores, digits,
spaces, dots and hyphens.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OVERRIDES = HERE / "overrides"
BOOKS = {"arm64": HERE / "book", "x86_64": HERE / "book-x86_64"}
NUMBERED = re.compile(r"^\d\d-")
PLACEHOLDER = re.compile(r"<[A-Za-z_][A-Za-z0-9_ .@-]*>")
# lines where angle brackets are legitimate shell or markup, not placeholders
IGNORE = re.compile(r"<<|EOF|https?://|</|<[0-9]|-> ")


def covered_by(arch: str) -> set[str]:
    """Page names (numbered and bare) an override exists for, in this arch's
    build: shared overrides plus overrides/<arch>/. Another arch's directory
    does not count, which is the point: an x86 page is not covered by an
    arm64 override."""
    names = set()
    for p in OVERRIDES.rglob("*.sh"):
        top = p.relative_to(OVERRIDES).parts[0]
        if top in BOOKS and top != arch:
            continue
        names.add(p.name)
        names.add(NUMBERED.sub("", p.name))
    return names


def main() -> int:
    bad, seen = [], 0
    for arch, book in BOOKS.items():
        if not book.is_dir():
            continue
        covered = covered_by(arch)
        for page in sorted(book.glob("ch*/[0-9]*.sh")):
            for i, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith("#") or IGNORE.search(line):
                    continue
                m = PLACEHOLDER.search(line)
                if not m:
                    continue
                seen += 1
                if page.name not in covered and NUMBERED.sub("", page.name) not in covered:
                    bad.append((f"{arch}:{page.parent.name}/{page.name}", i, line.strip()))
                break
    for pg, i, line in bad:
        print(f"  FAIL {pg}:{i}  unhandled placeholder\n         {line}")
    print(f"\n{seen - len(bad)}/{seen} pages with placeholders have an override")
    if bad:
        print("A placeholder without an override is a page that dies on contact "
              "with the driver. Write the override before building.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
