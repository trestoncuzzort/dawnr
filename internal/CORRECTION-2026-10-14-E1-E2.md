# Correction (2026-10-14): E1 false-accept curve and E2 independence claim are NOT supported as published

Found by independent code/data audit. The original numbers are kept (in docs/MEASURED.md, SCOREBOARD.md,
internal/E1-data, internal/E2-data) as evidence; the claims built on them are withdrawn or qualified here.

## 1. Missing kernel observations were counted as rejections (E1 and E2 — the core defect)

`t/audit.py` (lines ~185–189) adjudicates a survivor in a kernel ONLY when the real body verifies in that
kernel, and breaks at the first survivor it proves. So most survivors were observed by only some kernels.
In the committed `internal/E2-data`, of **167 survivors only 48 were adjudicated by all seven kernels**
(saw-count distribution {1:40, 2:12, 3:14, 4:28, 5:11, 6:14, 7:48}). `internal/e1_adequacy.py` computed
`false_accept(k) = survivors proved by ≥k kernels / 167`, treating a kernel that never observed a survivor
as "did not prove." Of the 74 survivors between "accepted by ≥1 kernel" (112) and "accepted by all seven"
(38), **71 have incomplete observation (saw<7)** — they dropped out because kernels did not run on them,
not because any kernel refuted them.

**Therefore the published "single-prover 67% → seven-kernel 23% false-accept, a threefold reduction by
cross-kernel agreement" is NOT established.** Non-observation was conflated with refutation. The only
defensible false-accept statement is over the 48 fully-adjudicated survivors, and even that must separate
refuted from unverifiable.

## 2. `T_MIN_KERNELS` is an availability floor, not a vote threshold (E1)

`t/cli.py` (~line 403) uses `T_MIN_KERNELS` as the minimum number of *available/installed* kernels needed
to write a table — not a k-of-seven acceptance vote. The operational gate's acceptance rule is separate (a
column counts when the real body is VERIFIED, its twin REFUTED, and the two agree). The "threshold k" in
E1's curve is an experimental vote construct I defined; labelling it "the T_MIN_KERNELS knob" was wrong.

## 3. SPARK used Z3, not cvc5 (E2)

`t/verifiers/spark.py` pins the prover to the bundled Z3 (`--prover=z3`, line 185); no override was set in
the recorded commands or `e1_adequacy.py`. The gate's SMT backends are **Z3 for four kernels (dafny, verus,
fstar, spark), Alt-Ergo for framac, and no SMT for lean and rocq** — not "three independent SMT solvers."
The E2 claim that the floor is "confirmed across three independent SMT cores" is wrong; it rests on two SMT
solvers (Z3-dominant) plus two proof assistants, on the same incomplete-observation data as E1. Any cvc5
comparison must set `T_SPARK_PROVER`/`--prover` explicitly and keep version receipts.

## 4. A behaviorally-different survivor may be a spec-permitted alternative, not a wrong program (E1)

`t/audit.py`'s own text notes a survivor can be "a latitude the author intended (a spec that allows either
of two answers)." Calling every accepted survivor a "false-accept" or "prover-unsound" overclaims;
intended-task incorrectness must be established first.

## What still stands

The spec-level mutation kill rate — **95.1% of behaviour-changing one-edit mutants killed by the spec**,
over 893 tasks — is unaffected: it is interpreter-decided and kernel-independent, not a function of kernel
observation. The *existence* of spec-gap survivors that every adjudicating kernel accepts is real (the
hand-audited plusOne / summax / findMax cases). What is withdrawn is their *rate*, the 67%→23%
agreement-removal story, and the three-SMT-backend independence claim.

## The fix (in progress)

A fully-adjudicated mutant matrix: every mutant adjudicated in every kernel (no real-verified gating, no
early stop), retaining four states — verified / refuted / unverifiable-with-reason / not-run — with stable
mutant identities and common denominators, never counting a missing observation as a rejection. The engine
change lands in `t-proof-engine` first (AGENTS.md), then `t/sync_engine.sh`. Plus an explicit
alternate-solver comparison where supported (SPARK `--prover=cvc5`, Frama-C `-wp-prover z3`), honest refusals
for unsupported paths, and an intended-incorrectness check on a survivor sample.
