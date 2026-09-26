"""Claims of checked correctness require evidence for each current program.

A4: a set with fewer answers than held-out problems is refused, not scored as if whole.
A6: a set whose records were decoded under different settings is refused.
E: the outcome export carries one Boolean per problem for every quantity a paired test needs.
"""
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


RECORD = {"task_id": 1, "fn": "identity", "model": "locallm:t/out/demo", "digest": "1 params",
          "pool_version": "v5", "prompt_version": "locallm-head",
          "options": {"temperature": 0.0, "top_k": 20, "max_new_tokens": 1200,
                      "tokenizer": "BPETokenizer", "seed": 1},
          "messages": [], "reply": "```t\n```", "done_reason": "length"}


class ScoreEvidenceTests(unittest.TestCase):
    def test_clean_eval_ids_exclude_the_registered_overlap(self):
        policy = loop_filter.decontamination()
        self.assertEqual(score.clean_eval_ids(set(policy.overlap_eval_ids) | {1}), {1})

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "set"
        (self.data / "tasks").mkdir(parents=True)
        (self.data / "raw").mkdir()
        (self.root / "out").mkdir()
        self.name = "mbpp_1__identity"
        source = Path(__file__).parent / "tasks" / "abs.t"
        # Use an actual task so evidence hashes the same canonical form as spec_check.
        self.task = surface.parse_file(str(source))
        (self.data / "tasks" / f"{self.name}.json").write_text(json.dumps(self.task))
        (self.data / "extract.json").write_text(json.dumps({"1": {"stage": "task", "name": self.name}}))
        self.write_tests("pass")
        self.table(score.KERNELS)
        self.raw(1)
        for target, value in (("HERE", self.root),):
            p = patch.object(score, target, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(score.se, "outdir", return_value=self.data)
        p.start()
        self.addCleanup(p.stop)

    def raw(self, tid, text=None, **changes):
        record = json.loads(json.dumps(RECORD))
        record["task_id"] = tid
        for key, value in changes.items():
            if key.startswith("opt_"):
                record["options"][key[4:]] = value
            else:
                record[key] = value
        (self.data / "raw" / f"{tid}.json").write_text(text if text is not None else json.dumps(record))

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

    # -- A4 ---------------------------------------------------------------------------------------

    def test_a_partial_answer_set_is_refused_unless_allowed(self):
        with self.assertRaises(SystemExit) as cm:
            score.score("demo", {1, 2})
        self.assertIn("demo", str(cm.exception))
        self.assertIn("1 of 2", str(cm.exception))
        self.assertIn("2", str(cm.exception))
        row = score.score("demo", {1, 2}, allow_partial=True)
        self.assertEqual((row["answered"], row["eval"], row["clean"]), (1, 2, 1))

    def test_raw_files_that_are_not_eval_ids_do_not_count_as_answers(self):
        # 368 raw files and 161 of 232 eval ids answered: a file count would pass it
        self.raw(77)
        self.raw(78)
        with self.assertRaises(SystemExit):
            score.score("demo", {1, 2})

    # -- A6 ---------------------------------------------------------------------------------------

    def test_records_decoded_under_different_settings_are_refused(self):
        self.raw(2, opt_temperature=0.5)
        with self.assertRaises(SystemExit) as cm:
            score.score("demo", {1, 2})
        self.assertIn("temperature", str(cm.exception))
        self.assertIn("demo", str(cm.exception))
        self.raw(2, model="locallm:t/out/other")
        with self.assertRaises(SystemExit) as cm:
            score.score("demo", {1, 2})
        self.assertIn("model", str(cm.exception))

    def test_an_option_the_plan_did_not_name_still_counts(self):
        # ollama records call the token limit num_predict, and the one real mixed set
        # (deepseek-coder-v2-16b-v4-s1) differs only there and in num_ctx
        self.raw(1, opt_num_predict=3072)
        self.raw(2, opt_num_predict=2048)
        with self.assertRaises(SystemExit) as cm:
            score.score("demo", {1, 2})
        self.assertIn("num_predict", str(cm.exception))

    def test_a_note_and_a_number_spelling_do_not_make_records_differ(self):
        self.raw(2, opt_note="rerun after the card was freed", opt_temperature=0)
        row = score.score("demo", {1, 2})
        self.assertEqual(row["answered"], 2)
        self.assertEqual(score.decoding_key(json.loads((self.data / "raw" / "1.json").read_text())),
                         score.decoding_key(json.loads((self.data / "raw" / "2.json").read_text())))

    def test_digest_is_not_part_of_the_decoding_key(self):
        # student-r6-v3 carries two torch builds around one adapter, by design
        self.raw(2, digest="torch 2.11.0+cu128")
        self.assertEqual(score.score("demo", {1, 2})["answered"], 2)

    def test_an_unreadable_record_is_refused_by_name(self):
        self.raw(2, text="{")
        with self.assertRaises(SystemExit) as cm:
            score.score("demo", {1, 2})
        self.assertIn("2.json", str(cm.exception))

    # -- E ----------------------------------------------------------------------------------------

    def run_main(self, *args):
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["score_heldout.py", *args]), redirect_stdout(stdout):
            rc = score.main()
        return rc, stdout.getvalue().splitlines()

    def test_outcome_export_has_complete_boolean_maps_without_changing_the_table(self):
        split = self.root / "split.json"
        split.write_text(json.dumps({"eval_ids": [1, 999999]}), encoding="utf-8")
        outcomes = self.root / "outcomes.json"
        with self.assertRaises(SystemExit):
            self.run_main("--split", str(split), "--outcomes", str(outcomes), "demo")
        rc, lines = self.run_main("--split", str(split), "--outcomes", str(outcomes),
                                  "--allow-partial", "demo")
        self.assertEqual(rc, 0)
        self.assertEqual(lines[0],
                         "| tag | kernels | eval | answered | task | tests pass | graded | clean | converts | "
                         "spec disagrees | clean, spec checked | spec unchecked | wrong but proven | "
                         "clean, recited | clean, novel |")
        self.assertEqual(len(lines), 4)
        export = json.loads(outcomes.read_text(encoding="utf-8"))
        self.assertEqual(export["schema_version"], 2)
        self.assertEqual(export["split"], str(split))
        for panel in ("all-2", "clean-2"):
            tagged = export["panels"][panel]["tags"]["demo"]
            self.assertEqual(export["panels"][panel]["task_ids"], [1, 999999])
            self.assertEqual(tagged["clean"], {"1": True, "999999": False})
            self.assertEqual(tagged["clean_count"], 1)
            self.assertEqual(tagged["spec_agrees"], {"1": False, "999999": False})
            self.assertEqual(tagged["spec_agrees_count"], 0)
            self.assertEqual(tagged["tests_pass"], {"1": True, "999999": False})
            self.assertEqual(tagged["tests_pass_count"], 1)
            self.assertEqual((tagged["answered_count"], tagged["partial"]), (1, True))
            self.assertNotIn("recited", tagged)

    def test_outcome_export_carries_recitation_when_a_corpus_is_given(self):
        split = self.root / "split.json"
        split.write_text(json.dumps({"eval_ids": [1]}), encoding="utf-8")
        outcomes = self.root / "outcomes.json"
        source = (Path(__file__).parent / "tasks" / "abs.t").read_text()
        doc = "Problem: absolute value\nSignature: other(int) -> int\n" + source.replace("task abs", "task other")
        corpus = self.root / "corpus.txt"
        corpus.write_text(doc + "\n")
        rc, _ = self.run_main("--split", str(split), "--outcomes", str(outcomes),
                              "--corpus", f"demo={corpus}", "demo")
        self.assertEqual(rc, 0)
        tagged = json.loads(outcomes.read_text())["panels"]["all-1"]["tags"]["demo"]
        self.assertEqual((tagged["recited"], tagged["recited_count"], tagged["partial"]),
                         ({"1": True}, 1, False))

    # -- the evidence rules that already held -----------------------------------------------------

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
