# Targeted follow-up to the 2026-10-10 seven-kernel sweep

Registered before isolated kernel rechecks or implementation. The completed sweep
has three cells whose real program verified but whose twin did not refute:
`relu_all` and `px4_request_event_fixed` in SPARK (timeout), and
`readings_in_band` in Verus (unproved). None counts as agreement. The sweep's
tables and verdicts remain historical evidence, not targets to overwrite.

The Verus gap is documented in T52 of `PREDICT-2026-10-06-t-expansion.md`:
grounding the filter's free variables changes its registered shape, so its
certificate is omitted. The emitted Lean `crosstrack_side` also contains
unconditionally nonnegative-product helper theorems that are false for
mixed-sign inputs. Lean rejects those helpers; this is lost coverage, not a
false proof.

Prior art: the existing Dafny ground comprehension expansion (T3b-3),
`lower_verus._unroll` and its finite budget; Verus's
[proof by computation](https://verus-lang.github.io/verus/guide/assert_by_compute.html)
and [compute_only reference](https://verus-lang.github.io/verus/guide/reference-prover-mode-compute.html).
`compute_only` must reduce the actual ground proposition to true; the host
interpreter must not replace a certificate with an asserted truth value.
Lean's [tactic reference](https://lean-lang.org/doc/reference/latest/Tactic-Proofs/Tactic-Reference/)
documents `omega`'s linear arithmetic scope and propositional case splitting.
The replacement sign helper states only that same-sign factors have a
nonnegative product, using the core `Int.mul_nonneg` and
`Int.mul_nonneg_of_nonpos_of_nonpos` theorems already used by this lowering.
The local research mirror was unavailable at its documented location.

Predictions and falsifiers:

1. Recheck the three original cells individually, with three sequential calls
   per source and full adapter receipts. Verus will remain verified/unproved
   because its twin has no certificate. SPARK may remain a limit or recover
   outside contention; either result is recorded separately and cannot change
   the historical sweep. A verified twin or unsupported promotion falsifies
   the trust boundary.
2. A bounded expansion of a ground comprehension into conditional singleton
   sequences will retain its filter and mapped expression. The real
   `readings_in_band` source stays byte-identical; its twin gains a certificate
   accepted by Verus at `s=[0], lo=hi=1`. Unsupported sources and exhausted
   expansion budgets still refuse certification. The false claim that the
   same twin returned zero must not receive an accepted certificate.
3. Lean's product-sign support must never require every product seen inside a
   conditional postcondition to be nonnegative. Any replacement auxiliary
   statement must hold for both mixed-sign and same-sign factors, while the
   existing valid sign-bridge use remains provable. `crosstrack_side` must
   verify with its measured twin refuted; an axiom, dropped user obligation,
   or new false helper falsifies the change.
4. After targeted controls pass, rerun the full 114-task columns for every
   changed backend in an isolated staged checkout. Report every moved cell
   and every limit; do not install a new agreement matrix from a column run.

## SPARK renamed-loop follow-up registered after the isolated rechecks

All three old-source repetitions reproduced `px4_request_event_fixed` as
verified/timeout. The certificate's own postcondition exhausted its step
budget; this is not a wall-clock timeout. Inspection shows `last` is renamed
to `t_last`, which selects a fresh certificate Lower without the already
emitted loop clones and with no final body. The certificate therefore calls
the contracted F instead of replaying F_Cert. This is the existing fallback
documented beside `cert_L` in `lower_spark.py`.

Prior art: the existing loop-replay path and its positive/negative controls
in `test_spark_multiloop_kernel.py`, and AdaCore's
[function proof-context documentation](https://docs.adacore.com/spark2014-docs/html/ug/en/appendix/additional_annotate_pragmas.html#annotation-for-inlining-functions-for-proof).
Function contracts and expression definitions affect the proof context;
renaming alone must not replace execution replay with an unproved contract.

Prediction: for value witnesses of renamed loop tasks, consistently rename
the task, twin body, and witness together and use the already-populated Lower
and rendered body. The real source remains byte-identical, while the twin
uses F_Cert. The PX4 request-event twin should refute in three calls. Supplying
that same alleged counterexample to the correct real body must reach the
certificate checker and be rejected, never refuted or verified. If this
negative control fails, no change lands. Non-value witnesses and sources
without renames must retain their existing paths. The whole SPARK task
column must be rerun from a separate frozen candidate after targeted controls.

## Targeted read and completed Lean/Verus columns

The old-source rechecks reproduced all three gaps in three sequential calls
per side: Verus `readings_in_band` was verified/unproved, SPARK `relu_all`
and `px4_request_event_fixed` were verified/timeout. SPARK's own audits
report step limits, including an unproved certificate postcondition in both
twins. These were not promoted to refutations.

With the repairs, three repetitions of every following control agreed:

| control | outcome |
|---|---|
| Verus `readings_in_band`, real / twin | verified / refuted |
| Verus same twin with fabricated return value 0 in its certificate | unproved |
| Lean `crosstrack_side`, real / twin | verified / refuted |
| Lean `px4_sq`, real / twin | verified / refuted |
| Lean existing hexagonal-number sign-bridge shape | verified |
| SPARK `px4_request_event_fixed`, real / twin | verified / refuted |
| SPARK same alleged counterexample attached to the correct body | timeout |

The last control reached the certificate checker: zero certificate
postconditions proved, one unproved. The repaired twin instead proved its
certificate postcondition. Neither repair introduces an axiom or changes a
user contract. Lean's original unconditional helpers were false; conditional
same-sign helpers proved, but the task initially remained unproved until
splitting its actual branches before `omega` closed the specification.

Persistent native controls are in `test_certificate_sweep_kernel.py` and
`test_spark_multiloop_kernel.py`. Running
`PYTHONPATH=t python3 -m unittest test_certificate_sweep_kernel test_spark_multiloop_kernel -v`
on the frozen candidate passed all five tests (42 adapter verification calls,
three repetitions per source) in 116 seconds. The emitted-source comparison across all
177 tasks found only these changes: Verus `readings_in_band` twin; Lean
`crosstrack_side` and `px4_sq` real/twin; SPARK
`px4_request_event_fixed` twin. All 114 `t/tasks` real and twin source files
were byte-identical in each changed backend.

The frozen candidate's whole 114-task columns were run with
`T_MIN_KERNELS=1 python3 t/cli.py verify t/tasks --kernels K --jobs 2`
and separate explicit `--out` and `--table` destinations:

| column | verified / refuted | abstain / abstain | other cells | moved vs. prior sweep |
|---|---:|---:|---|---:|
| Verus | 104 | 7 | 3 unproved / refuted | 0 |
| Lean | 89 | 21 | 3 unproved / refuted; 1 unproved / unproved | 0 |
| SPARK | 79 | 30 | 4 timeout / refuted; 1 verified / timeout | 0 |

Three additional SPARK negative probes used the correct body with fabricated
counterexamples at `(first, last, capacity)` equal to `(0, 0, 1)`,
`(65535, 0, 2)`, and `(0, 2, 1)`. Each single diagnostic call reached the
certificate checker, proved zero certificate postconditions, and timed out
with that postcondition unproved. These cover executing a loop, wrapping the
sequence number, and truncating to capacity; they do not count as successful
proofs or three-run agreement measurements.

The SPARK column completed in a separate jobs-8 run using the same frozen
sources and proof budgets, capped at 32 GiB and 48 logical CPUs. It took
354.1 seconds wall time and 13,090.9 CPU seconds, with 7,600,734,208 bytes
of peak cgroup memory (7.08 GiB; this is aggregate cgroup memory, not a
per-process RSS measurement). All 60 completed cells from the preserved
jobs-2 run matched, including flake status, before its redundant remainder
was stopped. Its partial log is retained.

All three full columns reproduced every historical outcome. The existing
SPARK `relu_all` twin remains a timeout; none of the unresolved cells is
counted as agreement. The three targeted coverage repairs passed their
positive and negative native controls, while the all-seven aggregate remains
unmodified. These column runs do not replace `AGREEMENT.md`.
