"""The selector sees the two shown examples and nothing else, and chooses the way its sources say.

The problem is f(x) = x*x with points (1, 1), (30, 900), (40, 1600): discriminative()
ranks the last two highest, so the hidden point is index 0, the trap spec_check's own
draw shaping falls into on 20 of the 232 eval ids.
"""
import ast
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import loop_filter
import loop_locallm
import select_candidates as sc
import spec_experiment as se

HERE = Path(__file__).resolve().parent

SQUARE = "t 1\ntask sq(x: int) returns (r: int)\n  ensures r == x * x\n{\n  r := x * x;\n}\n"
BADSPEC = "t 1\ntask sq(x: int) returns (r: int)\n  ensures r == x + x\n{\n  r := x * x;\n}\n"
MEMO = "t 1\ntask sq(x: int) returns (r: int)\n  requires x == 30 or x == 40\n  ensures r == x * x\n{\n  r := x * x;\n}\n"
HARD = ("t 1\ntask sq(x: int) returns (r: int)\n  ensures true\n{\n  if x == 30 {\n    r := 900;\n  } else {\n"
        "    if x == 40 {\n      r := 1600;\n    } else {\n      r := 0;\n    }\n  }\n}\n")
PLUS6 = "t 1\ntask sq(x: int) returns (r: int)\n  ensures r == x + 6\n{\n  r := x + 6;\n}\n"
PLUS7 = "t 1\ntask sq(x: int) returns (r: int)\n  ensures r == x + 7\n{\n  r := x + 7;\n}\n"
GARBAGE = "not a program at all\n"

POINTS = [{"args": [["int", 1]], "expected": ["int", 1]},
          {"args": [["int", 30]], "expected": ["int", 900]},
          {"args": [["int", 40]], "expected": ["int", 1600]}]


def fake_pool(hidden=None, rec=None):
    points = [dict(p) for p in POINTS]
    if hidden is not None:
        points[0] = hidden
    return {7: {"task_id": 7, "fn": "sq", "rec": rec if rec is not None else {"text": "square it"},
                "points": points},
            8: {"task_id": 8, "fn": "sq", "rec": {"text": "square it again"}, "points": [dict(p) for p in POINTS]}}


class Trip(BaseException):
    """Not an Exception: nothing in the selector may swallow it."""


class Tripwire(dict):
    """A point (or rec) whose content is readable only while the prompt builder ranks the points.

    The dict storage stays empty, so json.dumps and other C-level readers see {}; every
    Python-level read goes through _guard, which allows it only when
    loop_locallm.discriminative's code object is on the stack."""

    def __init__(self, real, log):
        super().__init__()
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_log", log)

    def _guard(self, what):
        frame = sys._getframe(2)
        while frame is not None:
            if frame.f_code is loop_locallm.discriminative.__code__:
                return
            frame = frame.f_back
        self._log.append(what)
        raise Trip(what)

    def __getitem__(self, key):
        self._guard(f"getitem {key}")
        return self._real[key]

    def get(self, key, default=None):
        self._guard(f"get {key}")
        return self._real.get(key, default)

    def __contains__(self, key):
        self._guard(f"contains {key}")
        return key in self._real

    def keys(self):
        self._guard("keys")
        return self._real.keys()

    def items(self):
        self._guard("items")
        return self._real.items()

    def values(self):
        self._guard("values")
        return self._real.values()

    def __iter__(self):
        self._guard("iter")
        return iter(self._real)

    def __len__(self):
        self._guard("len")
        return len(self._real)


def write_candidates(root, tid, programs, logprobs=None, options=None, model="locallm:m", fmt="locallm", **extra):
    root.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, prog in enumerate(programs):
        text = prog if fmt == "locallm" else "```t\n" + prog.rstrip("\n") + "\n```"
        line = {"text": text, "logprob": (logprobs[i] if logprobs else -1.0),
                "options": options if options is not None else {"temperature": 0.5, "top_k": 20},
                "model": model, "tokens": len(prog.split())}
        line.update(extra)
        lines.append(json.dumps(line))
    (root / f"{tid}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


class Harness:
    """A temp OUT_ROOT, a split with the fake pool's ids, and a way to run main()."""

    def __init__(self, ids=(7,), pool=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cands = self.root / "cands"
        self.split = self.root / "split.json"
        self.split.write_text(json.dumps({"pool": "v3", "eval_ids": list(ids), "train_ids": []}), encoding="utf-8")
        self.pool = pool if pool is not None else fake_pool()
        self.out_root = self.root / "spec-experiment"

    def run(self, tag="sel", samples=None, extra=()):
        argv = ["--candidates", str(self.cands), "--split", str(self.split), "--tag", tag,
                "--samples", str(samples), *extra]
        with mock.patch.object(se, "pool", lambda version="v1": self.pool), \
                mock.patch.object(se, "OUT_ROOT", self.out_root):
            return sc.main(argv)

    def record(self, tid, tag="sel"):
        return json.loads((self.out_root / tag / "raw" / f"{tid}.json").read_text(encoding="utf-8"))

    def selection(self, tag="sel"):
        return json.loads((self.out_root / tag / "selection.json").read_text(encoding="utf-8"))

    def raw_files(self, tag="sel"):
        d = self.out_root / tag / "raw"
        return sorted(p.name for p in d.glob("*")) if d.exists() else []

    def close(self):
        self.tmp.cleanup()


def body_of(record):
    return se.find_block(record["reply"]).strip() + "\n"


class Choice(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.addCleanup(self.h.close)

    def test_the_filter_drops_the_largest_group_when_it_fails_a_shown_example(self):
        write_candidates(self.h.cands, 7, [PLUS6, PLUS6, PLUS6, SQUARE])
        self.assertEqual(self.h.run(samples=4), 0)
        rec = self.h.record(7)
        self.assertEqual(body_of(rec).replace("mbpp_7__sq", "sq"), SQUARE)
        self.assertEqual(rec["selection"]["tier"], "shown")
        self.assertEqual(rec["selection"]["counts"], {"samples": 4, "well_formed": 4, "shown_pass": 1})

    def test_the_largest_cluster_beats_a_higher_logprob(self):
        write_candidates(self.h.cands, 7, [SQUARE, HARD, SQUARE], logprobs=[-2.0, -0.1, -2.5])
        self.h.run(samples=3)
        rec = self.h.record(7)
        self.assertEqual(body_of(rec).replace("mbpp_7__sq", "sq"), SQUARE)
        self.assertEqual(rec["selection"]["cluster_size"], 2)
        self.assertEqual(rec["selection"]["clusters"], [2, 1])

    def test_equal_clusters_go_to_the_likeliest_member_in_both_directions(self):
        write_candidates(self.h.cands, 7, [SQUARE, HARD], logprobs=[-1.0, -0.5])
        self.h.run(samples=2, tag="a")
        self.assertEqual(body_of(self.h.record(7, "a")).replace("mbpp_7__sq", "sq"), HARD)
        write_candidates(self.h.cands, 7, [SQUARE, HARD], logprobs=[-0.5, -1.0])
        self.h.run(samples=2, tag="b")
        self.assertEqual(body_of(self.h.record(7, "b")).replace("mbpp_7__sq", "sq"), SQUARE)

    def test_the_representative_has_a_specification_that_holds_at_the_examples(self):
        # same behaviour, so one cluster; the likelier member's ensures is false at the shown examples
        write_candidates(self.h.cands, 7, [BADSPEC, SQUARE], logprobs=[-0.1, -3.0])
        self.h.run(samples=2)
        rec = self.h.record(7)
        self.assertEqual(body_of(rec).replace("mbpp_7__sq", "sq"), SQUARE)
        self.assertEqual(rec["selection"]["cluster_size"], 2)
        self.assertTrue(rec["selection"]["spec_ok"])

    def test_a_memorising_majority_does_not_win(self):
        # MEMO is defined only at the shown inputs; with the shown inputs excluded from the
        # signature it has no output on any draw and groups with nothing.
        inputs = sc.draw_inputs(fake_pool()[7]["points"][1:], 24, 0, 7)
        self.assertFalse(any(p["args"][0][1] in (30, 40) for p in inputs), "the draws must miss the shown values")
        write_candidates(self.h.cands, 7, [MEMO, MEMO, MEMO, SQUARE, SQUARE], logprobs=[-0.1] * 3 + [-2.0] * 2)
        self.h.run(samples=5)
        rec = self.h.record(7)
        self.assertEqual(body_of(rec).replace("mbpp_7__sq", "sq"), SQUARE)
        self.assertEqual(rec["selection"]["clusters"], [2, 1, 1, 1])

    def test_tier_two_falls_back_to_well_formed_samples(self):
        write_candidates(self.h.cands, 7, [PLUS6, PLUS7, PLUS6])
        self.h.run(samples=3)
        rec = self.h.record(7)
        self.assertEqual(rec["selection"]["tier"], "well-formed")
        self.assertEqual(body_of(rec).replace("mbpp_7__sq", "sq"), PLUS6)

    def test_tier_three_copies_the_greedy_reply_verbatim_with_identical_options(self):
        greedy_dir = self.h.out_root / "greedy" / "raw"
        greedy_dir.mkdir(parents=True)
        greedy_reply = "```t\n" + SQUARE.replace("sq(", "mbpp_7__sq(") + "```"
        greedy_dir.joinpath("7.json").write_text(json.dumps(
            {"task_id": 7, "fn": "sq", "model": "locallm:g", "reply": greedy_reply, "done_reason": "length",
             "options": {"temperature": 0.0}}), encoding="utf-8")
        self.h.split.write_text(json.dumps({"pool": "v3", "eval_ids": [7, 8], "train_ids": []}), encoding="utf-8")
        write_candidates(self.h.cands, 7, [GARBAGE, GARBAGE])
        write_candidates(self.h.cands, 8, [SQUARE, SQUARE])
        self.h.run(samples=2, extra=["--greedy-tag", "greedy"])
        r7, r8 = self.h.record(7), self.h.record(8)
        self.assertEqual(r7["reply"], greedy_reply)
        self.assertEqual(r7["selection"]["tier"], "greedy")
        self.assertEqual(r7["selection"]["origin"]["tag"], "greedy")
        self.assertEqual(r7["options"], r8["options"], "A6: every record of a tag carries identical options")
        self.assertEqual(r7["model"], r8["model"])
        self.assertEqual(self.h.selection()["tiers"], {"shown": 1, "well-formed": 0, "greedy": 1})


class Refusals(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.addCleanup(self.h.close)

    def assertRefusedAndNothingWritten(self, samples=2, extra=(), pattern=""):
        with self.assertRaises(SystemExit) as cm:
            self.h.run(samples=samples, extra=extra)
        self.assertRegex(str(cm.exception), pattern)
        self.assertEqual(self.h.raw_files(), [])
        self.assertFalse((self.h.out_root / "sel" / "selection.json").exists())

    def test_a_missing_candidates_file_is_refused(self):
        self.h.cands.mkdir()
        self.assertRefusedAndNothingWritten(pattern="7.jsonl")

    def test_an_empty_or_malformed_file_is_refused(self):
        self.h.cands.mkdir()
        (self.h.cands / "7.jsonl").write_text("", encoding="utf-8")
        self.assertRefusedAndNothingWritten(pattern="7.jsonl")
        (self.h.cands / "7.jsonl").write_text('{"text": "x", "logprob": -1}\n{not json\n', encoding="utf-8")
        self.assertRefusedAndNothingWritten(pattern="7.jsonl:2")

    def test_the_wrong_sample_count_is_refused(self):
        write_candidates(self.h.cands, 7, [SQUARE, SQUARE, SQUARE])
        self.assertRefusedAndNothingWritten(samples=2, pattern="3 samples")

    def test_mixed_options_are_refused(self):
        write_candidates(self.h.cands, 7, [SQUARE, SQUARE])
        lines = (self.h.cands / "7.jsonl").read_text(encoding="utf-8").splitlines()
        second = json.loads(lines[1])
        second["options"]["temperature"] = 0.9
        (self.h.cands / "7.jsonl").write_text(lines[0] + "\n" + json.dumps(second) + "\n", encoding="utf-8")
        self.assertRefusedAndNothingWritten(pattern="options")

    def test_an_id_missing_from_the_pool_is_refused(self):
        self.h.split.write_text(json.dumps({"pool": "v3", "eval_ids": [7, 9], "train_ids": []}), encoding="utf-8")
        write_candidates(self.h.cands, 7, [SQUARE, SQUARE])
        write_candidates(self.h.cands, 9, [SQUARE, SQUARE])
        self.assertRefusedAndNothingWritten(pattern="9")

    def test_a_needed_greedy_record_that_is_missing_or_mismatched_is_refused(self):
        write_candidates(self.h.cands, 7, [GARBAGE, GARBAGE])
        self.assertRefusedAndNothingWritten(pattern="greedy")
        greedy_dir = self.h.out_root / "greedy" / "raw"
        greedy_dir.mkdir(parents=True)
        greedy_dir.joinpath("7.json").write_text(json.dumps(
            {"task_id": 7, "fn": "other", "model": "m", "reply": "```t\n" + SQUARE + "```", "options": {}}),
            encoding="utf-8")
        self.assertRefusedAndNothingWritten(extra=["--greedy-tag", "greedy"], pattern="fn")

    def test_an_output_that_already_holds_answers_is_refused(self):
        write_candidates(self.h.cands, 7, [SQUARE, SQUARE])
        (self.h.out_root / "sel" / "raw").mkdir(parents=True)
        (self.h.out_root / "sel" / "raw" / "7.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            self.h.run(samples=2)
        self.assertIn("already", str(cm.exception))
        self.assertEqual((self.h.out_root / "sel" / "raw" / "7.json").read_text(encoding="utf-8"), "{}")


class OnlyTheShownPair(unittest.TestCase):
    def test_tripwire_the_hidden_point_and_the_reference_are_never_read(self):
        log = []
        pool = fake_pool(hidden=Tripwire(POINTS[0], log), rec=Tripwire({"text": "square it", "code": "def sq"}, log))
        h = Harness(pool=pool)
        self.addCleanup(h.close)
        write_candidates(h.cands, 7, [SQUARE, HARD, BADSPEC, MEMO, PLUS6, GARBAGE], logprobs=[-1, -2, -3, -4, -5, -6])
        self.assertEqual(h.run(samples=6), 0)
        self.assertEqual(log, [])
        self.assertEqual(body_of(h.record(7)).replace("mbpp_7__sq", "sq"), SQUARE)

    def test_the_tripwire_fires_outside_the_prompt_builder(self):
        log = []
        point = Tripwire(POINTS[0], log)
        with self.assertRaises(Trip):
            _ = point["args"]
        self.assertEqual(log, ["getitem args"])
        # and stays quiet inside discriminative
        self.assertEqual(len(loop_locallm.discriminative([point, POINTS[1], POINTS[2]], 2)), 2)
        self.assertEqual(log, ["getitem args"])
        # spec_check's own draw shaping reads points[0]; the selector must not call it
        with self.assertRaises(Trip):
            loop_locallm.signature({"fn": "sq", "points": [point]})

    def test_the_pool_is_referenced_only_inside_shown_pairs(self):
        tree = ast.parse(Path(sc.__file__).read_text(encoding="utf-8"))
        where, spec_check_calls, modules = [], set(), set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules.update(alias.name for alias in node.names)
            if isinstance(node, ast.FunctionDef):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Attribute) and sub.attr == "pool" and isinstance(sub.value, ast.Name) \
                            and sub.value.id == "se":
                        where.append(node.name)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "spec_check":
                spec_check_calls.add(node.attr)
        self.assertEqual(sorted(set(where)), ["shown_pairs"])
        # draw and check_points (handed the shown pair only); never check_task, exploit or the reference
        self.assertEqual(spec_check_calls, {"draw", "check_points"})
        self.assertNotIn("loop_locallm", modules, "problem_head and signature read points[0]")


class Output(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.addCleanup(self.h.close)

    def test_the_grader_reads_the_written_answer(self):
        write_candidates(self.h.cands, 7, [SQUARE, PLUS6])
        self.h.run(samples=2)
        args = mock.Mock(model="sel", pool="v3")
        with mock.patch.object(se, "pool", lambda version="v1": self.h.pool), \
                mock.patch.object(se, "OUT_ROOT", self.h.out_root):
            se.cmd_extract(args)
            se.cmd_tests(args)
        ext = json.loads((self.h.out_root / "sel" / "extract.json").read_text(encoding="utf-8"))
        tests = json.loads((self.h.out_root / "sel" / "tests.json").read_text(encoding="utf-8"))
        self.assertEqual(ext["7"]["stage"], "task")
        self.assertEqual(ext["7"]["name"], "mbpp_7__sq")
        self.assertEqual(tests["7"]["overall"], "pass")

    def test_the_selected_tag_holds_only_raw_and_selection(self):
        write_candidates(self.h.cands, 7, [SQUARE, PLUS6])
        self.h.run(samples=2)
        entries = sorted(p.name for p in (self.h.out_root / "sel").iterdir())
        self.assertEqual(entries, ["raw", "selection.json"], "grade_lab.sh skips extraction when tasks/*.json exists")
        self.assertEqual(self.h.raw_files(), ["7.json"])

    def test_the_locallm_reply_cut_equals_cmd_generates(self):
        text = "Example: sq(1) == 1\n" + SQUARE + "\nProblem: another one\nSignature: f(int) -> int\nt 1\ntask f() ...\n"
        body = re.split(r"\n\s*\n(?=Problem: |Signature: |t \d)", text, maxsplit=1)[0]
        body = loop_filter.strip_head(body)
        self.assertEqual(sc.reply_of(text, "locallm"), "```t\n" + body.strip() + "\n```")
        self.assertEqual(se.find_block(sc.reply_of(text, "locallm")).strip() + "\n", SQUARE)

    def test_chat_replies_are_used_verbatim(self):
        reply = "Here you go:\n```t\n" + SQUARE + "```\nDone."
        self.assertEqual(sc.reply_of(reply, "chat"), reply)
        write_candidates(self.h.cands, 7, [SQUARE, SQUARE], fmt="chat")
        self.h.run(samples=2, extra=["--reply-format", "chat"])
        self.assertEqual(self.h.record(7)["reply"], "```t\n" + SQUARE.rstrip("\n") + "\n```")

    def test_two_runs_are_byte_identical(self):
        write_candidates(self.h.cands, 7, [SQUARE, HARD, MEMO, BADSPEC], logprobs=[-1, -2, -3, -4])
        self.h.run(samples=4, tag="one")
        self.h.run(samples=4, tag="two")
        a = (self.h.out_root / "one" / "raw" / "7.json").read_bytes()
        b = (self.h.out_root / "two" / "raw" / "7.json").read_bytes()
        self.assertEqual(a, b)
        sa = json.loads((self.h.out_root / "one" / "selection.json").read_text(encoding="utf-8"))
        sb = json.loads((self.h.out_root / "two" / "selection.json").read_text(encoding="utf-8"))
        sa.pop("tag"), sb.pop("tag")
        self.assertEqual(sa, sb)

    def test_the_record_carries_what_grading_and_scoring_read(self):
        write_candidates(self.h.cands, 7, [SQUARE, SQUARE], prompt_version="locallm-head", digest="92M params")
        self.h.run(samples=2)
        rec = self.h.record(7)
        for key in ("task_id", "fn", "model", "digest", "pool_version", "prompt_version", "options", "messages",
                    "reply", "done_reason", "selection"):
            self.assertIn(key, rec)
        self.assertEqual((rec["task_id"], rec["fn"], rec["pool_version"], rec["model"]), (7, "sq", "v3", "locallm:m"))
        self.assertEqual(rec["options"]["candidate_options"], {"temperature": 0.5, "top_k": 20})
        self.assertEqual(rec["options"]["samples"], 2)
        self.assertEqual(rec["selection"]["shown_indices"], [1, 2])


if __name__ == "__main__":
    unittest.main()
