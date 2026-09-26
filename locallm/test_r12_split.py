"""r12 blocker A7: the validation holdout is decided by each document's own text.

The grouped split used to pick the holdout from a seeded shuffle of document
ORDER, so the same seed on two corpora of different length held out unrelated
documents: r9 and r10 differed by about 53 documents, not by the 1% their
corpora differed by. Hash mode keys membership on the document's stripped text
and a split seed, the way Google's repeatable-splitting recipe keys on an
invariant field (developers.google.com/machine-learning/data-prep/construct/
sampling-splitting/randomization). Order mode stays byte-identical, so every
run from before this change can still be reproduced.

The split code is pure Python. When torch is absent (the desktop), a stub
module stands in for it so these tests still run; the Corpus tests need the
real thing and skip otherwise.
"""
import hashlib
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import torch  # noqa: F401
    HAVE_TORCH = True
except ImportError:                      # the split code never touches torch
    sys.modules["torch"] = types.ModuleType("torch")
    HAVE_TORCH = False

import data  # noqa: E402


def corpus(n=120):
    return "\n\n".join(f"Problem: task number {i}\nSignature: f{i}(int) -> int\n"
                       + ("r := r + %d;\n" % i) * (1 + (i * 37) % 23) + "}" for i in range(n)) + "\n"


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# Measured on the code before this change (plan of 2026-09-21, section 0), so
# a change to order mode's bytes is caught by number.
GOLDEN = {
    (0.1, 1337): ("1f1926acf78af6bbf2627a4972830048206613ca7d2dd0ba5fa559e3cbc344b9",
                  "eb7f875840214f2bf95f45f3ead989c33ad29576200cb36bb415dc3ba2239fea", 11),
    (0.1, 3): ("d53d7ce776d5512460d839c8bd5b3ea5e0519e4bc905a86584be4911499a79ad",
               "b5d0b3bb61bdc090e38ec7afb9151ce60a9f9c3dda9a095eee2e725676f7cd0c", 15),
}
GOLDEN_DUP = ("d4fbd39f59051ca4408bf0cd7e98a284761c197dd666ea370a01aa2fdf528542",
              "3c3808a1996163f3fd56942fd7558907823d5e2b079dceb8b88130ddb956d0e6")


def r10_like_edit(text: str) -> str:
    """Drop four documents, reword four, add two: the shape of r8 -> r10."""
    docs = data.documents(text)
    kept = [d for i, d in enumerate(docs) if i % 30 != 7]                 # drop 4 of 120
    kept = [d.replace("r := r + ", "r := r+ ") if i % 25 == 3 else d       # reword 4
            for i, d in enumerate(kept)]
    kept += ["Problem: extra one\nSignature: g(int) -> int\nr := 1;\n}",
             "Problem: extra two\nSignature: h(int) -> int\nr := 2;\n}"]
    return "\n\n".join(kept) + "\n"


def sides(train_docs, val_docs) -> dict[str, str]:
    return {**{d.strip(): "train" for d in train_docs}, **{d.strip(): "val" for d in val_docs}}


class OrderModeIsUnchanged(unittest.TestCase):
    def test_golden_hashes(self):
        text = corpus()
        for (frac, seed), (train_sha, val_sha, n_val) in GOLDEN.items():
            with self.subTest(frac=frac, seed=seed):
                train, val = data.group_split(text, frac, seed, by="order")
                self.assertEqual((sha(train), sha(val)), (train_sha, val_sha))
                self.assertEqual(len(data.documents(val)), n_val)
        text2 = text + "\n\n" + text.split("\n\n")[5] + "\n"
        train, val = data.group_split(text2, 0.2, 99, by="order")
        self.assertEqual((sha(train), sha(val)), GOLDEN_DUP)

    def test_default_is_still_order_mode(self):
        text = corpus()
        self.assertEqual(data.group_split(text), data.group_split(text, 0.1, 1337, by="order"))
        self.assertEqual(data.split_documents(text)[1], data.split_documents(text, by="order")[1])

    def test_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            data.split_documents(corpus(), by="shuffle")


class HashModeTests(unittest.TestCase):
    def test_membership_does_not_depend_on_the_rest_of_the_corpus(self):
        before, after = corpus(), r10_like_edit(corpus())
        a = sides(*data.split_documents(before, 0.1, 1337, by="hash"))
        b = sides(*data.split_documents(after, 0.1, 1337, by="hash"))
        shared = set(a) & set(b)
        self.assertGreater(len(shared), 100)
        moved = [d for d in shared if a[d] != b[d]]
        self.assertEqual(moved, [])

    def test_order_mode_moves_shared_documents_which_is_the_defect(self):
        before, after = corpus(), r10_like_edit(corpus())
        a = sides(*data.split_documents(before, 0.1, 1337, by="order"))
        b = sides(*data.split_documents(after, 0.1, 1337, by="order"))
        moved = [d for d in set(a) & set(b) if a[d] != b[d]]
        self.assertGreater(len(moved), 0)

    def test_split_seed_changes_the_holdout(self):
        text = corpus()
        v1 = {d.strip() for d in data.split_documents(text, 0.1, 1337, by="hash")[1]}
        v2 = {d.strip() for d in data.split_documents(text, 0.1, 1, by="hash")[1]}
        self.assertNotEqual(v1, v2)

    def test_hash_holdout_agrees_with_split_documents(self):
        text = corpus()
        train, val = data.split_documents(text, 0.1, 1337, by="hash")
        for d in train:
            self.assertFalse(data.hash_holdout(d, 1337, 0.1))
        for d in val:
            self.assertTrue(data.hash_holdout(d, 1337, 0.1))
        self.assertEqual(data.hash_holdout("\n\nabc\n", 7, 0.5), data.hash_holdout("abc", 7, 0.5))

    def test_a_duplicate_with_other_newlines_lands_once_on_one_side(self):
        text = corpus(40)
        first = data.documents(text)[0]
        # The builder joins with "\n\n", so a copy of the FIRST document appears
        # later with a leading newline. Order mode dedupes on the raw text and
        # keeps both (the defect the review of 2026-09-21 named); hash mode
        # dedupes on the stripped text.
        text2 = text + "\n\n" + first + "\n"
        train, val = data.split_documents(text2, 0.1, 1337, by="hash")
        copies = [d for d in train + val if d.strip() == first.strip()]
        self.assertEqual(len(copies), 1)
        self.assertEqual(len(train) + len(val), 40)

    def test_holdout_fraction_is_near_the_request_on_many_documents(self):
        text = corpus(2000)
        train, val = data.split_documents(text, 0.1, 1337, by="hash")
        self.assertAlmostEqual(len(val) / (len(train) + len(val)), 0.1, delta=0.02)

    def test_everything_in_validation_is_refused(self):
        with self.assertRaises(ValueError):
            data.split_documents(corpus(10), 1.0, 1337, by="hash")

    def test_group_split_joins_hash_mode(self):
        text = corpus()
        train_docs, val_docs = data.split_documents(text, 0.1, 1337, by="hash")
        train, val = data.group_split(text, 0.1, 1337, by="hash")
        self.assertEqual(train, "\n\n".join(train_docs))
        self.assertEqual(val, "\n\n".join(val_docs))


@unittest.skipUnless(HAVE_TORCH, "Corpus builds tensors; run on the lab")
class CorpusTests(unittest.TestCase):
    def test_corpus_exposes_the_split_and_the_document_lists(self):
        text = corpus(60)
        tok = data.CharTokenizer.from_text(text)
        c = data.Corpus(text, tok, "cpu", val_frac=0.1, seed=1337, split_by="hash")
        self.assertEqual(c.split_by, "hash")
        train_docs, val_docs = data.split_documents(text, 0.1, 1337, by="hash")
        self.assertEqual([d.strip() for d in c.train_docs], [d.strip() for d in train_docs])
        self.assertEqual([d.strip() for d in c.val_docs], [d.strip() for d in val_docs])
        self.assertEqual(tok.decode(c.val.tolist()), c.val_text)

    def test_default_corpus_is_order_mode(self):
        text = corpus(60)
        tok = data.CharTokenizer.from_text(text)
        c = data.Corpus(text, tok, "cpu")
        self.assertEqual(c.split_by, "order")
        self.assertEqual(c.val_text, data.group_split(text, 0.1, 1337)[1])
        explicit = data.Corpus("a b\n", tok, "cpu", validation_text="c\n")
        self.assertIsNone(explicit.split_by)
        self.assertIsNone(explicit.train_docs)


if __name__ == "__main__":
    unittest.main()
