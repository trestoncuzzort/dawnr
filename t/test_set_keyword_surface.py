"""Regression cover for the finite-sets keyword regression (found 2026-09-27,
SPEC.md "Finite sets (v1)" merged 2026-09-27, then respelled the same day).

`t/surface.py` reserved `set`, `card`, `union`, `inter` and `diff` as
keywords. `diff` is a common variable and return name -- 4 documents of the
proved corpus and 5 lifted task files under t/out/lifted-tasks-*/ used it --
and nothing checked that a corpus document still parsed before it was
written, so the builder kept emitting programs it could no longer read back.
`diff` is now spelled `setminus` at the surface (the AST op tag stays
"diff"; see surface.py's KEYWORDS comment and pexpr); these tests are the
three guards that regression asked for:

  1. every committed task (t/tasks, t/lemmas, t/nested) still parses;
  2. every document of the proved corpus still parses, when a corpus file is
     present to check (skipped by name otherwise, never silently passed);
  3. `diff` parses where the grammar allows an identifier, and the four
     words the grammar still needs reserved (`set`, `card`, `union`,
     `inter`) do not -- stated here, not just in a comment, so a future
     change to any of the five is caught by name.
"""
import glob
import os
import unittest
from pathlib import Path

import surface

HERE = Path(__file__).resolve().parent
CORPUS_CANDIDATES = (
    HERE / "out" / "loop" / "corpus-r12-headed.txt",
    Path("~/scratch/corpus-2026-09-27-7.txt").expanduser(),
)


def _committed_task_files():
    files = []
    for sub in ("tasks", "lemmas", "nested"):
        files += sorted(glob.glob(str(HERE / sub / "*.t")))
    return files


class CommittedTasksParseTests(unittest.TestCase):
    def test_every_committed_task_parses(self):
        files = _committed_task_files()
        self.assertGreater(len(files), 0, "no committed task files found under t/tasks, t/lemmas, t/nested")
        failures = []
        for path in files:
            try:
                surface.parse_file(path)
            except surface.SurfaceError as e:
                failures.append((os.path.basename(path), str(e)))
        self.assertEqual(failures, [], f"{len(failures)} committed task(s) do not parse: {failures}")


class ProvedCorpusParseTests(unittest.TestCase):
    def _corpus_path(self):
        for p in CORPUS_CANDIDATES:
            if p.exists():
                return p
        return None

    def test_every_document_of_the_proved_corpus_parses(self):
        corpus = self._corpus_path()
        if corpus is None:
            self.skipTest(f"neither {CORPUS_CANDIDATES[0]} nor {CORPUS_CANDIDATES[1]} is present")
        import loop_filter                                        # noqa: PLC0415
        import re                                                 # noqa: PLC0415
        text = corpus.read_text(encoding="utf-8")
        boundary = re.compile(r"\n\s*\n(?=Problem: |Signature: |t \d)")
        docs = [d for d in boundary.split(text) if d.strip()]
        self.assertGreater(len(docs), 0, f"{corpus} holds no document")
        failures = []
        for d in docs:
            if loop_filter.is_spec_document(d):
                continue                                          # by design: a declaration, no body
            try:
                surface.parse(loop_filter.strip_head(d))
            except surface.SurfaceError as e:
                name = next((ln.split()[1].split("(")[0] for ln in d.split("\n")
                            if ln.startswith("task ")), "?")
                failures.append((name, str(e)))
        self.assertEqual(failures, [], f"{len(failures)} of {len(docs)} document(s) in {corpus} do not "
                                       f"parse: {failures}")


# `diff` was freed by the 2026-09-27 respelling (set difference is now
# `setminus`); `set`, `card`, `union` and `inter` stay reserved because the
# grammar needs them at the exact point an identifier could otherwise start:
# `set` opens the type-name production a `var x: set` declaration and a
# param/return type need to recognize before they would try a user name,
# and `card`/`union`/`inter` are resolved by keyword in p_atom before the
# parser would fall through to a generic `name(args)` call -- an unreserved
# `card` would make `card(x)` an ordinary (and undefined) spec_fun call, a
# different AST, not the built-in operation. None of the four collide with
# a corpus identifier today (only `diff` did), so freeing them buys nothing
# and costs the AST ambiguity above; only `setminus` (the new reservation)
# and these four are kept.
_TASK = "t 1\ntask f_%s(%s: int) returns (r: int)\n  ensures r == %s\n{\n  r := %s;\n}\n"

STILL_FREE = ("diff",)
STILL_RESERVED = ("set", "card", "union", "inter")


class IdentifierReservationTests(unittest.TestCase):
    def test_diff_parses_as_an_ordinary_identifier(self):
        for word in STILL_FREE:
            with self.subTest(word=word):
                task = surface.parse(_TASK % (word, word, word, word))
                self.assertEqual(task["params"][0]["name"], word)

    def test_set_card_union_inter_stay_reserved(self):
        for word in STILL_RESERVED:
            with self.subTest(word=word):
                with self.assertRaises(surface.SurfaceError,
                                       msg=f"{word!r} parsed as an identifier; SPEC.md says the grammar "
                                           f"still needs it reserved"):
                    surface.parse(_TASK % (word, word, word, word))

    def test_setminus_is_the_new_reservation(self):
        with self.assertRaises(surface.SurfaceError):
            surface.parse(_TASK % ("setminus", "setminus", "setminus", "setminus"))


if __name__ == "__main__":
    unittest.main()
