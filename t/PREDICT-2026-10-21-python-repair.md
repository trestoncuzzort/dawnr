# A repair attempt at the Python stage, inside the same budget: registered 2026-10-21 09:42Z, before the run

The first drop of the funnel: 44 of 95 development problems have no Python that passes the tests after three
attempts (51 do), and 32 after ten (t/PREDICT-2026-10-21-spec-ceiling.md). A failing attempt gets no feedback;
the sandbox already knows which assert failed and how. Self-Debugging (arXiv:2304.05128) feeds execution
results back for a fix and Reflexion (arXiv:2303.11366) feeds test feedback; both report their largest gains on
exactly this kind of unit-test signal. The student was trained with 909 judge-python and 670 debug rows, so the
skill may be there to use.

## The change

`t/spec_first.py --python-repair`: the last Python attempt (the third at the frozen budget) repairs the best
failed reply instead of sampling afresh. The conversation is the Python question, the student's failed reply,
and one user turn with the sandbox's finding: the first two failing asserts with the error or the assertion
failure, or that the code does not load, times out, or has no fenced block. The best failed reply is the one
that passed the most tests. A repair ask replaces a sampled ask one for one, so the budget is unchanged.
Default off; without the flag the route is byte for byte what it was (tested).

## Arms (v5, desktop, cache seeded from the control; graded in the kernel container)

- Y17: the frozen route with `--python-repair`, tag `v5-20261021-pyr17`; paired against the control re-graded
  under the current tree (`v5-20261021-dev-desktop-r2`: 51 / 18 kept / 13 / 6 / 3).

## Predictions, with the numbers that falsify them

- **P1 (the stage moves).** Python passing the tests at least 55 (51). 54 or fewer falsifies it.
- **P2 (it reaches the end).** Kept specifications at least 19 (18), answered at least 14 (13), clean at least 7
  (6), all-seven at least 3, no control problem lost. Clean 6 or fewer, or a lost problem, falsifies it.
- **P3 (the mechanism).** Of the repair asks, at least a third pass the tests. Under a third falsifies it.
- **P4 (what decides).** P1 and P2 hold: `--python-repair` enters the route of record at its budget. P1 holds
  and P2 fails: the new problems are ones the specification stage cannot take; the budget belongs downstream.
  P1 fails: the student does not use test feedback either, and the Python stage waits for training.

Sources: Self-Debugging arXiv:2304.05128, Reflexion arXiv:2303.11366; t/py_sandbox.py (the finding).

## Result (2026-10-21 15:06Z; generated 12:55Z, graded in the desktop container, paired against `v5-20261021-dev-desktop-r2`)

Python passing the tests 48 (control 51): the third attempt as a repair passed 5 of 52 asks where the control's
third attempt as a fresh sample passed 8. Answered 13 (13), **clean 5 (6), lost 543** (its Python never came), all-seven
3 (3). Receipt `release/evidence/v5-python-repair17-2026-10-21.json`. **P1, P2 and P3 falsified** (48 under 55; clean
5 with a loss; 5 of 52 under a third). By P4 the Python stage waits for training; the test feedback is not used.
