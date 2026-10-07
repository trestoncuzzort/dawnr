# Zoom out, 2026-10-07: what the engine is now, what the landscape says, and what it decides

Written 2026-10-07 01:32Z, after the depth programme of 2026-10-06/07 (T9-T21) and a fresh landscape survey
(`internal/RESEARCH-2026-10-07-landscape-survey.md`: every competitor number there was read on a fetched page and
re-checked against raw text). This note supersedes the ordering in `internal/RESEARCH-2026-10-06-landscape.md`
where the two disagree, and corrects four of its claims.

## 1. Where the engine stands (measured)

| measure | 2026-10-06 21:20Z | 2026-10-07 01:20Z |
|---|---|---|
| repository | `t/` inside dawnr | its own repository, t-proof-engine, with its history |
| committed tasks | 84 | 88 |
| verified with the twin refuted in all seven kernels | 36 | 47 (48 if T21's matrix reads as registered) |
| per kernel | Dafny 84, Verus 76, F* 53, SPARK 50, Rocq 43, Lean 40, Frama-C 36 | Dafny 88, Verus 80, Rocq 62, Lean 61, F* 58, SPARK 55, Frama-C 49 |
| twin refuted where the real is verified | 100% in every kernel | 100% in every kernel |
| AlgoVeri contracts stated in t | 0 | 21 of the 22 stateable; Dafny 21, Verus 6, F* 5, SPARK 3, Frama-C 2, Rocq 1, Lean 0 |
| MALFORMED cells on AlgoVeri | n/a | 13 found, 11 repaired (T15, T17), 2 named and open |

What moved the numbers was depth, as the 10-06 note decided. Two things carried it: the library, in Lean, Rocq
and Frama-C; and comprehension maps, in every kernel. Each landing was registered before its run, and each was
read cell by cell against a whole-column re-run. AlgoVeri was the first outside benchmark the lowerings had met,
and it found six defect classes that none of the 88 tasks reach.

## 2. What the landscape says (read on 2026-10-07)

1. **The twin is no longer unique.** SWE-Proof ships a "pre-fix twin" per task that must fail to verify, in three
   backends, with a mutation-kill check. SpecSyn and MutDafny score specs by refuted mutants. What stays
   distinct in t:
   - the twin is one mechanical edit away, with a measured witness;
   - REFUTED means the kernel accepted a certificate at that witness, never a bare verifier failure;
   - the same twin is refuted in all seven legs.
2. **Multi-verifier benchmarks.** VerifyThisBench covers seven tools, but its tasks differ per tool. Aligned
   benchmarks stop at three verifiers (AlgoVeri, Vericoding, SWE-Proof). t's claim, one statement checked in
   seven, holds for aligned contracts and should be worded that way.
3. **The seven kernels are not seven independent solvers.** Dafny (through Boogie) and Verus both default to Z3.
   SPARK runs on Why3 with CVC5 and Z3, and Frama-C's WP on Alt-Ergo and others. Lean and Rocq are
   kernel-checked, and Lean documents independent re-checkers (comparator with nanoda, lean4checker). "Seven
   independent kernels" overstates it; "seven independent front ends, five distinct proof engines, two of them
   small trusted kernels" is accurate.
4. **Lean is no longer the weak leg for agents.** CLEVER went from 1/161 to 98.1%, and Aristotle resolves 96.8% of
   VERINA. It is still the weak leg for one-shot writing and on AlgoVeri (7.8% direct). In t, Lean carries 10 of
   the 21 AlgoVeri contracts and verifies none, and it co-blocks 20 of them.
5. **Defective specs are common, and nobody grades them by cross-kernel refutation.** LeetProof finds 8.5% of
   VERINA's and 11.2% of CLEVER's specs defective, Vericoding about 9% too weak, and Aristotle 23 false VERINA
   statements.
6. **Agents bypass weak checks.** In 49,280 SPARK obligations, agents used `pragma Assume`, then `SPARK_Mode => Off`.
   An unstaged agent plus a verifier "proves 98% of both the correct and the known-buggy programs". This is the
   failure t's no-assume rules and its twin exist to stop.
7. **Competitors lead** on scale and real code (500 real issues, 849 Verus tasks, 12,504 specs), language reach
   (heaps, Rust), agentic proof search, foundational trust (a verified Dafny VCG in HOL4), and shipping code.

## 3. Corrections to the 10-06 note

- "None pairs each proof with a refuted mutant": SWE-Proof does, on three backends (item 1 above).
- "No system targets more than three verifiers": true only for aligned tasks; VerifyThisBench uses seven.
- "Lean is the weak leg on every multi-verifier benchmark": true for one-shot writing, not for agents.
- AxDafny "paper only": its paper names a repository that returned 404 on 2026-10-07.

The engine's README states none of the four, so it needs no change. Its "seven independent proof systems" wording
is corrected by item 3.

## 4. Decisions, in order

Each is its own registration, measured before it is claimed.

1. **D6, a common-mode audit (low effort).** Re-run the SMT-backed legs under a second solver: Dafny through
   Boogie's CVC5, and SPARK and Frama-C with their own alternate provers. Replay the Lean cells through an
   independent checker. The table this produces is agreement under solver change, which answers item 3 with a
   measurement instead of wording. Verus has no second solver and is reported as such.
2. **D7, Lean loops through `mvcgen` (a one-task probe first).** Lean co-blocks 20 of 21 AlgoVeri contracts, and
   `t/lower_lean.py` drives every loop proof through `grind` alone. Lean's own tutorial pairs `mvcgen` (loop
   invariants supplied, which t's loops always carry) with `grind` for the rest. Bar for the probe:
   `integer_exponential`, the AlgoVeri task Lean alone keeps from six-kernel agreement, verifies with the twin
   refuted.
3. **The near misses on the 88 (low effort each).** Three tasks are one kernel short of all seven: `palindrome`
   (Frama-C: a `rev` local needs a workspace buffer; the patch is written and shelved), `odd_positions` (Lean: an
   index sum `grind` does not reorder) and `swap_rows` (Frama-C: a nested-seq return). `double_all` is a Frama-C
   timeout. With `largest` (T21), these are the cheapest all-seven gains left.
4. **G9, datatypes with fields (high effort, high value).** Records and non-recursive sums first, then recursive
   ones. 37 of AlgoVeri's 55 unstated contracts need them. The v1 AST already carries `ctor` arguments and `match`
   binders, and `check_wf`'s `ctor-fields-not-v1` rule is the gate to lift. Waves: Dafny, Verus, Lean; then Rocq,
   F*; then SPARK, Frama-C; then recursion.
5. **D8, a twin audit of public benchmark specs (medium-high effort, the most distinctive result available).**
   Lift what t can state from Vericoding's Dafny sources (which include VERINA, CLEVER and DafnyBench). For each
   spec, publish whether its twins are refuted in every kernel: a kernel-checked weak-spec count. No published
   work grades spec strength this way, and the defect rates above say there is something to find.
6. **D9, DafnyComp's chained programs (medium).** Lift 30 of the 300. Models fall from over 58% to 3.69% verified
   when functions compose, and t's methods, lemmas and per-function twins give a compositional agreement table.
7. **Proposed, not started: a model writing t against AlgoVeri's per-language baselines.** This is the real test
   of "write once, verify seven", and the twin would replace the LLM judge that cost direct Dafny about 15
   points. It needs a model budget and the operator's go-ahead: on 2026-10-06 the operator paused assistant,
   training and speed work until t is done.
8. **Later: one foundational column.** Lower to Velvet or Strata Core, so one leg's verification conditions have
   Lean semantics. Both are pre-1.0 with breaking changes announced, so this follows 1-6.

## 5. What this note does not change

The rules: refusal by name, never a weakened spec; a prediction before every run; the twin rule; tables installed
only from a clean clone. The landscape changes what is claimed and what comes first, not how anything is measured.
