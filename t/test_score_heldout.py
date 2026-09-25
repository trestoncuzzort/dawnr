"""Claims of checked correctness require evidence for each current program."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import score_heldout as score
import spec_check
import surface
import loop_filter


class ScoreEvidenceTests(unittest.TestCase):
    def test_clean_eval_ids_exclude_the_registered_overlap(self):
        policy = loop_filter.decontamination()
        self.assertEqual(score.clean_eval_ids(set(policy.overlap_eval_ids) | {1}), {1})

    def test_outcome_export_has_complete_boolean_maps_without_changing_the_table(self):
        split = self.root / "split.json"
        split.write_text(json.dumps({"eval_ids": [1, 999999]}), encoding="utf-8")
        outcomes = self.root / "outcomes.json"
        (self.data / "raw").mkdir()
        (self.data / "raw" / "1.json").write_text("{}", encoding="utf-8")
        stdout = io.StringIO()
        with patch.object(sys, "argv", [
            "score_heldout.py", "--split", str(split), "--outcomes", str(outcomes), "demo",
        ]), redirect_stdout(stdout):
            self.assertEqual(score.main(), 0)
        lines = stdout.getvalue().splitlines()
        self.assertEqual(lines[0],
                         "| tag | kernels | eval | answered | task | tests pass | graded | clean | converts | "
                         "spec disagrees | clean, spec checked | spec unchecked | wrong but proven | "
                         "clean, recited | clean, novel |")
        self.assertEqual(len(lines), 4)
        export = json.loads(outcomes.read_text(encoding="utf-8"))
        self.assertEqual(export["schema_version"], 1)
        for panel in ("all-2", "clean-2"):
            tagged = export["panels"][panel]["tags"]["demo"]
            self.assertEqual(export["panels"][panel]["task_ids"], [1, 999999])
            self.assertEqual(tagged["clean"], {"1": True, "999999": False})
            self.assertEqual(tagged["clean_count"], 1)
            self.assertEqual(tagged["spec_agrees"], {"1": False, "999999": False})
            self.assertEqual(tagged["spec_agrees_count"], 0)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "set"
        (self.data / "tasks").mkdir(parents=True)
        (self.root / "out").mkdir()
        self.name = "mbpp_1__identity"
        source = Path(__file__).parent / "tasks" / "abs.t"
        # Use an actual task so evidence hashes the same canonical form as spec_check.
        self.task = surface.parse_file(str(source))
        (self.data / "tasks" / f"{self.name}.json").write_text(json.dumps(self.task))
        (self.data / "extract.json").write_text(json.dumps({"1": {"stage": "task", "name": self.name}}))
        self.write_tests("pass")
        self.table(score.KERNELS)
        for target, value in (("HERE", self.root),):
            p = patch.object(score, target, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(score.se, "outdir", return_value=self.data)
        p.start()
        self.addCleanup(p.stop)

    def write_tests(self, outcome):
        rows = {"1": {"name": self.name, "overall": outcome}} if outcome else {}
        (self.data / "tests.json").write_text(json.dumps(rows))

    def table(self, kernels, flaky=False):
        cols = sorted(kernels)
        row = [score.CLEAN + (" (FLAKED)" if flaky and i == 0 else "") for i, _ in enumerate(cols)]
        (self.data / "kernels.md").write_text("| task | " + " | ".join(cols) + " |\n|---|" +
            "---|" * len(cols) + "\n| " + self.name + " | " + " | ".join(row) + " |\n")

    def evidence(self, status="agrees", draws=200, digest=None):
        result = {"status": status, "draws": draws,
                  "task_sha256": digest if digest is not None else spec_check.task_sha256(self.task)}
        (self.root / "out/spec-disagree.json").write_text(json.dumps({
            "tags": ["demo"], "disagree": [], "results": {f"demo/{self.name}": result}}))

    def test_tag_only_unknown_zero_draw_and_stale_are_unchecked(self):
        (self.root / "out/spec-disagree.json").write_text('{"tags":["demo"],"disagree":[]}')
        for label in ("tag-only", "refusal", "zero", "stale"):
            if label == "refusal": self.evidence(status="uncheckable")
            if label == "zero": self.evidence(draws=0)
            if label == "stale": self.evidence(digest="old")
            with self.subTest(label=label):
                row = score.score("demo", {1})
                self.assertEqual(row["clean"], 1)
                self.assertEqual(row["clean, spec checked"], 0)
                self.assertEqual(row["spec unchecked"], 1)

    def test_only_matching_explicit_agreement_counts(self):
        self.evidence()
        self.assertEqual(score.score("demo", {1})["clean, spec checked"], 1)
        self.evidence(status="disagrees")
        row = score.score("demo", {1})
        self.assertEqual(row["clean, spec checked"], 0)
        self.assertEqual(row["spec disagrees"], 1)
        self.assertEqual(row["spec unchecked"], 0)

    def test_partial_wrong_named_or_flaky_kernel_tables_cannot_be_clean(self):
        self.evidence()
        for cols, flaky in (({"lean"}, False), ((score.KERNELS - {"lean"}) | {"unknown"}, False),
                            (score.KERNELS, True)):
            self.table(cols, flaky)
            self.assertEqual(score.score("demo", {1})["clean"], 0)

    def corpus(self, *docs):
        path = self.root / "corpus.txt"
        path.write_text("\n\n\n".join(docs) + "\n")
        return score.corpus_keys(path)

    def test_a_clean_answer_that_is_a_training_document_is_recited(self):
        # the same program under another problem's name, behind a head: the shape of
        # mbpp_729 add_list answered with the corpus's mbpp_728 sum_list
        source = (Path(__file__).parent / "tasks" / "abs.t").read_text()
        doc = "Problem: absolute value\nSignature: other(int) -> int\n" + source.replace("task abs", "task other")
        row = score.score("demo", {1}, self.corpus(doc))
        self.assertEqual((row["clean"], row["clean, recited"], row["clean, novel"]), (1, 1, 0))

    def test_a_clean_answer_nothing_in_the_corpus_matches_is_novel(self):
        other = (Path(__file__).parent / "tasks" / "all_nonneg.t").read_text()
        row = score.score("demo", {1}, self.corpus(other))
        self.assertEqual((row["clean, recited"], row["clean, novel"]), (0, 1))

    def test_without_a_corpus_the_split_is_not_measured_rather_than_zero(self):
        row = score.score("demo", {1})
        self.assertEqual((row["clean, recited"], row["clean, novel"]), ("-", "-"))

    def test_an_unreadable_corpus_is_refused_not_skipped(self):
        source = (Path(__file__).parent / "tasks" / "abs.t").read_text()
        with self.assertRaises(SystemExit):
            self.corpus(source, "t 0\ntask broken(x: int) returns (r: int)\n{")
        # two documents with one blank line between them read as one: refused, because
        # the second one's answers would otherwise count as novel
        with self.assertRaises(SystemExit):
            self.corpus(source + "\n" + source.replace("task abs", "task twice"))

    def test_missing_tests_are_not_wrong(self):
        self.write_tests(None)
        self.assertEqual(score.score("demo", {1})["wrong but proven"], 0)
        self.write_tests("fail")
        self.assertEqual(score.score("demo", {1})["wrong but proven"], 1)


if __name__ == "__main__":
    unittest.main()
