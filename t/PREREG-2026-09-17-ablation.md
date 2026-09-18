# Preregistration: what the seven checkers and the twin rule actually buy

Written 2026-09-17, before the measurement was run. The script that measures it is `t/ablation.py`, and it was
written after this file and before any number in it was read.

## The claim under test

This project spends seven independent proof systems and a deliberately broken twin on every training example.
The cheap alternative is one prover, or seven provers without the twin rule. The claim is that the extra cost
buys a lower **false-accept rate**: answers the gate admits that are wrong.

"Wrong" here is decided by the problem's own tests, which are not part of any gate. An answer is a false accept
when the gate admits it and its tests fail.

## The gates compared

Each gate is applied to the same graded answers, so nothing is regenerated and nothing is regraded.

| Gate | Admits an answer when |
|---|---|
| `dafny` | Dafny verifies the program. The twin is ignored. |
| `dafny+twin` | Dafny verifies the program and refutes its twin. |
| `any1` | At least one of the seven verifies the program. The twin is ignored. |
| `four+twin` | At least four verify with the twin refuted (the `--min-kernels 4` setting used in earlier rounds). |
| `seven` | All seven verify the program. The twin is ignored. |
| `seven+twin` | All seven verify and all seven refute the twin. This is what the project calls clean. |

## What is reported, per gate

1. **Accepted**: answers admitted.
2. **False accepts**: admitted and the tests fail.
3. **False-accept rate**: 2 divided by 1.
4. **Problems covered**: distinct problems with at least one admitted answer.
5. **Prover seconds per accepted answer**, from the check events, so the cost of each gate is beside its error.

## The decision rule, fixed now

- If `seven+twin` has a false-accept rate at least **five times lower** than `dafny` while covering at least
  **half** the problems `dafny` covers, the seven-checker gate with the twin rule is worth its cost and stays as
  the definition of clean.
- If `dafny+twin` or `four+twin` matches `seven+twin` within **one percentage point** of false-accept rate while
  covering **more** problems, then the cheaper gate is the better instrument and the project should adopt it,
  say so in the README, and re-derive the pool with it.
- If no gate separates on false accepts, the tests are doing all the work, the proofs are decoration on this
  corpus, and that is the finding to publish.

Any outcome is reportable. The numbers go into `t/ABLATION-2026-09-17.md` and the row that names the winner
goes into the README whatever it says.

## Sample

Every answer set graded in this repository that has both `kernels.md` and `tests.json`: the 27B's sets, the
14B's eight seeds, the HumanEval sets, deepseek's two seeds, the repaired sets, and the held-out answers of
Phi-4-mini, the untrained 1.5B, the student and locallm. Answer sets whose problems are held out are counted
separately from training-problem sets, since a held-out answer can never enter the pool.
