# t witness, 2026-09-02: the REFUTED purge (the training box, Ubuntu 24.04, x86_64)

Gate run for ROADMAP 10.7, 10.8 and 10.9: the columns that had been
selling incompleteness as REFUTED (verus, spark, framac, lean, rocq) were
purged and each given exactly one door to REFUTED, positive kernel
evidence only, and the full suite was re-run in the real tree to measure
what that honesty costs and what the certificate protocol earns back. `python3 run_par.py`: **exit 1, 194 s wall**, all 77 real
cells verified, 71 of 77 twins refuted, 6 twins timeout.

## Baseline table (git HEAD, pre-purge)

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| abs | v / r | v / r | v / r | v / r | v / r | v / r | v / r |
| all_nonneg | v / r | v / r | v / **timeout** | v / r | v / r | v / r | v / r |
| contains | v / r | v / r | v / **timeout** | v / r | v / r | v / r | v / r |
| count_matches | v / r | v / r | v / **timeout** | v / r | v / r | v / r | v / r |
| factorial | v / r | v / r | v / **timeout** | v / r | v / r | v / r | v / r |
| fib | v / r | v / r | v / **timeout** | v / r | v / r | v / r | v / r |
| gcd | v / r | v / r | v / **timeout** | v / r | v / r | v / r | v / r |
| linear_search | v / r | v / r | v / **timeout** | v / r | v / r | v / r | v / r |
| max | v / r | v / r | v / r | v / r | v / r | v / r | v / r |
| seq_max | v / r | v / r | v / **timeout** | v / r | v / r | v / r | v / r |
| sum_upto | v / r | v / r | v / **timeout** | v / r | v / r | v / r | v / r |

## New table (this run; v = verified, r = refuted)

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| abs | v / r | v / r | v / r | v / r | v / r | v / r | v / r |
| all_nonneg | v / r | v / r | v / r | v / **timeout** | v / r | v / r | v / r |
| contains | v / r | v / r | v / r | v / **timeout** | v / r | v / r | v / r |
| count_matches | v / r | v / r | v / r | v / **timeout** | v / r | v / r | v / r |
| factorial | v / r | v / r | v / r | v / r | v / r | v / r | v / r |
| fib | v / r | v / r | v / r | v / r | v / r | v / r | v / r |
| gcd | v / r | v / r | v / r | v / r | v / r | v / r | v / r |
| linear_search | v / r | v / r | v / r | v / **timeout** | v / r | v / r | v / r |
| max | v / r | v / r | v / r | v / r | v / r | v / r | v / r |
| seq_max | v / r | v / r | v / r | v / **timeout** | v / r | v / r | v / r |
| sum_upto | v / r | v / r | v / r | v / **timeout** | v / r | v / r | v / r |

15 cells changed, every one classified; zero regressions. No real-program
cell moved: 77 of 77 stayed verified.

## The certificate mechanism, in three sentences

On a twin call (and only then) the harness passes the lowering the measured
witness, and the lowering appends one extra declaration with a protocol-
fixed name (`t_refutation_certificate`; SPARK's `T_Refutation_Certificate`;
framac's `t_certificate`) whose body restates that witness as a ground
theorem: the spec's ensures fails at the measured input on the file's own
twin function. The adapter mints REFUTED if and only if the kernel itself
accepts that proof (verus: an isolated `--verify-function` run with
errors=0 verified=1; spark: gnatprove discharges every check of the
certificate function; framac: the certificate goals prove in the WP report;
lean and rocq: the theorem passes the nonce-sentinel axiom audit or the
`Print Assumptions` closedness audit). Every give-up signal that used to be
sold as REFUTED (marker lists, bare error counts, goals whose own status is
Timeout) now mints UNPROVED or TIMEOUT, so losing a flip is possible again
and the flips below were re-earned, not asserted.

## Changed cells, classified

**spark, 9 cells, timeout to refuted: earned certificate flips.**
all_nonneg, contains, count_matches, linear_search, seq_max, sum_upto
(exit-kind witnesses) and factorial, fib, gcd (value-kind). Evidence,
re-measured on this run's own artifacts: every `*_twin.ads` in `t/out/`
carries `T_Refutation_Certificate` and the adapter's extras record the
kernel discharging it in full (for example all_nonneg_twin: cert proved 8,
post_proved 1, unproved empty; factorial_twin: proved 6, post_proved 1,
unproved empty). abs and max are NOT in the changed set: they keep their
RAC-confirmed countermodels from the 10.8 first half, evidence signature
unchanged, and so classify as recovered SPARK countermodels already banked
at baseline.

**framac, 6 cells, refuted to timeout: honesty reminting.** all_nonneg,
contains, count_matches, linear_search, seq_max, sum_upto, exactly the six
invariant-drop twins the framac purge report predicted would be lost. Their
old REFUTED was a goal whose own WP status was Timeout/Stepout, which is
budget exhaustion, never a countermodel. Re-measured here:
all_nonneg_twin.c scores timeout with unproved goal
`typed_nat_all_nonneg_t_ensures` at status stepout and certificate null.
The loss is correct twice over: the witnesses for these twins are loop-exit
states, not program inputs, so no input-replay certificate exists to emit,
and the budget genuinely fired. The five value-kind framac twins (abs,
factorial, fib, gcd, max) stay refuted, now through `t_certificate`
(abs_twin.c: certificate declared true, accepted true).

**verus, lean, rocq: 0 table cells changed, every twin verdict re-earned.**
All 33 twin cells still read refuted, but the evidence underneath is new:
each `*_twin.rs`, `*_twin.lean`, `*_twin.v` in `t/out/` declares the
certificate, and the adapters now refuse REFUTED without it. Spot-checked
on this run's artifacts: abs_twin.rs and seq_max_twin.rs refute with
cert_results errors=0 verified=1 in an isolated cert run; gcd_twin.v and
linear_search_twin.v refute with certificate kernel-accepted; abs_twin.lean
and sum_upto_twin.lean refute through the lean adapter's only REFUTED door,
the declared `t_refutation_certificate` passing the nonce-sentinel audit.

**dafny, fstar: 0 cells changed, mechanism unchanged.** Fstar's REFUTED
comes through its typing and solver channel and the sweep measures it
clean. Dafny's REFUTED is still the kernel's exit 4, and the sweep shows
that door is NOT fully inside the law: exit 4 is could-not-prove, and on
one quantified true task it reads as refutation (see the sweep section).
On the 11 committed twins the door is safe in practice, every twin failure
being a ground postcondition dafny decides, but the honest generalization
lives in ROADMAP.md 10.7 as remaining scope.

Note, added later on 2026-09-02: the dafny door was closed that afternoon.
Exit 4 now reads UNPROVED, the dafny column refutes only through the same
certificate protocol, and the re-run matrix and re-sweep (REFUTES-TRUE 0
machine-wide) are recorded in WITNESS-2026-09-02-dafny-door.md. The
measurements in this file, including the REFUTES-TRUE 1 line and the
Reproduce expectation below, stand as measured at the time of this run.

## What exit 1 means now

The suite exits 1 for exactly the six framac invariant-drop twin timeouts:
an honest incompleteness on the record. It no longer means a mislabelled
verdict anywhere, and the pre-purge table's spark timeouts are gone.

## Ground truth re-sweep

Re-run of `truth_fuzz.py` (the instrument that measured the 39
incompleteness-as-REFUTED cells), modest scope: `--mirror 16`, seed
20260901, 194 tasks (107 true by construction, 76 false by witness, 11
ill-defined), 7 kernels, 1357 cells, flake n=3.

    UNSOUNDNESS  : 1 cell   (gt_def_specfun_bad, framac)
    REFUTES-TRUE : 1 cell   (gt_q_ex_lit, dafny)
    ALL-KERNEL   : 0 tasks

Zero incompleteness-as-REFUTED remains in the five purged columns (verus,
spark, framac, lean, rocq) and in fstar; on `gt_q_ex_lit` lean and rocq
now honestly read unproved where they used to refute. The two nonzero
lines are both known and both outside this wave's changed files: the
UNSOUNDNESS is 10.6's stated residual (a spec_fun body is axiomatized
total, byte-identical emission before and after this work), and the
REFUTES-TRUE is the dafny adapter's exit-4 door, could-not-prove read as
refutation, on a true task whose existential the solver will not
instantiate unprompted. The dafny door was named remaining scope in
ROADMAP.md 10.7 and closed later that day (note above;
WITNESS-2026-09-02-dafny-door.md). Neither is a regression: both doors
predate this wave,
and the sweep exits 1 for the unsoundness exactly as the pre-wave
instrument did.

## Changed instrument files (sha256)

    061ea361fdf0d670  t/lower_dafny.py
    5c99973b5dadbf7e  t/lower_verus.py
    49498a36f36857fa  t/lower_spark.py
    499925be16953b24  t/lower_framac.py
    f52693035ddd51f0  t/lower_lean.py
    8a8244b08840dc5c  t/lower_rocq.py
    55418b3496781f45  t/lower_fstar.py
    6e3bcb00a5c12496  t/verifiers/verus.py
    9842a609f26889bb  t/verifiers/spark.py
    358b0d0ca3d37a09  t/verifiers/framac.py
    afe9e1333d37d392  t/verifiers/lean.py
    29798a1bf467c23f  t/verifiers/rocq.py
    3b9e80668c1b55b1  t/harness.py
    eb970bed46953748  t/run_all.py
    df41df18486ed5dd  t/run_par.py
    574ee46e7202f7ca  t/SPEC.md

## Reproduce

    cd t
    python3 run_par.py            # full matrix; expect exit 1, the six
                                  # framac twin timeouts, 77/77 reals
    python3 truth_fuzz.py --mirror 16 --jobs 48 --out <a directory outside the repo>
                                  # expect UNSOUNDNESS 1 (framac 10.6
                                  # residual), REFUTES-TRUE 1 (the dafny
                                  # exit-4 door), ALL-KERNEL 0
    git show HEAD:t/AGREEMENT.md  # the pre-purge baseline to diff against

Adapter evidence for any single cell replays from the run's own artifacts,
for example:

    python3 -c "import sys; sys.path.insert(0,'.'); from pathlib import Path; \
    from verifiers import spark; r = spark.verify(Path('out/all_nonneg_twin.ads')); \
    print(r.outcome, r.extras['cert'])"
