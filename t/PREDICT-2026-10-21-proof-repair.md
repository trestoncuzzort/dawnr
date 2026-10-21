# A repair attempt at the proof stage, inside the same budget: registered 2026-10-21 09:18Z, before the run

From the 39-call oracle arm (t/PREDICT-2026-10-21-oracle-route.md): 28 problems had a kept specification and 12
of them no accepted answer after three proof attempts. The cheap gates' refusals over those 75 asks: not well
formed 49, fails a test 21, does not parse 5. The well-formedness errors are the kind a compiler reports and a
model fixes when told (unbound loop variables used outside their scope, `at` and `==` on mismatched types, calls
to helpers the task never declared, string-library signatures), unlike the specification misreadings of
t/PREDICT-2026-10-21-repair-turn.md. The witness exists already: `accept()` computes it when it refuses.

## The change

`t/spec_first.py --proof-repair`: the last proof attempt (the second sampled one, attempt 2) repairs the best
refused reply of each kept specification instead of sampling afresh. The conversation is the proof question, the
student's refused reply, and one user turn with the gate's finding: the parser's message, the changed
specification, the first three well-formedness errors, or the first two failing tests with what the task
returned. The budget is unchanged: a repair ask replaces a sampled ask one for one. The best refusal is the one
closest to acceptance (fails a test over not well formed over specification changed over does not parse over no
block). Default off; without the flag the route is byte for byte what it was (tested).

## Arms (v5, desktop, caches seeded from the control and the 39-call oracle run; graded in the kernel container)

- R17: the frozen route with `--proof-repair`, tag `v5-20261021-pr17`; paired against the control re-graded
  under the current tree (`v5-20261021-dev-desktop-r2`: 51 / 13 / 6 / 3).
- R39: the 39-call oracle route with `--proof-repair`, tag `v5-20261021-pr39`; paired against
  `v5-20261021-oracle39` (63 / 28 / 16 / 7 / 3).

## Predictions, with the numbers that falsify them

- **P1 (the repair converts).** R39: answered at least 20 (16), clean at least 8 (7), all-seven at least 3, no
  problem lost. Answered 16 or fewer, or clean 7 or fewer, falsifies it.
- **P2 (at the frozen budget).** R17: answered at least 14 (13), clean at least 7 (6), all-seven at least 3, no
  problem lost. Clean 6 or fewer falsifies it.
- **P3 (the mechanism).** Of the repair asks whose witness is a well-formedness error, at least a third are
  accepted by the gates. Under a third falsifies it: the student does not act on compiler-style findings either.
- **P4 (what decides).** P1 or P2 holds: `--proof-repair` enters the route of record at its budget. Both fail
  and P3 holds: the repairs are accepted but do not verify, so the proof stage's limit is the prover, not the
  gate, and the next row is annotation-and-proof data or the dense reward. P3 fails: feedback does not work on
  this student at either stage, and only training can move it.

Sources: ExVerus arXiv:2603.25810, AxDafny arXiv:2606.32007 (the repair loop), SAFE arXiv:2410.15756.

## Result (2026-10-21 15:06Z; generated 12:50Z, graded in the desktop container, paired)

| arm | answered | clean | all seven | repair asks | accepted by the gates | paired against |
|---|---:|---:|---:|---:|---:|---|
| R17 | 14 (13) | 6 (6), the same six | 3 (3) | 7 | 1 | `v5-20261021-dev-desktop-r2` |
| R39 | 16 (16) | 7 (7), the same seven | 3 (3) | 25 | 0 | `v5-20261021-oracle39` |

Receipts `release/evidence/v5-proof-repair17-2026-10-21.json`, `v5-proof-repair39-2026-10-21.json`; records under
`t/out/v5-repair-20261021/`. **P1 falsified** (R39 answered 16, clean 7, neither moved). **P2 falsified** (R17 clean
6; one more answer, 14, and it does not verify). **P3 falsified**: 1 of 32 repair asks was accepted, far under a
third; the gate's own finding (an unbound variable, a type mismatch, a call to an undeclared helper, a failing test
with the returned value) does not get fixed by this student either. By P4 the finding is the same as the
specification stage's: feedback does not work on this student at any stage, and only training can move it.
