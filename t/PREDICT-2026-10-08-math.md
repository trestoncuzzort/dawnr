# Math problems with t: UVa / uDebug (registered 2026-10-08)

## T73 registered (2026-10-08 18:20Z, after three hand runs and before the rest): judge-checked proofs of UVa math problems

**What changes.** `problems/uva/` holds one t task per UVa Online Judge math problem: the task's `ensures` states the
problem, its body solves it. `t/judge.py` translates the task's Dafny lowering to Python once (`dafny translate py
--include-runtime`, unbounded integers) and runs it on uDebug's judge inputs; a per-problem `_io.py` reads the
input and writes the output. The judge files are the user's uDebug export and are not committed.

**Measured before this registration (by hand):**
- 495 Fibonacci Freeze: 6 of 7 kernels verified with the twin refuted (F* proved the real program; its twin was not
  refuted, so the cell does not count). uDebug: 5 of 5 files with a stored output match (2,989 lines); the sixth
  file's stored output is uDebug's placeholder "Sorry! Output limit exceeded!".
- 10302 Summation of Polynomials (spec: the sum of cubes as stated; body: the closed form, proved by Nicomachus'
  theorem as an induction lemma): 4 of 7 (Dafny, Lean, Rocq, F*). uDebug 4 of 4 files (100,716 lines).
- 369 Combinations (spec: N!/((N-M)!M!) as stated): 3 of 7 (Dafny, Frama-C, F*) once the spec states its divisor
  is positive before dividing; Dafny refused the first version for a possible division by zero in the ensures.
  uDebug 2 of 2 files (1,255 lines).

**Bars**, read when the batch is done:
(1) Every problem attempted either passes every uDebug file that has a stored output, or is reported as failing
    with the first differing line. No failing problem is dropped from the table.
(2) Every attempted problem is verified with the twin refuted in at least one kernel; the per-kernel count is the
    reported number, never a total.
(3) The statement is the spec: each task's README row says whether its `ensures` is the statement's own definition
    or a standard model of it (a recurrence the statement implies), and a model row is named as such.

**Added before the clean-clone run (2026-10-08 18:35Z).** The batch grew to 23 problems by hand: 10007, 10223,
10268, 10302, 10312, 10334, 10541, 10551, 10931, 11384, 11526, 11847, 11955, 12004, 1224, 12712, 12918, 343, 369,
495, 496, 575, 991. Every one passes every uDebug file that has a stored output, by hand on this machine, and every
one verifies in Dafny with `--warn-contradictory-assumptions` and no warning, also by hand. Two Dafny refusals on
the way were the engine doing its job: 369's first spec could divide by zero, and 10551's first uniqueness lemma
argued by contradiction, which the vacuity guard reads as "proved for the wrong reason"; both were rewritten, not
the guard. The bars above are read on a clean clone of the commit that adds this text.

### T73 read (2026-10-08 18:48Z): all three bars held

Clean clone of 3219642 on the lab, `python3 t/cli.py verify problems/uva --jobs 24`, table installed as
`problems/uva/AGREEMENT.md`; judge runs by hand on this machine against the uDebug export.
- **(1) held.** All 23 problems pass every uDebug file with a stored output: 179,549 lines. 495's sixth file holds
  uDebug's placeholder, not an output, and is reported as such.
- **(2) held.** Every problem is verified with the twin refuted in at least one kernel. Per kernel: Dafny 22,
  Frama-C 13, Verus 10, SPARK 10, Lean 10, F* 10, Rocq 7. In all seven: 991, 10334, 10931; 495 in six (F*'s twin
  unproved). Dafny's one miss is 496, whose twin it does not refute; SPARK refutes it. 343 and 496 abstain in most
  kernels (a seq-returning task with nested quantifiers, methods returning bool over seqs).
- **(3) held.** README.md labels every row "the statement" or "a model".

What it establishes: a specification written from a problem statement, a proof in at least one independent kernel,
and the proved code reproducing the judge's outputs, for 23 UVa problems. What limits the kernel counts is mostly
nonlinear arithmetic: Lean's lowering states `pow` through `toNat` (575's step `pow(2, e+1) = 2·pow(2, e)` is
unsolved there; Lean 4.33's `grind` proves the ring identities themselves), Rocq's lowering discharges by `lia`, and
SPARK times out. Those are the next registration.

Added after the read, by hand (not in the clean table yet): 11231 Black and white painting (the spec counts the 8x8
boards with a white bottom-right square cell by cell; the body is the closed form ((n-7)(m-7)+c)/2, proved through
two lemmas: adjacent rows hold complementary colours, and the last row holds (m-k+c)/2) and 264 Count on Cantor (the
spec is the diagram's zigzag: diagonal by triangular numbers, direction by parity). Both pass every uDebug file and
verify in Dafny with no warning; their seven-kernel cells wait for the next clean run.
