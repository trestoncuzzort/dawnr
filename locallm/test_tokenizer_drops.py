"""A prompt with one unseen character in it must not become a different prompt.

Both character tokenizers in this repository encode with a filter — `if c in
self.stoi` — so anything the model never saw during training is dropped where it
stands. Not substituted, not counted, not mentioned. Someone who trains on
English and then types a line in their own script gets no error and a reply
written from whatever survived, which may be nothing at all. This file pins down
what the new `unknown_characters()` reports and, more importantly, pins the two
implementations to each other.

THERE ARE TWO IMPLEMENTATIONS AND THAT IS ON PURPOSE. `data.CharTokenizer` is
the torch path; `plain_generate.CharTokens` re-reads the same `tokenizer.json`
with nothing installed, which is what makes a USB stick work on a computer with
no machine-learning software on it. They cannot share code without one of them
gaining the other's dependencies, so the only thing that can keep them honest is
a test that runs them side by side on the same input. Every case below runs
through both.

WHY data.py IS READ RATHER THAN IMPORTED. `import data` executes `import torch`
at module scope, and this machine, like CI, has no torch, so importing it here
would skip the half of the comparison that matters. Instead the `CharTokenizer`
class is lifted out of data.py's source and compiled on its own —
docs.python.org/3/library/ast.html: "An abstract syntax tree can be compiled
into a Python code object using the built-in compile()" — into a namespace
holding only `json` and `Path`. That is not a workaround with a cost, it is a
second assertion for free: if anyone gives CharTokenizer a dependency beyond
those two names, the class stops building here and every test in this file says
so. Stubbing a fake `torch` into sys.modules was tried first and rejected for
exactly that reason — it keeps passing while the thing it is meant to protect
rots.

The error-handling shape comes from docs.python.org/3/library/codecs.html, where
'strict' raises and names the offending slice and 'ignore' drops in silence;
data.CharTokenizer.unknown_characters says why this repository asks the question
separately instead of making it a mode of encode().

Nothing here imports torch and nothing constructs a window, so it runs on this
machine and in CI:

    python3 -m unittest test_tokenizer_drops -v

RED WITNESS, each mutation applied to a copy of the file named, run there, and
the output quoted as it came back:

    data.py   unknown[c] = unknown.get(c, 0) + 1  ->  unknown[c] = 1
      FAIL test_counts_are_occurrences_not_distinct_characters:
        AssertionError: 1 != 3 : 'x' appears 3 times != 1
      FAIL test_every_character_is_either_encoded_or_reported:
        AssertionError: 5 != 9 : repeated unseen characters: 4+1
      FAIL test_both_implementations_agree_on_every_case:
        repeated unseen characters: {'x': 1} != {'x': 5}

    plain_generate.py   for c in text:  ->  for c in reversed(text):
      (counts unchanged, only the order, which is what dict equality alone
       would have let through)
      FAIL test_both_implementations_agree_on_every_case:
        AssertionError: Lists differ: ['x', 'y', 'z'] != ['z', 'y', 'x']
        : entirely unseen: ['x', 'y', 'z'] != ['z', 'y', 'x'] -- the order
        the characters were typed

    data.py   encode loses its filter: [self.stoi[c] for c in s]
      ERROR test_encode_still_drops_what_it_cannot_encode: KeyError: 'x'
      FAILED (errors=39)
      (a KeyError is what every caller in this repository would then have to
       learn to catch, which is why encode was left exactly as it was)
"""
from __future__ import annotations

import __future__
import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

import plain_generate

HERE = Path(__file__).resolve().parent

# data.py's own header, so the class is compiled under the same rules it was
# written under. Without this the method annotations are evaluated at class
# creation instead of left as strings, which is a difference this test has no
# business introducing.
_ANNOTATIONS = __future__.annotations.compiler_flag


def _class_from_source(module_name: str, class_name: str, allowed: dict):
    """Build one class out of a module's source without executing the module.

    `allowed` is the entire namespace it may use. A NameError from here is a
    finding, not a fixture problem: it means the class grew a dependency on
    something above it in its own file.
    """
    path = HERE / module_name
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = next(n for n in tree.body
                if isinstance(n, ast.ClassDef) and n.name == class_name)
    code = compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec",
                   flags=_ANNOTATIONS)
    namespace = dict(allowed)
    exec(code, namespace)
    return namespace[class_name]


CharTokenizer = _class_from_source("data.py", "CharTokenizer",
                                   {"json": json, "Path": Path})
CharTokens = plain_generate.CharTokens

# The vocabulary every case below is encoded against: the letters of "abc", a
# space and a newline. Small enough to write the expected ids by hand.
VOCAB = ["\n", " ", "a", "b", "c"]

# (name, text) pairs, run through both implementations. The names are what a
# failure prints, so they say which shape of input broke.
CASES = [
    ("empty", ""),
    ("entirely known", "abc cab\na"),
    ("one unseen character", "abx"),
    ("repeated unseen characters", "xax xbx x"),
    ("entirely unseen", "xyz"),
    ("unseen before seen", "xa"),
    ("mixed, unseen first", "xa ax"),
    ("curly quotes, the word-processor case", "“abc”"),
    ("another script", "абв abc"),          # Cyrillic a, be, ve
    ("outside the basic plane", "a\U0001f642b"),           # a slightly smiling face
    ("a combining mark on a known letter", "ábc"),
    ("a tab, which is not the space in the vocabulary", "a\tb"),
    ("a null byte", "a\x00b"),
    ("carriage return against the newline in the vocabulary", "a\r\nb"),
]


class UnknownCharacterReporting(unittest.TestCase):
    """What the new query says, on data.py's implementation."""

    def setUp(self):
        self.tok = CharTokenizer(VOCAB)

    def test_encode_still_drops_what_it_cannot_encode(self):
        # The behaviour every existing caller depends on, unchanged: a plain
        # list of ids, no exception, the unseen characters simply absent.
        ids = self.tok.encode("axb")
        self.assertEqual(ids, [2, 3])
        self.assertIsInstance(ids, list)
        self.assertEqual(self.tok.decode(ids), "ab")

    def test_nothing_dropped_reports_nothing(self):
        self.assertEqual(self.tok.unknown_characters("abc cab\n"), {})
        self.assertFalse(self.tok.unknown_characters("abc"))

    def test_unknown_characters_names_each_one_once(self):
        self.assertEqual(self.tok.unknown_characters("axbyc"), {"x": 1, "y": 1})

    def test_counts_are_occurrences_not_distinct_characters(self):
        unknown = self.tok.unknown_characters("xaxbx")
        self.assertEqual(unknown["x"], 3, f"'x' appears 3 times != {unknown['x']}")

    def test_order_is_first_appearance_not_sorted(self):
        # A message to a person reads in the order they typed, and sorting would
        # also hide a disagreement between the two implementations behind a
        # dict comparison that ignores order.
        self.assertEqual(list(self.tok.unknown_characters("zyx")), ["z", "y", "x"])

    def test_every_character_is_either_encoded_or_reported(self):
        # The invariant that makes the pair trustworthy: nothing falls between
        # the two. sum(...values()) is what ingest.Read calls `dropped`.
        for name, text in CASES:
            with self.subTest(name):
                kept = len(self.tok.encode(text))
                lost = sum(self.tok.unknown_characters(text).values())
                self.assertEqual(kept + lost, len(text), f"{name}: {kept}+{lost}")

    def test_an_empty_vocabulary_reports_everything(self):
        self.assertEqual(CharTokenizer([]).unknown_characters("ab"),
                         {"a": 1, "b": 1})

    def test_the_query_does_not_disturb_the_tokenizer(self):
        before = dict(self.tok.stoi)
        self.tok.unknown_characters("xyz" * 4)
        self.assertEqual(self.tok.stoi, before)
        self.assertEqual(self.tok.vocab_size, len(VOCAB))


class ExistingBehaviourStillHolds(unittest.TestCase):
    """The assertions test_tokenizer_integrity.py makes that need no torch.

    That file cannot run on this machine — it imports torch, checkpoint and
    model at module scope — so the character-tokenizer half of it is restated
    here, where it runs. It is restated, not moved: that file also covers
    checkpoint loading and byte-BPE fingerprints, which are torch's and the
    tokenizers package's business and are not this file's to take over.
    """

    def test_a_permuted_vocabulary_still_encodes_differently(self):
        original, permuted = CharTokenizer(["a", "b", "c"]), CharTokenizer(["b", "a", "c"])
        self.assertEqual(original.vocab_size, permuted.vocab_size)
        self.assertNotEqual(original.encode("ab"), permuted.encode("ab"))

    def test_from_text_builds_a_sorted_vocabulary_of_what_it_saw(self):
        tok = CharTokenizer.from_text("cab cab")
        self.assertEqual(tok.chars, [" ", "a", "b", "c"])
        self.assertEqual(tok.decode(tok.encode("cab cab")), "cab cab")

    def test_save_and_load_preserve_the_ids(self):
        tok = CharTokenizer.from_text("abc\n ")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tokenizer.json"
            tok.save(path)
            restored = CharTokenizer.load(path)
            self.assertEqual(restored.chars, tok.chars)
            self.assertEqual(restored.encode("cab"), tok.encode("cab"))


class TheTwoImplementationsAgree(unittest.TestCase):
    """One vocabulary, two tokenizers, the same answers.

    A person can reach a checkpoint either way — `studio.py` and `train.py` hold
    a data.CharTokenizer, `plain_generate.py` holds a CharTokens built from the
    tokenizer.json the first one wrote — and the two disagreeing means the same
    prompt becomes different tokens depending on which one opened the file.
    """

    def setUp(self):
        self.torch_path = CharTokenizer(VOCAB)
        self.plain_path = CharTokens(VOCAB)

    def test_both_implementations_agree_on_every_case(self):
        for name, text in CASES:
            with self.subTest(name):
                ours = self.torch_path.unknown_characters(text)
                theirs = self.plain_path.unknown_characters(text)
                self.assertEqual(self.torch_path.encode(text),
                                 self.plain_path.encode(text), name)
                self.assertEqual(ours, theirs, f"{name}: {ours} != {theirs}")
                # Dict equality ignores order, and order is part of the answer.
                self.assertEqual(list(ours), list(theirs),
                                 f"{name}: {list(ours)} != {list(theirs)} -- "
                                 f"the order the characters were typed")
                ids = self.torch_path.encode(text)
                self.assertEqual(self.torch_path.decode(ids),
                                 self.plain_path.decode(ids), name)

    def test_they_agree_on_a_vocabulary_with_a_repeated_character(self):
        # Degenerate but reachable: a hand-edited tokenizer.json. Both build
        # their index the same way, so the later id wins in both.
        duplicated = ["a", "a", "b"]
        for text in ("ab", "aXb"):
            self.assertEqual(CharTokenizer(duplicated).encode(text),
                             CharTokens(duplicated).encode(text), text)
            self.assertEqual(CharTokenizer(duplicated).unknown_characters(text),
                             CharTokens(duplicated).unknown_characters(text), text)

    def test_they_agree_on_the_tokenizer_file_one_of_them_wrote(self):
        # The real path: data.py saves, plain_generate.py loads, no torch in
        # between. This is what a stranger's stick actually does.
        tok = CharTokenizer.from_text("the quick brown fox\n")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tokenizer.json"
            tok.save(path)
            plain = CharTokens.load(path)
            self.assertEqual(plain.vocab_size, tok.vocab_size)
            for name, text in CASES:
                with self.subTest(name):
                    self.assertEqual(tok.encode(text), plain.encode(text), name)
                    self.assertEqual(tok.unknown_characters(text),
                                     plain.unknown_characters(text), name)


class NeitherFileGrewADependency(unittest.TestCase):
    """The two properties this whole arrangement rests on."""

    def test_plain_generate_imports_only_the_standard_library(self):
        # Load-bearing for the release: this module is verified to open the
        # shipped checkpoint and generate at 292 ms/token with no torch and no
        # numpy. An import added anywhere in it — including inside a function,
        # which is how one usually sneaks in — breaks that, so the whole tree is
        # walked rather than just the header.
        path = HERE / "plain_generate.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                roots = [(node.module or "").split(".")[0]] if node.level == 0 else ["."]
            else:
                continue
            for root in roots:
                self.assertIn(root, sys.stdlib_module_names,
                              f"plain_generate.py line {node.lineno} imports "
                              f"{root!r}, which is not in the standard library")

    def test_data_py_char_tokenizer_needs_only_json_and_path(self):
        # _class_from_source already proved it by building the class at import
        # time with nothing else in scope; this states it as a test so the
        # failure reads as a finding rather than a collection error.
        tok = CharTokenizer.from_text("abc")
        self.assertEqual(tok.unknown_characters("abx"), {"x": 1})


if __name__ == "__main__":
    unittest.main()
