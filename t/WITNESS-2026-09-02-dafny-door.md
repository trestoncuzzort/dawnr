# t witness, 2026-09-02: the dafny door (the training box, Ubuntu 24.04, x86_64)

Gate run for the last item of ROADMAP 10.7: the dafny column, the one
door the morning's REFUTED purge left outside the law (kernel exit 4 read
as REFUTED), was brought inside it later the same day and the full suite
was re-run in the real tree. `python3 run_par.py`: **exit 1, 190 s wall**
(user 35 m 16 s), all 77 real cells verified, 71 of 77 twins refuted, 6
twins timeout. Every one of the 77 cells is identical to the committed
table; only the evidence under the 11 dafny REFUTED cells changed.

Toolchain: dafny 4.11.0+fcb2042d, Z3 as bundled; the other six kernels as
recorded in AGREEMENT.md, unchanged from the purge witness.

## Before table (git show HEAD:t/AGREEMENT.md, 2026-09-02 09:26Z)

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

In this table the 11 dafny `r` cells were minted by the old rule: kernel
exit 4, could-not-prove, sold as refutation.

## After table (this run, 2026-09-02 13:01Z; v = verified, r = refuted)

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

0 table cells changed; `diff` of the two AGREEMENT.md files differs only in
the header timestamp. The 11 dafny `r` cells are now certificate flips:
every `*_twin.dfy` in `t/out/` carries exactly one
`lemma t_refutation_certificate()`, no real `*.dfy` carries it, and the
adapter refuses REFUTED without it. Zero REFUSED lines in the runner
output, so no verdict flaked (flake n=3 on every cell). The suite still
exits 1 for the six framac invariant-drop twin timeouts and for nothing
else.

## The mechanism, in one paragraph

`verifiers/dafny.py` no longer maps kernel exit 4 to REFUTED: exit 4 reads
TIMEOUT on "out of resource" and UNPROVED otherwise, never REFUTED. On a
twin call, and only then, `harness.py` hands `lower_dafny.py` the measured
witness and the lowering appends one parameterless
`lemma t_refutation_certificate()` whose single `ensures` restates that
witness as a ground theorem over the file's own twin: for a value witness
(abs, factorial, fib, gcd, max) the ensures fails at the twin's result on
the measured input; for an exit witness (the six invariant-drop twins) the
twin's surviving invariants and the negated guard hold at the measured
loop-exit state and the ensures conjunction fails there. Bounded
quantifiers are unrolled with their bounds restated as kernel-checked
conjuncts, seq witnesses are let-bound by name inside the ensures, spec_fun
values get an `assert f(args) == v;` ladder in the lemma body, and operands
t's short-circuit semantics never evaluated are pruned with each deciding
operand hoisted as a top-level conjunct, because dafny 4.11.0 proves the
index-in-range obligation of `s[(-1)]` under a false guard from the
contradiction and `--warn-contradictory-assumptions` then ends the whole
file at exit 2. The adapter mints REFUTED if and only if an isolated
`dafny verify --filter-symbol=t_refutation_certificate.` run (trailing dot
measured to anchor the end of the name) exits 0 with every "Results for"
block of its text log naming exactly that lemma at outcome Correct, the
kernel's own `--rprint` of the main run shows exactly one unmodified
`lemma t_refutation_certificate()` with exactly one ensures and no
requires, and every failing block of the main run belongs to a plain
`method`, since the filtered run assumes callee contracts unverified. A
file naming the certificate can never mint VERIFIED, and a certificate the
kernel rejects or cannot read mints UNPROVED. Evidence replayed from this
run's own artifacts: abs_twin refutes with cert_exit 0, 1 verified, 0
errors, `t_refutation_certificate (correctness): Correct`; linear_search
twin refutes with 2 verified, 0 errors, the second being the
`(well-formedness)` task dafny splits off for its index obligation; abs
real verifies with certificate absent.

The refusals were measured on the abs twin and the abs real the same day
(all UNPROVED unless stated): the honest certificate planted in the
verified real program reads REFUTED, not VERIFIED, as the protocol
requires; the name in a comment; the full declaration text in a comment
plus a `lemma xt_refutation_certificate() ensures true {}` decoy, which
the filter does match; `ensures 1 == 2`; `requires false` with the honest
ensures (the contradictory-assumptions warning fires and the isolated run
ends at exit 2) and with `ensures false`; a satisfiable requires; a second
ensures; a decreases clause; a method-, twostate- or least-typed
certificate; a parameterised one; a module wrapper; a failing helper
`lemma bad() ensures false {}` called from the certificate; a
non-terminating function used by it. What the adapter cannot check is that
the ensures IS the negated spec at the witness: that binding is the trusted
lowering's, so a content-free `ensures true` certificate is kernel-accepted
and reads REFUTED, exactly as a hand-planted certificate does in verus.

## Ground truth re-sweep

Re-run of `truth_fuzz.py` at the purge witness's scope: `--mirror 16`,
seed 20260901, 194 tasks (107 true by construction, 76 false by witness,
11 ill-defined), 7 kernels, 1357 cells, flake n=3 with zero disagreements,
211 s wall.

    Before (the purge witness, same seed, corpus and scope, that morning)
    UNSOUNDNESS  : 1 cell   (gt_def_specfun_bad, framac)
    REFUTES-TRUE : 1 cell   (gt_q_ex_lit, dafny)
    ALL-KERNEL   : 0 tasks

    After (this run)
    UNSOUNDNESS  : 1 cell   (gt_def_specfun_bad, framac)
    REFUTES-TRUE : 0 cells
    ALL-KERNEL   : 1 task   (gt_width_loop, FALSE)

The dafny column after, by row class: TRUE 107 rows, pass 99, incomplete 8
(7 malformed at exit 2, 1 unproved at exit 4, and that one is
`gt_q_ex_lit`, the morning's REFUTES-TRUE cell, now read honestly);
FALSE 76 rows, pass 0, incomplete 76 (all unproved, exit 4); ILLDEF 11
rows, pass 0, incomplete 11 (all unproved, exit 4). The before split is
not on a per-cell record (the purge sweep kept only its headline), but it
follows from the old rule: every FALSE and ILLDEF dafny cell still exits 4
today and exit 4 was REFUTED then, so those 87 cells graded pass before
and grade incomplete now. That is the dafny FALSE-row cost, stated
plainly: the column lost 87 fuzz passes it had never earned, the same cost
the five purged columns paid that morning under ROADMAP 10.7 residual (1),
because the sweep lowers FALSE rows without the witness it holds and no
certificate is emitted. ALL-KERNEL rising from 0 to 1 is the same fact
seen from the other side: on `gt_width_loop` every kernel now reads
non-pass (dafny unproved, verus unproved, spark unproved, framac timeout,
lean unproved, rocq unproved, fstar abstain), and dafny's exit-4 door had
been the one column masking that shared incompleteness. The UNSOUNDNESS
line is 10.6's stated residual, unchanged. `gt_q_ex_lit` replayed through
the new adapter from the sweep's own lowered source: unproved, exit 4,
ok=False, certificate absent.

Cost: one extra kernel run per twin verify call, about the cost of the
main run. Remeasured 2026-09-02 on the shipped adapter, sequential on an
idle box, the abs, seq_max, linear_search and count_matches twins three
runs each: isolated run mean 1056 ms (978 to 1101) against 1113 ms (1027
to 1173) for the main run with its rprint and text log. (An earlier
reading of 812 ms and 860 ms on the abs and linear_search twins against a
946 ms main run predates the rprint and text log and is superseded.)
Real-program calls pay nothing, the certificate is absent there and the
isolated run is not made.

## Changed instrument files (sha256)

    ee004482eff50645  t/lower_dafny.py
    f9a72736d3007725  t/verifiers/dafny.py
    54aa8986bec869b2  t/harness.py

`harness.py` changed in two statements only: the twin and real fixture
writes pass `newline="\n"`, matching `run_all.py` and `run_par.py`, so the
per-column driver path no longer writes CRLF fixtures on Windows. It is
verdict-neutral; a CRLF linear_search twin reads REFUTED with the same
certificate detail.

## Reproduce

    cd t
    python3 run_par.py            # full matrix; expect exit 1, the six
                                  # framac twin timeouts, 77/77 reals,
                                  # every table cell as above
    python3 truth_fuzz.py --mirror 16 --jobs 48 --out <a directory outside the repo>
                                  # expect UNSOUNDNESS 1 (framac 10.6
                                  # residual), REFUTES-TRUE 0,
                                  # ALL-KERNEL 1 (gt_width_loop)
    git show HEAD:t/AGREEMENT.md  # the pre-change table to diff against

Known pre-existing: the `AGREEMENT.md` header line the runners emit
(`run_par.py`, `run_all.py`) carries a dash that predates this wave; the
generator is out of this wave's files, so every gate run re-adds it.

Adapter evidence for any single dafny cell replays from the run's own
artifacts:

    python3 -c "import sys; sys.path.insert(0,'.'); from pathlib import Path; \
    from verifiers import dafny; r = dafny.verify(Path('out/abs_twin.dfy')); \
    print(r.outcome, r.exit_code, r.extras['certificate'])"

The morning's mislabel replays from the sweep's lowered source and must
now read unproved:

    python3 -c "import sys; sys.path.insert(0,'.'); from pathlib import Path; \
    from verifiers import dafny; r = dafny.verify(Path.home()/'t-truth-fuzz'/'src'/'gt_q_ex_lit.dfy'); \
    print(r.outcome, r.exit_code, r.ok, r.extras['certificate'])"
