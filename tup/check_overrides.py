#!/usr/bin/env python3
"""check_overrides.py: every override must name a page that exists.

    python3 tup/check_overrides.py

An override is matched to a page BY NAME within a chapter (see driver.sh),
so a page that is renamed, or that exists in one book and not the other,
unhooks its override silently. The build then runs the raw book page, which
is exactly what the override existed to prevent, and nothing says a word.
That is the same silent-drop class as the dropped Python page and the eaten
ORDER list, so it gets the same treatment: a check that fails loudly.

History worth keeping: overrides used to carry the page NUMBER in their
name (29-shadow.sh). That hooked correctly on the arm64 book and would have
unhooked every chapter-8 override on the x86 12.4 book, whose chapter 8 is
two pages shorter. Numbers are still accepted, but they bind to one book.

This resolves every override against every extracted book (book/ is arm64,
book-x86_64/ is x86_64), the way the driver does: arch-bound overrides
(overrides/<arch>/...) against that arch's book only, shared overrides
against all of them. Exits nonzero if any override hooks nothing in a book
it applies to, or if a flat override would fire in two chapters at once.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OVERRIDES = HERE / "overrides"
BOOKS = {"arm64": HERE / "book", "x86_64": HERE / "book-x86_64"}
NUMBERED = re.compile(r"^\d\d-")


def pages_of(book: Path) -> dict[str, list[str]]:
    """page name (with and without its number) -> chapters it appears in."""
    out: dict[str, list[str]] = {}
    for order in sorted(book.glob("ch*/ORDER")):
        ch = order.parent.name
        for line in order.read_text().split():
            out.setdefault(line, []).append(ch)
            out.setdefault(NUMBERED.sub("", line), []).append(ch)
    return out


def main() -> int:
    books = {a: pages_of(p) for a, p in BOOKS.items() if p.is_dir()}
    if not books:
        print("no extracted book found; run extract_book.py first")
        return 1
    bad, ok = [], []
    for ov in sorted(OVERRIDES.rglob("*.sh")):
        if ov.name.startswith("lib-"):   # shared helpers, not pages
            continue
        rel = ov.relative_to(OVERRIDES)
        parts = rel.parts
        arch = parts[0] if parts[0] in BOOKS else ""
        scoped = parts[-2] if len(parts) >= 2 and parts[-2].startswith("ch") else ""
        applies = [arch] if arch else sorted(books)
        for a in applies:
            if a not in books:
                bad.append((str(rel), a, ["no extracted book for this arch"]))
                continue
            chapters = books[a].get(ov.name, [])
            if scoped:
                chapters = [c for c in chapters if c == scoped]
            if not chapters:
                stem = NUMBERED.sub("", ov.name)
                near = sorted({p for p in books[a] if p.endswith(stem)})
                bad.append((str(rel), a, near))
            elif len(set(chapters)) > 1 and not scoped:
                bad.append((str(rel), a, [f"AMBIGUOUS across {','.join(sorted(set(chapters)))}: "
                                         f"move it into overrides/{chapters[0]}/"]))
            else:
                ok.append((str(rel), a, chapters[0]))

    for name, a, ch in ok:
        print(f"  ok   {name:30} [{a:6}] -> {ch}")
    for name, a, near in bad:
        print(f"  FAIL {name:30} [{a:6}] -> hooks no page"
              + (f"; did you mean {', '.join(near)}?" if near else ""))
    print(f"\n{len(ok)}/{len(ok)+len(bad)} override/book pairs are hooked to a real page")
    if bad:
        print("An unhooked override does not fire, and the raw book page runs "
              "in its place, silently. Rename it to match.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
