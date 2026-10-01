"""t/score_levels.py (2026-10-01): what counts at each trust level. One sound verifier is the
published filter (SAFE, arXiv:2410.15756); the level is reported, never rounded up. No kernel."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import score_levels  # noqa: E402
import spec_check  # noqa: E402

ALL = {k: "verified / refuted" for k in spec_check.KERNELS}


def row(**cells):
    return {**ALL, **cells}


class Level(unittest.TestCase):
    def test_all_seven_with_the_specification_checked_is_seven(self):
        self.assertEqual(score_levels.answer_level("pass", ALL, "agrees"), (7, 7))

    def test_a_kernel_that_could_not_decide_lowers_the_level(self):
        r = row(spark="timeout / refuted", framac="abstain / abstain")
        self.assertEqual(score_levels.answer_level("pass", r, "agrees"), (5, 5))

    def test_a_refuting_kernel_makes_it_nothing_at_any_level(self):
        self.assertEqual(score_levels.answer_level("pass", row(lean="refuted / refuted"), "agrees"), (0, 0))

    def test_tests_must_pass(self):
        self.assertEqual(score_levels.answer_level("fail", ALL, "agrees"), (0, 0))
        self.assertEqual(score_levels.answer_level(None, ALL, "agrees"), (0, 0))

    def test_without_an_agreeing_specification_it_counts_only_in_the_unchecked_column(self):
        for status in ("disagrees", None):
            self.assertEqual(score_levels.answer_level("pass", ALL, status), (0, 7))

    def test_a_twin_that_was_not_refuted_is_not_a_proof(self):
        r = {k: "verified / verified" for k in spec_check.KERNELS}
        self.assertEqual(score_levels.answer_level("pass", r, "agrees"), (0, 0))

    def test_a_table_without_exactly_the_seven_kernels_does_not_count(self):
        r = dict(ALL)
        del r["rocq"]
        self.assertEqual(score_levels.answer_level("pass", r, "agrees"), (0, 0))


class WeakSpecification(unittest.TestCase):
    """An agreeing specification that rejects few wrong outputs is not counted when asked
    (SAFE's 60% rule, arXiv:2410.15756 3.2); without the option nothing changes."""

    def setUp(self):
        import json
        import tempfile
        from unittest import mock

        import spec_experiment as se
        import surface
        real = surface.parse_file(str(HERE / "tasks" / "abs.t"))    # a task the canonical printer accepts
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        patch = mock.patch.object(se, "OUT_ROOT", root)
        patch.start()
        self.addCleanup(patch.stop)
        d = root / se.model_tag("set")
        (d / "tasks").mkdir(parents=True)
        cols = sorted(spec_check.KERNELS)
        lines = ["| task | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        self.verdicts = {}
        # problem -> the share of mutated outputs its specification rejects (None: no mutant was judged)
        for tid, share in {1: 1.0, 2: 0.6, 3: 0.59, 4: 0.0, 5: None}.items():
            name = f"p{tid}"
            task = dict(real, name=name)
            (d / "tasks" / f"{name}.json").write_text(json.dumps(task), encoding="utf-8")
            lines.append(f"| {name} | " + " | ".join("verified / refuted" for _ in cols) + " |")
            v = {"status": "agrees", "draws": 100, "task_sha256": spec_check.task_sha256(task)}
            if share is not None:
                v["completeness"] = share
            self.verdicts[f"set/{name}"] = v
        (d / "kernels.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (d / "extract.json").write_text(json.dumps(
            {str(i): {"name": f"p{i}", "stage": "task"} for i in range(1, 6)}), encoding="utf-8")
        (d / "tests.json").write_text(json.dumps(
            {str(i): {"name": f"p{i}", "overall": "pass"} for i in range(1, 6)}), encoding="utf-8")

    def levels(self, floor):
        lv = score_levels.tag_levels("set", {1, 2, 3, 4, 5}, self.verdicts, floor)
        return {tid: v[0] for tid, v in lv.items()}

    def test_without_the_option_every_agreeing_answer_counts(self):
        self.assertEqual(self.levels(None), {1: 7, 2: 7, 3: 7, 4: 7, 5: 7})

    def test_below_the_floor_is_not_counted_and_the_floor_itself_is(self):
        self.assertEqual(self.levels(0.6), {1: 7, 2: 7, 3: 0, 4: 0, 5: 7})

    def test_the_unchecked_column_does_not_move(self):
        lv = score_levels.tag_levels("set", {3, 4}, self.verdicts, 0.6)
        self.assertEqual({tid: v[1] for tid, v in lv.items()}, {3: 7, 4: 7})

    def test_the_table_and_the_pooled_row_use_it(self):
        rows, pooled = score_levels.table(["set"], {1, 2, 3, 4, 5}, self.verdicts, 0.6)
        self.assertEqual((rows[0][">=7"], pooled[">=7"]), (3, 3))
        self.assertEqual(pooled[">=7 before the specification check"], 5)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
