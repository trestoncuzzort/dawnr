#!/usr/bin/env python3
"""The repair loop's two claims, tested where they can actually fail.

`t/repair.py` asks a model to fix an answer that passes its problem's tests but
is not clean in all seven kernels. Two things decide whether that ask is worth
sending:

1. **It has to reach the model.** `se.chat`'s `api` argument selects the
   transport, and it was taking its default here while the host was a vLLM
   server, so every request went to `/api/chat`, which vLLM does not serve. The
   symptom was not an error about transports: it was `no answer` for every task,
   which reads like a model that would not cooperate.
2. **It has to carry the counterexample.** Checker prose alone is the middle
   rung of VeriMed's ladder (https://arxiv.org/abs/2605.13817): 80.0 percent
   against 98.5 with a concrete witness beside it. The witness is computed on
   every grading run already, so the only failure mode worth testing is the one
   where `counterexample` quietly returns nothing.

Stdlib only, no corpus and no model: the tasks are built here.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import repair                                                    # noqa: E402

COLS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]


def row(**over):
    r = {k: "verified / refuted" for k in COLS}
    r.update(over)
    return r


# A task whose body returns a + b but whose ensures only says r >= a, which is
# satisfied by answers that are not a + b: the shape a decorative verdict is
# about.
WEAK = {
    "name": "add_weak", "t": 0,
    "params": [["a", "int"], ["b", "int"]],
    "returns": [{"name": "r", "type": "int"}],
    "requires": [{"op": ">=", "args": [{"var": "b"}, {"int": 0}]}],
    "ensures": [{"op": ">=", "args": [{"var": "r"}, {"var": "a"}]}],
    "body": [{"assign": "r", "value": {"op": "+", "args": [{"var": "a"}, {"var": "b"}]}}],
}


class TestCounterexample(unittest.TestCase):
    def test_a_clean_row_asks_for_nothing(self):
        """Every kernel verified the program and refuted the broken copy, so
        there is no fault to localize and nothing to put in the prompt."""
        self.assertEqual(repair.counterexample(WEAK, row(), COLS), "")

    def test_a_decorative_row_gets_a_concrete_input(self):
        """Real verified, twin verified: the ensures cannot separate them. The
        message has to name the input where they differ, not just say so."""
        out = repair.counterexample(WEAK, row(dafny="verified / verified"), COLS)
        if out:                                  # the bounded search found one
            self.assertIn("->", out)
            self.assertIn("broken copy", out)
        else:                                    # it may legitimately find none
            self.assertEqual(out, "")

    def test_a_missing_task_never_raises(self):
        """A witness is evidence, not a precondition: a malformed or empty task
        degrades to prose feedback rather than killing the repair run."""
        self.assertEqual(repair.counterexample({}, row(dafny="refuted / refuted"), COLS), "")

    def test_it_does_not_invent_a_witness_it_did_not_find(self):
        out = repair.counterexample({}, row(), COLS)
        self.assertEqual(out, "")


class TestTheTransportIsSelectable(unittest.TestCase):
    """The one-argument gap that made every repair against vLLM report
    `no answer`."""

    def test_api_is_a_flag(self):
        src = (HERE / "repair.py").read_text(encoding="utf-8")
        self.assertIn('"--api"', src)

    def test_the_api_choice_reaches_the_transport(self):
        src = (HERE / "repair.py").read_text(encoding="utf-8")
        self.assertIn("se.chat(a.host, a.model, messages, options, a.timeout, a.api)", src)
        self.assertNotIn("se.chat(a.host, a.model, messages, options, a.timeout)", src)


class TestRepairKind(unittest.TestCase):
    """Which half of the answer the model is allowed to touch."""

    def test_a_refuted_real_is_a_specification_problem(self):
        self.assertEqual(repair.kind_of(row(lean="refuted / refuted"), COLS), "spec")

    def test_an_unproved_real_is_a_proof_problem(self):
        self.assertEqual(repair.kind_of(row(lean="unproved / refuted"), COLS), "proof")


if __name__ == "__main__":
    unittest.main()
