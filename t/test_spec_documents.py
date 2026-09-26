"""A specification document beside every positive (r12 data build, track W3).

Distilling Step-by-Step (https://ar5iv.labs.arxiv.org/html/2305.02301, Table 2,
a 220M T5 on ANLI): the extra target trained as its own task scored 49.58;
folded into one target with the answer, 43.50; the plain finetune, 43.58. So
the specification is a SECOND document with the same head, never a prefix
inside the program document. Its marker line is `Spec:`, and every reader that
knows a head must know it: the stripper, the head aligner, and the answer
extraction (which cuts at the next Problem:/Signature:/t-header and then strips
what is in front of the reply).

What a spec document is not: a program. It has no body, so the recitation key
(loop_filter.key, computed from a parsed task) can never be computed for one;
what strip_head leaves of it is a declaration that surface.parse refuses, and
first_task finds no closing brace. These tests state that outcome.
"""
import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import head_align_corpus
import loop_filter
import loop_locallm
import surface

HERE = Path(__file__).resolve().parent
HEAD = "Problem: keep every element\nSignature: f(seq) -> seq\n"
EXAMPLE = "Example: f([1, 2]) == [1, 2]\n"
DECLARATION = ("t 1\ntask f(s: seq) returns (r: seq)\n"
               "  requires len(s) >= 0\n  ensures len(r) == len(s)\n")
PROGRAM = DECLARATION + "{\n  r := s;\n}\n"
SPEC = HEAD + "Spec:\n" + DECLARATION
TASK = ("t 1\n"
        "task {name}(a: int) returns (r: int)\n"
        "  ensures r == a\n"
        "{{\n"
        "  r := a;\n"
        "}}\n")


class SpecDocumentTests(unittest.TestCase):
    def test_the_spec_document_is_the_head_the_marker_and_the_declaration(self):
        doc = loop_locallm.spec_document(HEAD, PROGRAM)
        self.assertEqual(doc, SPEC)
        self.assertNotIn("{", doc)                      # no body, not even an empty one
        self.assertNotIn(":=", doc)

    def test_the_examples_head_is_carried_onto_the_spec_document(self):
        doc = loop_locallm.spec_document(HEAD + EXAMPLE, PROGRAM)
        self.assertTrue(doc.startswith(HEAD + EXAMPLE + "Spec:\n"))
        self.assertTrue(doc.endswith(DECLARATION))

    def test_a_spec_fun_is_specification_and_stays(self):
        program = (HERE / "tasks" / "factorial.t").read_text(encoding="utf-8")
        doc = loop_locallm.spec_document(HEAD, program)
        after = doc.split("Spec:\n", 1)[1]
        self.assertIn("spec fun fact(n: int): int", after)
        self.assertIn("ensures r == fact(n)", after)
        self.assertNotIn("{", after)
        self.assertNotIn("factorial(n - 1)", after)     # the recursive body is gone

    def test_a_positive_that_does_not_parse_has_no_spec_document(self):
        with self.assertRaises(surface.SurfaceError):
            loop_locallm.spec_document(HEAD, "t 1\ntask (\n")


class HeadMachineryTests(unittest.TestCase):
    def test_spec_is_a_head_line_for_the_stripper(self):
        self.assertEqual(loop_filter.strip_head(SPEC), DECLARATION)
        self.assertEqual(loop_filter.strip_head(HEAD + EXAMPLE + "Spec:\n" + DECLARATION), DECLARATION)
        self.assertEqual(loop_filter.strip_head(HEAD + PROGRAM), PROGRAM)

    def test_what_the_stripper_leaves_of_a_spec_document_is_not_a_program(self):
        with self.assertRaises(surface.SurfaceError):
            surface.parse(loop_filter.strip_head(SPEC))
        self.assertIsNone(loop_filter.first_task(SPEC))
        self.assertTrue(loop_filter.is_spec_document(SPEC))
        self.assertFalse(loop_filter.is_spec_document(HEAD + PROGRAM))
        self.assertFalse(loop_filter.is_spec_document(PROGRAM))

    def test_the_recitation_key_is_computed_for_programs_only(self):
        corpus = [HEAD + PROGRAM, SPEC]
        keys = [loop_filter.key(surface.parse(loop_filter.strip_head(d)))
                for d in corpus if not loop_filter.is_spec_document(d)]
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0], loop_filter.key(surface.parse(PROGRAM)))

    def test_head_align_keeps_spec_documents_aligned(self):
        documents, counts = head_align_corpus.align(HEAD + PROGRAM + "\n\n" + SPEC + "\n\n" + PROGRAM)
        self.assertEqual(len(documents), 3)
        self.assertEqual(documents[0], HEAD + PROGRAM)
        self.assertEqual(documents[1], SPEC)
        self.assertEqual(documents[2], "Signature: f(seq) -> seq\n" + PROGRAM)
        self.assertEqual(counts["heads_added"], 1)
        self.assertEqual(counts["already_headed"], 2)
        self.assertEqual(counts["spec_documents"], 1)
        self.assertEqual(counts["unparsed"], 0)

    def test_head_align_recognises_every_head_the_stripper_does(self):
        # an Example: line in front of a program is a head, not unparsed text
        documents, counts = head_align_corpus.align(EXAMPLE + PROGRAM)
        self.assertEqual(documents, [EXAMPLE + PROGRAM])
        self.assertEqual(counts["already_headed"], 1)
        self.assertEqual(counts["unparsed"], 0)

    def test_the_boundary_does_not_split_a_spec_document(self):
        self.assertNotIn("\n\n", SPEC)                  # locallm/data.py documents() splits on a blank line
        self.assertEqual(loop_locallm.REPLY_BOUNDARY.split(SPEC), [SPEC])
        self.assertEqual(head_align_corpus.SPLIT.split(SPEC), [SPEC])
        self.assertEqual(len(loop_locallm.REPLY_BOUNDARY.split(SPEC + "\n\n" + HEAD + PROGRAM)), 2)

    def test_a_reply_that_opens_with_spec_is_not_mistaken_for_a_program(self):
        # the corpus shows the model two continuations of one head; nothing in
        # the generate prompt selects the program, so a reply may open with Spec:
        next_doc = "Problem: next\nSignature: g(int) -> int\nt 1\ntask g(x: int) returns (r: int)\n{\n  r := x;\n}\n"
        reply = "Spec:\n" + DECLARATION + "\n\n" + next_doc
        body = loop_locallm.REPLY_BOUNDARY.split(reply, maxsplit=1)[0]
        self.assertEqual(body.strip() + "\n", "Spec:\n" + DECLARATION)   # cut before the next document
        with self.assertRaises(surface.SurfaceError):      # scored not well-formed, never as g
            surface.parse(loop_filter.strip_head(body))
        # a Spec: line in front of a whole program is stripped like any head
        self.assertEqual(surface.parse(loop_filter.strip_head("Spec:\n" + PROGRAM))["name"], "f")


class TempDirTestCase(unittest.TestCase):
    def tempdir(self) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name)


class CorpusCountTests(TempDirTestCase):
    """The document count rises by exactly the number of positives."""

    def setUp(self):
        pool = loop_locallm.se.pool("v5")
        policy = loop_filter.decontamination()
        self.ids = [i for i in sorted(int(k) for k in pool)
                    if i != 269 and i not in policy.exclude_train_ids][:3]

    def build(self, **over):
        d = self.tempdir()
        split = d / "split.json"
        split.write_text(json.dumps({"eval_ids": [269]}), encoding="utf-8")
        base = dict(pool="v5", split=split, base="", sft=[], lifted=False, out=str(d / "corpus.txt"),
                    examples=False, spec_docs=False)
        base.update(over)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = loop_locallm.cmd_corpus(argparse.Namespace(**base))
        return code, out.getvalue(), Path(base["out"])

    def sft(self, rows) -> Path:
        path = self.tempdir() / "sft.jsonl"
        path.write_text("".join(json.dumps({"task_id": tid, "task": "x", "chosen": chosen}) + "\n"
                                for tid, chosen in rows), encoding="utf-8")
        return path

    @staticmethod
    def docs(out: Path) -> list[str]:
        text = out.read_text(encoding="utf-8")
        # the boundary swallows the blank line before each document, so every
        # part is compared without its trailing newlines
        return [d.strip() + "\n" for d in loop_locallm.REPLY_BOUNDARY.split(text) if d.strip()]

    def test_the_document_count_rises_by_exactly_the_number_of_positives(self):
        rows = self.sft([(tid, "```t\n" + TASK.format(name=f"mbpp_{tid}__f") + "```") for tid in self.ids])
        code, said, out = self.build(sft=[str(rows)])
        self.assertEqual(code, 0)
        plain = self.docs(out)
        code, said, out = self.build(sft=[str(rows)], spec_docs=True)
        self.assertEqual(code, 0)
        with_spec = self.docs(out)
        self.assertEqual(len(plain), len(self.ids))
        self.assertEqual(len(with_spec), len(plain) + len(self.ids))
        self.assertEqual(sum(loop_filter.is_spec_document(d) for d in with_spec), len(self.ids))
        self.assertIn(f"{len(self.ids)} spec documents", said)
        for doc in with_spec:
            if loop_filter.is_spec_document(doc):
                self.assertNotIn("{", doc)
                self.assertTrue(doc.startswith("Problem: "))
        # the corpus is the same documents plus the spec documents, nothing else changed
        self.assertEqual([d for d in with_spec if not loop_filter.is_spec_document(d)], plain)

    def test_lifted_and_committed_documents_get_no_spec_document(self):
        lifted = self.tempdir()
        (lifted / "lifted_one.json").write_text(
            json.dumps(surface.parse(TASK.format(name="lifted_one"))), encoding="utf-8")
        committed = self.tempdir()
        (committed / "c_one.t").write_text(TASK.format(name="c_one"), encoding="utf-8")
        rows = self.sft([(self.ids[0], "```t\n" + TASK.format(name=f"mbpp_{self.ids[0]}__f") + "```")])
        with mock.patch.object(loop_locallm, "LIFTED_DIR", lifted), \
             mock.patch.object(loop_locallm, "LIFTED_TABLE", self.table(["lifted_one"])), \
             mock.patch.object(loop_locallm, "COMMITTED_DIR", committed), \
             mock.patch.object(loop_locallm, "AGREEMENT", self.table(["c_one"])):
            code, said, out = self.build(sft=[str(rows)], lifted=True, spec_docs=True)
        self.assertEqual(code, 0)
        docs = self.docs(out)
        self.assertEqual(len(docs), 4)                  # program, its spec, lifted, committed
        self.assertEqual(sum(loop_filter.is_spec_document(d) for d in docs), 1)
        self.assertIn("1 spec documents", said)
        self.assertIn("1 lifted, 1 committed", said)

    def test_a_held_out_positive_gets_no_document_of_either_kind(self):
        rows = self.sft([(269, "```t\n" + TASK.format(name="mbpp_269__f") + "```"),
                         (self.ids[0], "```t\n" + TASK.format(name=f"mbpp_{self.ids[0]}__f") + "```")])
        code, said, out = self.build(sft=[str(rows)], spec_docs=True)
        self.assertEqual(code, 0)
        text = out.read_text(encoding="utf-8")
        self.assertNotIn("mbpp_269", text)
        self.assertEqual(len(self.docs(out)), 2)
        self.assertIn("1 document(s) excluded", said)

    def test_spec_docs_with_no_positive_to_write_for_is_refused(self):
        base = self.tempdir() / "base.txt"
        base.write_text(TASK.format(name="bare"), encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            self.build(base=str(base), spec_docs=True)
        self.assertIn("0 spec documents", str(caught.exception))

    def test_a_positive_that_does_not_parse_is_named_under_spec_docs(self):
        rows = self.sft([(self.ids[0], "```t\nt 1\ntask (\n```")])
        with self.assertRaises(SystemExit) as caught:
            self.build(sft=[str(rows)], spec_docs=True)
        self.assertIn(f"task_id={self.ids[0]}", str(caught.exception))
        self.assertIn("no specification", str(caught.exception))

    def table(self, names) -> Path:
        cells = " | ".join([loop_locallm.CLEAN] * 7)
        rows = "\n".join(f"| {name} | {cells} |" for name in names)
        path = self.tempdir() / "AGREEMENT.md"
        path.write_text("| task | dafny | verus | spark | framac | lean | rocq | fstar |\n"
                        "|---|---|---|---|---|---|---|---|\n" + rows + "\n"
                        "\n| kernel | version |\n|---|---|\n| dafny | 4.11.0 |\n", encoding="utf-8")
        return path


class FlagTests(unittest.TestCase):
    def test_corpus_takes_spec_docs(self):
        args = loop_locallm.build_parser().parse_args(
            ["corpus", "--split", "x.json", "--spec-docs"])
        self.assertTrue(args.spec_docs)
        args = loop_locallm.build_parser().parse_args(["corpus", "--split", "x.json"])
        self.assertFalse(args.spec_docs)


if __name__ == "__main__":
    unittest.main()
