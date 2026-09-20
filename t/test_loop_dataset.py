"""New training rows require current evidence and cannot import held-out pairs."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

import loop_dataset as dataset
import spec_check
import surface


def sample(tag="checked", tid=1):
    task = surface.parse(f"t 0\ntask mbpp_{tid}__f(a: int) returns (r: int)\n"
                         "  ensures r == a + 1\n{ r := a + 1; }\n")
    return {"tag": tag, "k": 0, "task_id": tid, "stage": "task", "wellformed": True,
            "name": task["name"], "task": task, "text": dataset.fence(surface.print_task(task)),
            "prompt": [{"role": "user", "content": f"Increment problem {tid}"}],
            "tests_pass": True, "tests_overall": "pass", "kernel_count": 7,
            "kernel_columns": list(spec_check.KERNELS),
            "kernel_row": {k: "verified / refuted" for k in spec_check.KERNELS},
            "refuted_kernels": list(spec_check.KERNELS)}


def evidence(s):
    return {f"{s['tag']}/{s['name']}": {
        "status": "agrees", "draws": 20, "task_id": s["task_id"], "pool": "v5",
        "task_sha256": spec_check.task_sha256(s["task"])}}


def pair(s):
    return {"source": "samples", "tag": s["tag"], "sample_index": s["k"],
            "task_id": s["task_id"], "task": s["name"], "prompt": s["prompt"],
            "chosen": s["text"], "rejected": s["text"].replace("a + 1", "a + 2"),
            "kind": "twin:fixture", "operator": "fixture", "witness": {"a": 0},
            "kernel_count": 7, "refuted_kernels": list(spec_check.KERNELS),
            "neg_tag": None, "neg_sample_index": None}


class SampleGateTests(unittest.TestCase):
    def test_positive_requires_explicit_current_problem_and_program_evidence(self):
        s = sample()
        key = f"{s['tag']}/{s['name']}"
        good = evidence(s)
        self.assertEqual(dataset.positives_of([s], results=good, pool_name="v5"), [s])
        self.assertEqual(dataset.positive_rejection(s, {}), "spec-unchecked")
        cases = [("status", "disagrees", "spec-not-agrees"),
                 ("draws", 0, "spec-no-valid-draws"),
                 ("draws", -1, "spec-no-valid-draws"),
                 ("draws", True, "spec-no-valid-draws"),
                 ("draws", "20", "spec-no-valid-draws"),
                 ("task_id", 2, "spec-problem-mismatch"),
                 ("task_id", True, "spec-problem-mismatch"),
                 ("pool", "v1", "spec-pool-mismatch"),
                 ("task_sha256", "old", "spec-hash-missing-or-stale"),
                 ("points_failed", 1, "spec-contradicts-example"),
                 ("points_failed", 3, "spec-contradicts-example"),
                 ("over_constrained", True, "spec-refuses-every-example")]
        for field, value, expected in cases:
            with self.subTest(field=field, value=value):
                modified = copy.deepcopy(good)
                modified[key][field] = value
                self.assertEqual(dataset.positive_rejection(s, modified, "v5"), expected)
        del good[key]["task_sha256"]
        self.assertEqual(dataset.positive_rejection(s, good), "spec-hash-missing-or-stale")
        changed = copy.deepcopy(s)
        changed["task"] = surface.parse(surface.print_task(s["task"]).replace("a + 1", "a + 2"))
        self.assertEqual(dataset.positive_rejection(changed, evidence(s)), "spec-hash-missing-or-stale")

    def test_agreeing_on_draws_does_not_excuse_contradicting_a_stated_example(self):
        """A specification can agree on every random draw and still be false at an
        input the problem itself supplies. The draws are sampled; the examples are
        the ones a problem author chose. Before 2026-09-20 spec_check computed this
        and only the scorecard read it, so such an answer entered the training set.
        """
        s = sample()
        key = f"{s['tag']}/{s['name']}"
        ev = evidence(s)
        ev[key].update(points_held=2, points_failed=1,
                       contradicts_example={"args": [7], "expected": 8})
        self.assertEqual(dataset.positive_rejection(s, ev, "v5"), "spec-contradicts-example")
        self.assertEqual(dataset.positives_of([s], results=ev, pool_name="v5"), [])
        # Held at every example and failing none is the passing shape.
        ev[key].update(points_held=3, points_failed=0)
        ev[key].pop("contradicts_example")
        self.assertIsNone(dataset.positive_rejection(s, ev, "v5"))
        # A specification whose precondition refuses every example the problem
        # gave it narrows the problem instead of describing it.
        ev[key].update(points_held=0, points_failed=0, points_excluded=3,
                       over_constrained=True)
        self.assertEqual(dataset.positive_rejection(s, ev, "v5"), "spec-refuses-every-example")

    def test_missing_points_columns_are_not_treated_as_a_failure(self):
        """470 of 512 existing rows predate check_points. They must still pass the
        gates that do apply rather than being rejected for a column that did not
        exist when they were written -- and, equally, absence is not evidence they
        hold at their examples. Only a present, positive count rejects.
        """
        s = sample()
        key = f"{s['tag']}/{s['name']}"
        ev = evidence(s)
        self.assertNotIn("points_failed", ev[key])
        self.assertIsNone(dataset.positive_rejection(s, ev, "v5"))
        for value in (None, "1", True, 0):
            with self.subTest(points_failed=value):
                modified = copy.deepcopy(ev)
                modified[key]["points_failed"] = value
                self.assertIsNone(dataset.positive_rejection(modified and s, modified, "v5"))

    def test_examples_supply_a_missing_verdict_but_never_overturn_a_negative_one(self):
        """t has no string type, so check_task cannot draw an argument the reference
        solution of a string problem will accept and the status reads "no valid
        draws" -- no verdict, not a bad one. check_points answers such a problem
        from the input/output pairs it states. But the examples are WEAKER than the
        draws, measured: of 12 specifications known to disagree with their
        reference, 6 hold at every stated example. So a disagreement is absolute.
        """
        s = sample()
        key = f"{s['tag']}/{s['name']}"

        def ev_with(**kw):
            e = evidence(s)
            e[key].update(**kw)
            return e

        # No verdict + holds at every stated example -> admitted.
        for status in ("no valid draws", "reference result has no t value"):
            with self.subTest(status=status):
                e = ev_with(status=status, draws=0, points_held=3, points_failed=0)
                self.assertIsNone(dataset.positive_rejection(s, e, "v5"))
                self.assertEqual(dataset.positives_of([s], results=e, pool_name="v5"), [s])

        # A disagreement stays a rejection however well the examples hold. This is
        # the case that would have readmitted six known-wrong specifications.
        e = ev_with(status="disagrees", draws=0, points_held=3, points_failed=0)
        self.assertEqual(dataset.positive_rejection(s, e, "v5"), "spec-not-agrees")

        # Statuses that are not a missing verdict get no fallback.
        for status in ("arity differs from the problem", "interpreter refused"):
            with self.subTest(status=status):
                e = ev_with(status=status, draws=0, points_held=3, points_failed=0)
                self.assertEqual(dataset.positive_rejection(s, e, "v5"), "spec-not-agrees")

        # No verdict and no examples either is still no evidence.
        for held, failed in ((0, 0), (0, 3), (3, 1)):
            with self.subTest(held=held, failed=failed):
                e = ev_with(status="no valid draws", draws=0,
                            points_held=held, points_failed=failed)
                self.assertEqual(dataset.positive_rejection(s, e, "v5"), "spec-not-agrees")

        # Over-constrained: it refused every example it was given.
        e = ev_with(status="no valid draws", draws=0, points_held=0,
                    points_failed=0, points_excluded=3, over_constrained=True)
        self.assertEqual(dataset.positive_rejection(s, e, "v5"), "spec-not-agrees")

        # The examples path does not excuse the other gates.
        e = ev_with(status="no valid draws", draws=0, points_held=3,
                    points_failed=0, pool="v1")
        self.assertEqual(dataset.positive_rejection(s, e, "v5"), "spec-pool-mismatch")
        e = ev_with(status="no valid draws", draws=0, points_held=3,
                    points_failed=0, task_sha256="old")
        self.assertEqual(dataset.positive_rejection(s, e, "v5"), "spec-hash-missing-or-stale")

        # An agreeing result still needs a real draw; the examples do not stand in.
        e = ev_with(draws=0, points_held=3, points_failed=0)
        self.assertEqual(dataset.positive_rejection(s, e, "v5"), "spec-no-valid-draws")

    def test_seven_means_exact_named_clean_kernels(self):
        s = sample()
        for columns in (["dafny"] * 7, list(spec_check.KERNELS[:-1]) + ["fake"],
                        list(spec_check.KERNELS) + ["dafny"], list(spec_check.KERNELS[:-1])):
            with self.subTest(columns=columns):
                changed = copy.deepcopy(s)
                changed["kernel_columns"] = columns
                self.assertEqual(dataset.positive_rejection(changed, evidence(s)),
                                 "kernel-names-not-exact-seven")
        for value in ("verified / refuted FLAKED", "verified / refuted (FLAKED)",
                      "verified / unknown", "verified / verified"):
            with self.subTest(value=value):
                changed = copy.deepcopy(s)
                changed["kernel_row"]["spark"] = value
                self.assertEqual(dataset.positive_rejection(changed, evidence(s)), "kernels-not-clean-seven")
        with self.assertRaisesRegex(ValueError, "seven named"):
            dataset.positives_of([s], min_kernels=4, results=evidence(s))

    def test_checked_duplicate_survives_unchecked_first_copy(self):
        unchecked, checked = sample("unchecked"), sample("checked")
        checked["k"] = 1
        self.assertEqual(unchecked["text"], checked["text"])
        self.assertEqual(dataset.positives_of([unchecked, checked], results=evidence(checked)), [checked])

    def test_include_cannot_import_changed_or_unmeasured_rows(self):
        s = sample()
        p = pair(s)
        heldout = sample(tid=2)
        rows = [p]
        expected = []
        changes = [("task_id", 2, "include-not-train-pool-id"),
                   ("task_id", True, "include-not-train-pool-id"),
                   ("task_id", 3, "include-not-train-pool-id"),
                   ("tag", "unselected", "include-tag-not-selected"),
                   ("chosen", p["chosen"] + "\n", "include-program-mismatch"),
                   ("task", "other", "include-program-mismatch"),
                   ("prompt", None, "include-prompt-missing"),
                   ("prompt", [{"role": "user", "content": "other"}], "include-prompt-mismatch"),
                   ("rejected", "arbitrary unchecked text", "include-negative-not-current")]
        for field, value, reason in changes:
            modified = copy.deepcopy(p)
            modified[field] = value
            rows.append(modified)
            expected.append(reason)
        forged_metadata = dict(p, kernel_count=100, witness={"forged": True})
        rows.append(forged_metadata)
        accepted, rejected = dataset.validate_included_pairs(
            rows, {(s["tag"], 1): s, (heldout["tag"], 2): heldout}, [p], ["checked"],
            {1, 3}, {2}, {1: {}, 2: {}}, evidence(s), "v5")
        self.assertEqual(accepted, [p, p])
        self.assertEqual(rejected, dataset.Counter(expected))
        for changed_evidence, reason in (({}, "include-spec-unchecked"),
                                         ({f"checked/{s['name']}": {**next(iter(evidence(s).values())),
                                                                  "task_sha256": "stale"}},
                                          "include-spec-hash-missing-or-stale")):
            kept, dropped = dataset.validate_included_pairs(
                [p], {("checked", 1): s}, [p], ["checked"], {1}, set(), {1: {}}, changed_evidence, "v5")
            self.assertEqual(kept, [])
            self.assertEqual(dropped, {reason: 1})

    def test_default_cli_requires_seven(self):
        with patch("sys.argv", ["loop_dataset.py", "--from-samples", "checked"]), \
                patch.object(dataset, "run_from_samples", return_value=0) as run:
            self.assertEqual(dataset.main(), 0)
            self.assertEqual(run.call_args.args[0].min_kernels, 7)

    def test_disagreement_negative_requires_current_explicit_evidence(self):
        positive, negative = sample(), sample("negative")
        negative["task"] = surface.parse(surface.print_task(negative["task"]).replace("a + 1", "a + 2"))
        negative["text"] = dataset.fence(surface.print_task(negative["task"]))
        checked = evidence(negative)
        result = next(iter(checked.values()))
        result.update(status="disagrees", args=[0], reference_said=1, ensures=0)
        with patch.object(dataset, "build_negatives", return_value=[]):
            self.assertEqual(dataset.negatives_for_positive(positive, [negative], {}, "v5"), [])
            for field, bad in (("task_sha256", "stale"), ("task_id", 2),
                               ("pool", "v1"), ("status", "agrees")):
                with self.subTest(field=field):
                    modified = copy.deepcopy(checked)
                    next(iter(modified.values()))[field] = bad
                    self.assertEqual(dataset.negatives_for_positive(positive, [negative], modified, "v5"), [])
            negatives = dataset.negatives_for_positive(positive, [negative], checked, "v5")
            self.assertEqual(len(negatives), 1)
            self.assertEqual(negatives[0]["kind"], "spec-disagrees")
            self.assertEqual(negatives[0]["rejected"], negative["text"])

    def test_real_sample_loading_and_output_exclude_eval_in_both_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            here = Path(tmp)
            tag = here / "tag"
            (tag / "tasks").mkdir(parents=True)
            (tag / "raw").mkdir()
            train, heldout = sample(tid=1), sample(tid=2)
            for s in (train, heldout):
                (tag / "tasks" / f"{s['name']}.json").write_text(json.dumps(s["task"]))
                (tag / "raw" / f"{s['task_id']}.json").write_text(json.dumps({"messages": s["prompt"]}))
            (tag / "extract.json").write_text(json.dumps({str(s["task_id"]): {
                "stage": "task", "name": s["name"]} for s in (train, heldout)}))
            (tag / "tests.json").write_text(json.dumps({"1": {"overall": "pass"}, "2": {"overall": "pass"}}))
            cols = spec_check.KERNELS
            (tag / "kernels.md").write_text(
                "| task | " + " | ".join(cols) + " |\n|---|" + "---|" * 7 + "\n" +
                "".join("| " + s["name"] + " | " + " | ".join(["verified / refuted"] * 7) + " |\n"
                        for s in (train, heldout)))
            out = here / "out/loop"
            out.mkdir(parents=True)
            (here / "out/spec-disagree.json").write_text(json.dumps({
                "results": {**evidence(train), **evidence(heldout)}}))
            split_path = here / "split.json"
            split_path.write_text(json.dumps({"pool": "v5", "train_ids": [1], "eval_ids": [2]}))
            include_path = here / "include.jsonl"
            include_path.write_text("\n".join(json.dumps(pair(s)) for s in (train, heldout)))
            args = SimpleNamespace(from_samples=["checked"], split=str(split_path), min_kernels=7,
                                   include=str(include_path), out_suffix="fixture")

            def negative(s, _, *_evidence):
                p = pair(s)
                return [{key: p[key] for key in ("kind", "operator", "witness", "rejected", "neg_tag", "neg_sample_index")}]

            with patch.object(dataset, "HERE", here), patch.object(dataset, "OUT", out), \
                    patch.object(dataset.spec_experiment, "outdir", return_value=tag), \
                    patch.object(dataset.spec_experiment, "pool", return_value={1: {}, 2: {}}), \
                    patch.object(dataset, "negatives_for_positive", side_effect=negative), redirect_stdout(io.StringIO()):
                self.assertEqual(dataset.run_from_samples(args), 0)
                for name in ("pairs-fixture.jsonl", "sft-fixture.jsonl"):
                    saved = [json.loads(line) for line in (out / name).read_text().splitlines()]
                    self.assertEqual([row["task_id"] for row in saved], [1])
                    self.assertEqual(saved[0]["prompt"], train["prompt"])
                report = (out / "DATASET-fixture.md").read_text()
                self.assertIn("include-not-train-pool-id | 1", report)
                self.assertIn("| eval | 1 | 1 | 1 | 1 |", report)

                # The established missing-prompt refusal still prevents output.
                (tag / "raw/1.json").unlink()
                args.include = None
                args.out_suffix = "missing-prompt"
                with self.assertRaisesRegex(SystemExit, "no recorded prompt"):
                    dataset.run_from_samples(args)
                self.assertFalse((out / "sft-missing-prompt.jsonl").exists())

                split_path.write_text(json.dumps({"pool": "v5", "train_ids": [1, 2], "eval_ids": [2]}))
                with self.assertRaisesRegex(ValueError, "overlap"):
                    dataset.run_from_samples(args)


if __name__ == "__main__":
    unittest.main()
