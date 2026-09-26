"""Regression tests for explicit preflight answer-set and input scopes."""
import json
import io
import shlex
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest import mock

import preflight


HEAD = ("| task | dafny | verus | spark | framac | lean | rocq | fstar |\n"
        "|---|---|---|---|---|---|---|---|\n")
OK = "verified / refuted"
ROW = ("| mbpp_1__f | " + " | ".join([OK] * 7) + " |\n")


def answer_set(root: Path, name: str, complete: bool = True) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "kernels.md").write_text(HEAD + ROW, encoding="utf-8")
    if complete:
        (directory / "tests.json").write_text(
            json.dumps({"1": {"name": "mbpp_1__f", "overall": "pass"}}), encoding="utf-8")
        (directory / "extract.json").write_text(
            json.dumps({"1": {"name": "mbpp_1__f"}}), encoding="utf-8")
    return directory


@contextmanager
def harmless_main_checks():
    names = (
        "check_lab_quiet", "check_kernels", "check_prompt", "check_grammar", "check_tokenizer", "check_split", "check_data",
        "check_agreement_covers_tasks", "check_spec_agreement", "check_keys", "check_space", "check_evaluator",
    )
    with mock.patch.multiple(preflight, **{name: mock.DEFAULT for name in names}) as checks:
        for check in checks.values():
            check.return_value = True
        yield


class PreflightScopeTests(unittest.TestCase):
    def tempdir(self) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def test_pretraining_defers_answer_quality_without_discovering_history(self):
        root = self.tempdir()
        se = root / "spec-experiment"
        answer_set(se, "old-incomplete", complete=False)
        split = root / "split.json"
        corpus = root / "current.txt"
        split.write_text(json.dumps({"eval_ids": []}), encoding="utf-8")
        corpus.write_text("safe current training row\n", encoding="utf-8")

        with mock.patch.object(preflight, "SE", se), \
                mock.patch.object(preflight, "tables", side_effect=AssertionError("history was scanned")), \
                harmless_main_checks(), \
                mock.patch("sys.argv", ["preflight.py", "--split", str(split), "--corpus", str(corpus), "--quick"]):
            preflight.WARNED.clear()
            self.assertEqual(preflight.main(), 0)

    def test_main_fails_closed_when_answer_set_does_not_exist(self):
        root = self.tempdir()
        split = root / "split.json"
        corpus = root / "current.txt"
        split.write_text(json.dumps({"eval_ids": []}), encoding="utf-8")
        corpus.write_text("safe current training row\n", encoding="utf-8")

        with mock.patch.object(preflight, "SE", root / "spec-experiment"), \
                harmless_main_checks(), \
                mock.patch("sys.argv", ["preflight.py", "--split", str(split), "--corpus", str(corpus),
                                         "--answer-set", "missing", "--quick"]):
            preflight.WARNED.clear()
            self.assertEqual(preflight.main(), 1)

    def test_explicit_current_answer_set_ignores_old_incomplete_history(self):
        root = self.tempdir()
        se = root / "spec-experiment"
        current = answer_set(se, "current", complete=True)
        answer_set(se, "old-incomplete", complete=False)

        with mock.patch.object(preflight, "SE", se), mock.patch.object(preflight, "OUT", root / "out"):
            ok, selected = preflight.select_answer_sets(["current"], audit_history=False)
            self.assertTrue(ok)
            self.assertEqual(selected, [current])
            self.assertTrue(preflight.check_result_quality(selected))

    def test_unknown_explicit_answer_set_fails_closed(self):
        root = self.tempdir()
        with mock.patch.object(preflight, "SE", root / "spec-experiment"):
            ok, selected = preflight.select_answer_sets(["missing"], audit_history=False)
        self.assertFalse(ok)
        self.assertEqual(selected, [])

    def test_audit_history_deliberately_includes_old_incomplete_set(self):
        root = self.tempdir()
        se = root / "spec-experiment"
        answer_set(se, "current", complete=True)
        answer_set(se, "old-incomplete", complete=False)

        with mock.patch.object(preflight, "SE", se), mock.patch.object(preflight, "OUT", root / "out"):
            ok, selected = preflight.select_answer_sets(["current"], audit_history=True)
            self.assertTrue(ok)
            self.assertEqual({path.name for path in selected}, {"current", "old-incomplete"})
            self.assertFalse(preflight.check_result_quality(selected))

    def test_spec_gate_checks_only_selected_training_files(self):
        root = self.tempdir()
        out = root / "out"
        (out / "loop").mkdir(parents=True)
        disagree = "t 1\ntask mbpp_1__f(a: int) returns (r: int) { r := a; }"
        (out / "spec-disagree.json").write_text(json.dumps({
            "disagree": ["old/mbpp_1__f"],
            "programs": {"old/mbpp_1__f": disagree},
        }), encoding="utf-8")
        # This historical filename was hard-coded by the old implementation;
        # it must not affect a preflight that selected only `current`.
        (out / "loop" / "sft-r4.jsonl").write_text(disagree, encoding="utf-8")
        current = root / "current.jsonl"
        current.write_text("safe current training row\n", encoding="utf-8")

        with mock.patch.object(preflight, "OUT", out):
            self.assertTrue(preflight.check_spec_agreement([current], []))

    def test_spec_gate_rejects_a_disagreement_in_selected_training_file(self):
        root = self.tempdir()
        out = root / "out"
        out.mkdir()
        disagree = "t 1\ntask mbpp_1__f(a: int) returns (r: int) { r := a; }"
        (out / "spec-disagree.json").write_text(json.dumps({
            "disagree": ["old/mbpp_1__f"],
            "programs": {"old/mbpp_1__f": disagree},
        }), encoding="utf-8")
        current = root / "current.jsonl"
        current.write_text(disagree, encoding="utf-8")

        with mock.patch.object(preflight, "OUT", out):
            self.assertFalse(preflight.check_spec_agreement([current], []))

    def test_spec_gate_decodes_a_selected_jsonl_before_matching_programs(self):
        root = self.tempdir()
        out = root / "out"
        out.mkdir()
        disagree = "t 1\ntask mbpp_1__f(a: int) returns (r: int) { r := a; }"
        (out / "spec-disagree.json").write_text(json.dumps({
            "disagree": ["old/mbpp_1__f"],
            "programs": {"old/mbpp_1__f": disagree},
        }), encoding="utf-8")
        current = root / "current.jsonl"
        current.write_text(json.dumps({"chosen": disagree}) + "\n", encoding="utf-8")

        with mock.patch.object(preflight, "OUT", out):
            self.assertFalse(preflight.check_spec_agreement([current], []))

    def test_spec_gate_fails_closed_on_a_non_object_report(self):
        root = self.tempdir()
        out = root / "out"
        out.mkdir()
        (out / "spec-disagree.json").write_text("[]", encoding="utf-8")
        current = root / "current.jsonl"
        current.write_text("safe current training row\n", encoding="utf-8")

        with mock.patch.object(preflight, "OUT", out):
            self.assertFalse(preflight.check_spec_agreement([current], []))

    def test_spec_gate_fails_closed_on_an_unmapped_disagreement(self):
        root = self.tempdir()
        out = root / "out"
        out.mkdir()
        (out / "spec-disagree.json").write_text(json.dumps({
            "disagree": ["old/mbpp_1__f"],
            "programs": {},
        }), encoding="utf-8")
        current = root / "current.jsonl"
        current.write_text("safe current training row\n", encoding="utf-8")

        with mock.patch.object(preflight, "OUT", out):
            self.assertFalse(preflight.check_spec_agreement([current], []))

    def test_data_gate_includes_the_selected_current_corpus(self):
        root = self.tempdir()
        split = root / "t" / "split.json"
        corpus = root / "t" / "out" / "current.txt"
        split.parent.mkdir(parents=True)
        corpus.parent.mkdir(parents=True)
        split.write_text(json.dumps({"eval_ids": []}), encoding="utf-8")
        corpus.write_text("safe current training row\n", encoding="utf-8")
        output = io.StringIO()

        with mock.patch.object(preflight, "ROOT", root), \
                mock.patch.object(preflight, "run_text", return_value=""), \
                mock.patch.object(preflight.subprocess, "run",
                                  return_value=mock.Mock(stdout="t/split.json\n")), \
                redirect_stdout(output):
            self.assertTrue(preflight.check_data(Path("t/split.json"), None, [],
                                                  [Path("t/out/current.txt")]))
        self.assertIn("t/out/current.txt", output.getvalue())

    def test_data_gate_rejects_a_current_input_outside_the_repository(self):
        root = self.tempdir()
        outside = root.parent / "not-in-this-repository.txt"
        output = io.StringIO()

        with mock.patch.object(preflight, "ROOT", root), \
                mock.patch.object(preflight, "run_text", return_value=""), \
                redirect_stdout(output):
            self.assertFalse(preflight.check_data(Path("t/split.json"), None, [], [outside]))
        self.assertIn("inside this repository", output.getvalue())

    def test_data_gate_quotes_a_selected_path_before_ssh(self):
        root = self.tempdir()
        split = root / "t" / "split.json"
        corpus = root / "t" / "out" / 'unsafe "$(command)"; space.txt'
        split.parent.mkdir(parents=True)
        corpus.parent.mkdir(parents=True)
        split.write_text(json.dumps({"eval_ids": []}), encoding="utf-8")
        corpus.write_text("safe current training row\n", encoding="utf-8")
        calls = []
        relative = str(corpus.relative_to(root))

        def run(args, **_kwargs):
            calls.append(args)
            if args[0] == "git":
                return mock.Mock(stdout=f"t/split.json\n{relative}\n")
            return mock.Mock(returncode=0, stdout="")

        with mock.patch.object(preflight, "ROOT", root), \
                mock.patch.object(preflight, "run_text", return_value=""), \
                mock.patch.object(preflight.subprocess, "run", side_effect=run):
            self.assertTrue(preflight.check_data(Path("t/split.json"), "lab", [], [Path(relative)]))
        remote_command = calls[-1][-1]
        self.assertIn(f"[ -e {shlex.quote(relative)} ]", remote_command)
        self.assertNotIn(f'[ -e "{relative}"', remote_command)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
