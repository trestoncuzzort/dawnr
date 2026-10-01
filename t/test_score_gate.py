"""t/score_gate.py: what the gate shows without a reference and how much of it is right (the stage
is Clover's consistency check, arXiv:2310.17807; "right" keeps SAFE's 60% floor, arXiv:2410.15756)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import score_gate  # noqa: E402
import spec_check  # noqa: E402
import spec_experiment as se  # noqa: E402
import surface  # noqa: E402


class Shown(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        p = mock.patch.object(se, "OUT_ROOT", root)
        p.start()
        self.addCleanup(p.stop)
        real = surface.parse_file(str(HERE / "tasks" / "abs.t"))
        d = root / "set"
        (d / "tasks").mkdir(parents=True)
        cols = sorted(spec_check.KERNELS)
        lines = ["| task | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        self.verdicts, self.gate, tests = {}, {}, {}
        #      id: (tests, kernels proved, gate passes, reference status, completeness)
        plan = {1: ("pass", 7, True, "agrees", 1.0),        # shown and right
                2: ("pass", 7, True, "disagrees", None),    # shown, wrong: the failure
                3: ("pass", 7, False, "agrees", 1.0),       # right, refused by the gate
                4: ("pass", 3, True, "agrees", 0.2),        # shown, weak: not right
                5: ("fail", 7, True, "agrees", 1.0),        # fails its tests: nothing
                6: ("pass", 3, True, "agrees", 0.9)}        # shown and right at three kernels only
        for tid, (overall, proved, passes, status, share) in plan.items():
            name = f"p{tid}"
            task = dict(real, name=name)
            (d / "tasks" / f"{name}.json").write_text(json.dumps(task), encoding="utf-8")
            row = ["verified / refuted"] * proved + ["timeout / refuted"] * (7 - proved)
            lines.append(f"| {name} | " + " | ".join(row) + " |")
            tests[str(tid)] = {"name": name, "overall": overall}
            sha = spec_check.task_sha256(task)
            v = {"status": status, "draws": 100, "task_sha256": sha}
            if share is not None:
                v["completeness"] = share
            self.verdicts[f"set/{name}"] = v
            self.gate[f"set/{name}"] = {"passes": passes, "task_sha256": sha}
        (d / "kernels.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (d / "tests.json").write_text(json.dumps(tests), encoding="utf-8")
        self.ids = set(plan)

    def test_shown_needs_tests_a_proof_and_the_gate_and_right_needs_the_reference_too(self):
        rows, pooled = score_gate.table(["set"], self.ids, self.verdicts, self.gate)
        self.assertEqual((pooled["proved>=1"], pooled["shown>=1"], pooled["shown and right>=1"]), (5, 4, 2))
        self.assertEqual(pooled["shown, none right>=1"], [2, 4])
        self.assertEqual(pooled["right by the reference>=1"], 3)    # 1, 3 and 6: the gate lost 3
        self.assertEqual((pooled["proved>=7"], pooled["shown>=7"], pooled["shown and right>=7"]), (3, 2, 1))
        self.assertEqual(rows[0]["shown>=1"], 4)

    def test_a_gate_verdict_for_other_task_contents_shows_nothing(self):
        self.gate["set/p1"]["task_sha256"] = "0" * 64
        _rows, pooled = score_gate.table(["set"], self.ids, self.verdicts, self.gate)
        self.assertEqual((pooled["shown>=1"], pooled["shown and right>=1"]), (3, 1))

    def test_the_rendered_table_states_the_precision_and_names_the_failures(self):
        text = score_gate.render(*score_gate.table(["set"], self.ids, self.verdicts, self.gate))
        self.assertIn("4 problems shown, 2 right (50%)", text)
        self.assertIn("shown with no right answer: [2, 4]", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
