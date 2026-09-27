# Seq-valued spec_funs, 2026-09-27

Feature 9 of `t/FEATURES-TRACK.md`, the binding refusal for string
programs: a spec_fun whose result is a sequence of ints, so that a lifted
Dafny helper function returning `string` or `seq<int>` becomes a spec_fun
instead of refusing `function-result`. Branch `feat/seq-spec-fun`, from
`r12-blockers` (fc7e7933). This file is the record: what landed, the status
of every kernel on the fixtures, the measurement on the staged corpus, what
is left and why, and how to reproduce every count. Every count names the
run that produced it; the runs live under the measuring machine's
`scratch/seqfun/` directory (not committed).

A first attempt at this feature was cut short by a machine reboot before
any commit. Its working tree survived, and so did two of its runs, which
this record reuses rather than recomputes (both were re-checked against
the code they measure): the baseline lift of the 1,886 staged files on
`r12-blockers` (`base/`, 934 s wall) and the same lift on the branch's
first lifter (`new/`, 931 s wall), whose lifter code is unchanged here
except for decision 50 below, measured by its own run (`new2/`). Its
byte-identity baseline (`hashes_base.json`, 546 entries) agrees entry for
entry with the one recomputed here from a clean export of `r12-blockers`
(`hashes_base2.json`).

## What landed

**The language** (SPEC.md "Seq-valued spec_funs (v1)", SYNTAX.md,
t/surface.py): gate 3's SpecFun has a third result type, `"seq"`, the
elementary seq of ints a parameter already has (a string is a seq of code
points). The notation writes it as it writes a parameter's type, `spec fun
dbl(s: seq, n: int): seq decreases n = ...`. A call of a seq-valued
spec_fun is a seq expression wherever an int-valued call is an int
expression: specs, invariants, other spec_fun bodies, the task body;
indexed, measured, sliced, concatenated, compared. Not in v1: a nested-seq
result, a pair result, a bool-seq result; check_wf refuses them by name
(`spec-fun-result`, a rule the notation cannot reach and the JSON gate
can, named as such in t/test_wf_errors.py's UNREACHABLE table).

**check_wf** (t/check_wf.py): the result type is checked against the three
admitted, and the body is typed against a seq result exactly as against an
int one. **The interpreter** (t/interp.py) needed no change: `ev`'s call
case evaluates the body under the parameter binding and a seq body yields
a tuple, which every seq operator already consumes; the twin gate draws
points through the same path (t/test_seq_spec_fun.py exercises `len`,
`at`, slice, `+`, `==` on a call). **The twin ladder** (t/harness.py)
needed no new rung: the twin never touches a spec_fun (SPEC.md "The
twins"), and a task body that builds a seq under an invariant stated
through a spec_fun already offers the ladder its moves; `double_all` draws
`compare-flip` on the loop guard, refuted at `s = []`.

**The lowerings.** Six kernels state the construct in their own sequence
type in the function's signature, exactly as they state an int result:

| kernel | the seq-valued spec_fun | change |
|---|---|---|
| dafny | `function dbl(s: seq<int>, n: int): seq<int>` | none needed: the result type goes through the same table a parameter's does |
| verus | `spec fn dbl(s: Seq<int>, n: int) -> Seq<int>` | none needed, likewise |
| spark | an expression function returning the functional `Seq` | none needed, likewise |
| lean | `def dbl_s (s : List Int) (n : Int) : List Int` with `termination_by` | none needed, likewise |
| fstar | `let rec dbl .. : Tot (Seq.seq int) (decreases n)` | `emit_spec_fun` renders a seq body through `sx` (an `ite` over seqs and a call in seq position joined it) and parenthesises the two-token result type: `Tot Seq.seq int (decreases n)` parses as `Tot` applied to three arguments ("Effect Prims.Tot does not take a requires or ensures clause", measured on double_all) |
| rocq | a fuel Fixpoint returning the file's own `((Z -> Z) * Z)` function-and-length pair, read back by `fst`/`snd` at a call | `emit_spec_funs` builds the pair body from `seq_fn`, the out-of-fuel default is the empty seq `(t_fill 0, 0)`, `t_eqs`/`t_eqs_h` follow the unfolding rewrite with `cbn [fst snd]`, and the four `pair_line` gates that make a pair literal reduce (`cbn [fst snd]`) fire for a task with such a spec_fun (`_has_seq_sf`) |
| framac | abstains by name | `NotImplementedError("framac: spec_fun .. returns a seq; ..")` before any text is emitted |

Frama-C abstains because this lowering models every seq as a C buffer
(`int *s, integer s_n`) and a spec_fun as an ACSL logic function over that
buffer, and a logic function cannot return a buffer; the `\list<integer>`
route (ACSL's own logic lists, `\Nil`/`\Cons`/`^`/`\nth`/`\length`, ACSL
manual "Logic specifications") needs a bridge predicate between a buffer
and a list at every `==`/`len`/`at` site on a seq value. That bridge is the
open design; until it is built and measured, the column abstains rather
than emit an obligation WP cannot state (SPEC.md's rule for a kernel that
cannot state a construct).

**The lifter** (LIFTER-DECISIONS rows 49 and 50). Row 49: a closure
function returning `string`, `seq<char>`, `seq<int>` or `seq<nat>` lifts to
a spec_fun with a `"seq"` result (`_is_seq_fun_result` in
t/lift_classify.py; `_lift_function` in t/lift_rewrite.py emits the result
and the rule `function-result-seq`), the string spellings as code points
exactly as a string parameter is (row 28), decision 6's totalising default
the empty seq, a `seq<nat>` result's element fact dropped and counted
(`nat-result-fact-dropped`). The check stage's `L_fun_F` lemma relates the
source function to the lifted spec_fun as before, a string result viewed
as its code points (`_src_result_text`, unchanged). Row 50, forced by the
measurement below: a `function F(..): bool` (a predicate spelled as a
function, Dafny Reference Manual 6.4.2) is admitted beside int/nat/char;
the rewrite already typed it bool, and the 2026-09-27 check that first
named `function-result` refused it by omission (66 of the 305 baseline
tokens). A nested-seq, tuple, set, datatype or real result still refuses
`function-result` by name. The Lean lifter (t/lift_lean.py) has nothing
to change for this feature: it lifts one program with no helper functions
(a call of another definition refuses `unknown-function`, a recursive one
`recursion`), and a `String`-returning program was already lifted as a seq
return (cloud feature 6).

**Fixtures.** The committed task `t/tasks/double_all.t` (`dbl(s, n)` is the
first `n` elements doubled; the loop appends `2 * s[i]` under `r == dbl(s,
i)`; `ensures r == dbl(s, len(s))` and `len(r) == len(s)`), and four probes
in t/fuzz_lower.py, `fz_p_sf_seq_len` (the result measured), `fz_p_sf_seq_at`
(indexed), `fz_p_sf_seq_build` (built in the body from a slice) and
`fz_p_sf_seq_false` (a false ensures through the recursive spec_fun,
expected refuted, adversarial), each with the twin the ladder draws; and,
since the review ("The review and the seeded faults" below), two more
that plant the fault in the spec_fun's own body, `fz_p_sf_seq_swap`
(double_all's loop under a `dbl` that prepends) and `fz_p_sf_seq_slice_off`
(seq_build under a `tl` that drops the last element), both adversarial,
expected refuted. The conformance suite reads probes from
`fuzz_lower.probes()` directly; the committed t/CONFORMANCE.md is the
record of a full run and was not regenerated here (the probes are graded
below by t/run_par.py, the same cell machinery).

**Tests.** t/test_seq_spec_fun.py (the language side: notation round
trip, check_wf, the interpreter, the twin ladder, six lowerings plus the
named abstain, every committed task still lowering; since the review, the
dafny and F* certificate rungs on the two seeded-fault probes as text,
and with `--slow` the two kernels' own `refuted`) and
t/test_lift_seq_fun.py (the lifter: a string helper, a recursive seq
helper totalised with the empty seq, a result indexed/measured/sliced/
compared, a `seq<nat>` result's dropped fact, a bool function, nested and
tuple results still refused; `--slow` runs the check stage under dafny).
t/test_wf_errors.py's UNREACHABLE table names the new rule.

## Byte identity

For every committed task under t/tasks, t/lemmas and t/nested, real and
twin, in all seven kernels: sha256 of `tlib.lower(task, kernel,
twin_body)` (a named abstain or a task with no twin hashes its exception
text) on a clean `git archive r12-blockers` export and on the branch.
**546 of 546 entries identical** (`hashes_base2.json` against
`hashes_branch5.json`, the branch's final hashing after the last lowering
edit; `hashes_branch2` to `4` after each earlier one read the same); the branch has 14 more, double_all's own seven kernels times real
and twin. Every code path this feature adds is gated on a spec_fun whose
result is `"seq"` (`_has_seq_sf`, `sf["result"] == "seq"`), which no task
before double_all declares.

After the review's fix (the certificate rungs, "The review and the seeded
faults" below), hashed again with the same script on a fresh `git archive
r12-blockers` export: **546 of 546 identical** (`fix/hashes_base.json`
against `fix/hashes_fix.json`), and **560 of 560 identical** against the
branch as reviewed, 4cb7e5b4 (`fix/hashes_reviewed.json`): the fix changes
no committed lowering, double_all's own twin included, since its witness
is the undefined-kind one at `s = []` whose formula reaches no spec_fun
call, and the rungs are emitted only for a certificate that reaches a
seq-valued one. t/AGREEMENT.md's matrix therefore stands as regraded
below.

## The fixtures in seven kernels

Graded on the desktop with t/run_par.py (all seven kernels installed
under the user's own prefixes; the lab was unreachable through the VPN
for the whole session, so nothing below ran there), the committed task
from `tasks_fix/` and the four probes as task JSON from `probes_fix/`.
Cell = real / twin.

| task | expected | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|---|
| double_all | verified | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| fz_p_sf_seq_len | verified | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| fz_p_sf_seq_at | verified | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| fz_p_sf_seq_build | verified | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| fz_p_sf_seq_false | refuted (no twin) | refuted | refuted | refuted | abstain | refuted | refuted | refuted |
| fz_p_sf_seq_swap | refuted | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| fz_p_sf_seq_slice_off | refuted | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |

Runs: `fix7.md` (double_all, six kernels, 2026-09-27 18:45Z), `probes7.md`
(the four probes, six kernels), `rocq6.md` and `rocq7.md` (the Rocq
column after its two fixes below; `fix7`/`probes7` carried Rocq's earlier
verdicts, next paragraph), `false_real2/` (the adversarial probe's real
side through the conformance suite's own no-twin path: lowered with the
interpreter's real witness, `harness.real_witness`, then `flake_check`
over each kernel's `verify`; without that witness, `false_real/`, the six
kernels read unproved or timeout, no proof and no false verdict, which is
the honest half of the same answer). Frama-C's cell is the named abstain on all five.
The twin of every witnessed fixture is refuted by every kernel that
states the construct, six of six. The last two rows are the review's
seeded faults as probes, graded after the fix below: `fix/probes8.md`
(the six probes, seven kernels, 2026-09-27 20:29Z, 30 cells, 180 kernel
runs, no cache; the four earlier probes read as before, and double_all
alone the same in `fix/fix8.md`, 6 cells, 36 kernel runs). Their real
side is the refutation the probe exists for; their twin (`compare-flip`
on the loop guard, `off-by-one` on the slice) is refuted as any twin is.
The single-cell `refuted` in the expected column is `fix/seeded/`, the
no-twin path with the interpreter's real witness (next section).

Rocq took two measured fixes to get there, both gated on a seq-valued
spec_fun being present. As first built (the pair representation alone),
`fix7`/`probes7` read double_all `timeout / refuted`, fz_p_sf_seq_at and
fz_p_sf_seq_build `unproved / refuted`, fz_p_sf_seq_len `verified /
unproved`. (1) The unfolding rewrite `sf_f_eq` leaves a literal `(fn,
len)` under `fst`/`snd`; `t_eqs`/`t_eqs_h` now follow it with `cbn [fst
snd]`, which closed seq_at and seq_build. (2) A seq-valued spec_fun with
one int argument gets the argument normalisation (`ring_simplify`) the
file already gives a single-int-param spec_fun: the loop's forward step
lands on `sf_dbl s s_len (i + 1 - 1)`, never the invariant's `sf_dbl s
s_len i`; `double_all_loop_spec` ran past 900 s before and 1.8 s after
(hand-timed on the lowered file, then `rocq6.md`). (3) The refutation
certificate grounds every spec_fun call at the witness by `cbv;
reflexivity`; a seq-valued call has no literal for `_glit`, so it raised,
`_try_cert_v1` swallowed the error and emitted no certificate (the cell
honestly read unproved); it now asserts the length (`snd`) and each
element (`fst .. j`), which refuted seq_len's twin (`rocq7.md`).

## The review and the seeded faults

The 2026-09-27 review of this branch seeded three faults into a
seq-valued spec_fun's own body, a shape none of the four probes above
plants (each of theirs is on the task side, one unfolding from the base
case), and ran each through every kernel by the no-twin path: (1) `tl`
dropping the last element instead of the first (`slice(s, 0, len(s) - 1)`
in fz_p_sf_seq_build's spec_fun), (2) `dbl` dropping the appended element
(`dbl(s, n - 1)` alone in the else branch), (3) `dbl` prepending it
(`[2 * s[n - 1]] + dbl(s, n - 1)`). Verus, SPARK, Lean and Rocq refuted
all three; dafny and F* refuted (2) and read (1) and (3) **unproved**,
not refuted and not verified. Reproduced here first, on the reviewer's
own generated sources (`seqfun_review/seeded_faults/`): dafny 4.11.0 exit
4 on the certificate lemma, F* 2026.08.30 Error 19 "unknown because
(incomplete quantifiers)" up to fuel 8, both in 2 s. The finding is
real, and its cause is in the certificate, not in the lowering of the
construct.

**Two causes.** The twin certificate (lower_dafny.py's section comment
above `CERT_NAME`; lower_fstar.py's above its own) states the measured
witness as a ground lemma the kernel must accept. Dafny's carries an
assert ladder for every spec_fun call the formula reaches, `assert
f(args) == v;`, callees before callers, because the kernel unfolds a
recursive function only to its default fuel; that ladder skipped a
seq-valued fact (`if isinstance(v, list): continue`, a line dead before
this branch, since no spec_fun returned a seq), so `dbl([0, 1], 2)`
needed two unfoldings the kernel did not make. F* carries no ladder: its
`assert_norm` evaluates the formula by normalisation, which decides an
int-valued recursive call outright but cannot evaluate a seq-valued one
(`Seq.seq` is `new val`, abstract, in FStar.Seq.Base.fsti), so the
residual goes to Z3, whose only index and length facts are the SMTPat'd
lemmas (`lemma_index_app1`/`app2`, `lemma_index_create`,
`lemma_index_slice`, `lemma_len_*`), triggered by index terms the goal
never contains. That is cause one, the recursion. Cause two showed on the
slice fault, which needs no recursion at all: once `tl([0, 1])` is
grounded to `[0]`, what is left is `[1, 0] != [0] + [0]`, and neither
kernel proves that either. Probe `T1`, a Dafny lemma with nothing but
`ensures [1, 0] != [0] + [0]` and no spec_fun in the file, exits 4 on
4.11.0 (`fix/hand/T1.dfy`); a display is a `Seq#Build` chain with an
injectivity axiom, an append of two displays is not, and nothing relates
the two without an index term to trigger on. Asserting the append's
value as a display first (`T4`, `T6`) proves it; the same shape in F*
(`fix/hand/sliceV5-V7.fst`) reads refuted with the rung and unproved
without.

**The fix** (commit "the dafny and F* certificates ladder seq-valued
spec_fun calls and the ground seq operators around them"). lower_dafny.py's
ladder states a seq-valued fact with its result bound to a fresh
`seq<int>` local in the lemma body (`var t_v0: seq<int> := [];` then
`assert dbl(s, 0) == t_v0;`, since an inline literal is
type-underspecified), and, once a certificate grounds such a call, every
seq-typed ground operator subterm of the formula, innermost first
(`_seq_op_rungs`: `assert (tl(s) + [s[0]]) == t_v1;`). `seq_ladder` hands
the same rungs to lower_fstar.py, which asserts each as `Seq.equal
<term> <literal>` ahead of the `assert_norm`, so `lemma_eq_elim` and the
index lemmas have their terms. The rungs are hints: the kernel re-proves
every one, so a wrong rung loses the certificate and never fakes it, and
verifiers/dafny.py's shape rule (one `lemma t_refutation_certificate()`,
one ensures, no requires) and verifiers/fstar.py's targeted
`--admit_except` run are untouched. A certificate whose formula reaches
no seq-valued call gets no rung, which is every committed task's
(double_all's own twin is the undefined-kind witness at `s = []`, whose
formula has no call), hence the byte identity above. The two seeded
faults are committed as adversarial probes, `fz_p_sf_seq_swap` and
`fz_p_sf_seq_slice_off`, expected refuted.

**Measured** (`fix/seeded/`, 2026-09-27 20:28Z, the desktop; the lab was
unreachable for this session too): the reviewer's three seeded tasks and
the two probes, real side with `harness.real_witness`, `flake_check` n=3
over each kernel's `verify`:

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| seed_offbyone_slice_v2 (1) | refuted | refuted | refuted | abstain | refuted | refuted | refuted |
| seed_dropped_element (2) | refuted | refuted | refuted | abstain | refuted | refuted | refuted |
| seed_swapped_concat (3) | refuted | refuted | refuted | abstain | refuted | refuted | refuted |
| fz_p_sf_seq_swap | refuted | refuted | refuted | abstain | refuted | refuted | refuted |
| fz_p_sf_seq_slice_off | refuted | refuted | refuted | abstain | refuted | refuted | refuted |
| fz_p_sf_seq_false | refuted | refuted | refuted | abstain | refuted | refuted | refuted |

Every cell 3 of 3 agreed; dafny and F* under 3 s each, SPARK 19 to 27 s.
The four earlier probes and double_all, regraded by t/run_par.py after
the fix, read exactly as in the table above (`fix/probes8.md`,
`fix/fix8.md`).

**On the corpus.** The fix can only change a twin cell in the dafny and
F* columns, and only for a task whose certificate reaches a seq-valued
call, so the 55 checked tasks were regraded in those two columns alone
(`fix/grade_df.md`, 2026-09-27, 80 cells, 480 kernel runs, no cache)
against `COVERAGE-seqfun.md` (the 19:34Z grading): 6 twin cells moved
from `verified / unproved` to `verified / refuted`, one in dafny
(`vericoding_da0000__solve`, its certificate now laddering
`intToDigits(1)` through its helper) and five in F* (`da0526`, `da0561`,
`da0564`, `da0576`, `da0663`, each a string helper grounded by one
`Seq.equal` rung); dafny 29 to 30 and F* 18 to 22 tasks verified /
refuted of the 55. One real-side F* cell, `vericoding_da0453__solve`,
read timeout in the regrade where the 19:34Z run read verified; its
source is byte-identical to that run's (the fix does not touch a real
side) and re-verified alone three times it reads verified, 3 of 3 agreed, 50 s each: a load timeout, the regrade having shared the desktop with the CI step, the probe matrix and an unrelated SPARK job. The lift measurement itself (the 1,886-file
tally, the check stage) is untouched by the fix, which changes neither
the lifter nor the check stage, so its counts above stand as measured.

**The review's second finding**, that its own reproduction of the corpus
measurement covered about 570 of the 1,886 files in its budget, is a
coverage note on the review, not a discrepancy: the partial counts it
reports agree in direction, magnitude and refusal-reason names with the
full run above, and nothing in this fix touches the lifter, so the full
run was not repeated here.

**Left, and why.** Cause two is older than this branch: a certificate
whose formula compares a literal against a ground `+` (or slice, update,
fill, string member) of literals, with no spec_fun anywhere, is unproved
in dafny and F* today (`T1`). Closing it for every certificate is the
same rung emitted unconditionally, which changes the text of committed
twins and so waits for a branch that regrades the committed matrix on
purpose; here it is gated on a seq-valued fact.

## The measurement on the staged corpus

The 1,886 staged Dafny files of the 2026-09-26 lift
(`t/out/lifted-tasks-2026-09-26.meta/staged`, copied to `scratch/seqfun/
staged`), lifted without the check stage on `r12-blockers` (`base/`) and on
the branch (`new2/`), 8 jobs, then the check stage on the desktop over the
files whose methods newly lift, then the seven-kernel grading of the
checked tasks. Counts are methods unless a file is named; the tally script
reads each `<stem>.outcome.json` (`measure.py`, `summarize_check.py`, in
the reproduce section).

| stage | count | run |
|---|---:|---|
| methods in the 1,886 files | 1,884 | base/ |
| refused `function-result` before | 305 | base/ |
| of which the result type is `string` / `bool` / `real` / `seq<string>` / `seq<int>` / `seq<char>` / `seq<nat>` / other | 86 / 66 / 58 / 31 / 25 / 5 / 2 / 32 | base/ |
| refused `function-result` after | 139 | new2/ |
| pass the gate (no longer `function-result`) | 166 | new2/ |
| lift at the rewrite stage (of the 305) | 104, in 101 files | new2/ |
| refused later by another name (of the 305) | 62 | new2/ |
| lifted in total, before / after | 850 / 955 | base/, new2/ |
| lifted before and not after | 0 | base/, new2/ |
| of the 104: by row 49 (a seq-valued helper) / row 50 (a bool function only) | 72 / 32 | checked/ (the record's rewrites) |
| checked (of the 104, check stage, dafny, 120 s, 409 s wall for the 101 files) | 55 (35 with a seq-valued spec_fun, 20 bool-only) | checked/ |
| check-stage refusals by name | 47 `lift-check-failed` (35 of row 49, 12 of row 50), 2 `check-wf-failed` (row 49: a `multiset` call, an unbound local) | checked/ |
| graded in seven kernels (the 55 checked tasks; `COVERAGE-seqfun.md`, 2026-09-27 19:34Z, 1,326 kernel runs) | 55 | grade/ |
| clean in seven (verified / refuted in every column) | 0 | grade/ |
| clean in six (framac the one column short, its named abstain) | 2 (`vericoding_da0230__solve`, a seq-valued helper; `vericoding_da0558__solve`, a bool function) | grade/ |
| verified / refuted, per kernel, of the 55 | dafny 29, spark 27, verus 26, lean 18, fstar 18, rocq 5, framac 0 | grade/ |
| no twin (the ladder found nothing to mutate; graded on neither side by run_par) | 12 | grade/ |

The 62 that pass the gate and refuse later, by name (new2/): 12
`nested-seq-other`, 6 `unbounded-quantifier`, 6 `set`, 4 `as-cast`, 4
`seq-typing`, 3 `char-arith`, 3 `datatype`, 3 `ghost-local`, 3
`string-lib`, 2 `lexicographic-decreases`, 2 `char-cast-unbounded`, 2
`array`, 2 `callee-refused:return-not-assigned-on-all-paths`, 2
`seq-update`, and one each of `seq-slice`, `tuple-arity`,
`callee-refused:seq-typing`, `callee-refused:seq-update`,
`bodyless-function`, plus one method the baseline refused
`callee-refused:function-result` that now lifts.

What still refuses `function-result`, by result type (new2/, 139): 45
`seq<string>` (a nested-seq result, not in v1), 16 `real` and 6
`seq<real>` (no reals in t), 7 `set<int>` and the other set spellings
(feature 9 of the track), 3 tuples (a pair result is not in v1), 3 `bv`,
3 type synonyms, 2 `seq<id>`, 1 `seq<seq<int>>`, 1 `seq<bool>`, 1
`multiset<int>`, and the rest under a second function of the same
closure whose result is one of these. The token names the first offending
function of the closure, so a method whose closure has both a string
helper and a real one is counted under whichever the scan meets first.

The seven-kernel grading of the 55 checked tasks, by cell (`grade/`,
`COVERAGE-seqfun.md`; the abstain reasons were re-derived by lowering each
task in each kernel without a prover, `abstain_reasons.py`, since the run
log kept only the table). Frama-C abstains by name on the 32 tasks whose
seq-valued spec_fun it reaches (three more of the 35 abstain earlier, on a
nested-seq return or a quantifier in term position), and on 14 bool-only
tasks for a quantifier in ACSL term position; it verifies none of the 55.
Rocq abstains on 22 for a quantifier in computational position and on 3
for a loop under a conditional, reads unproved / refuted on 6 and
timeout / refuted on 2, and verified / refuted on 5. Lean abstains on 11
for a bounded quantifier in computational position and reads unproved on
both sides of 8. F* abstains on 4 (a loop under a conditional, a `return`
in a multi-loop body) and crashes its lowering on 2 (`TypeError:
unhashable dict`, a pre-existing gap the tally names), reads unproved /
refuted on 8. Dafny, Verus and SPARK read verified / refuted on 29, 26
and 27; SPARK's 8 timeouts are all on the real side of a task the other
two verify. Twelve tasks have no twin (the ladder found nothing to
mutate), so they are graded on neither side here.

Malformed cells, all read by hand: F* on 4 tasks (`Identifier not found:
j` / `k_v` inside a bounded quantifier's own helper `t_forall_at`, a
quantifier bound reaching an outer binder; two of the four are bool-only
tasks, so this is F*'s quantifier lowering, not the seq result); Rocq on 2
seq-valued tasks (`sf_repeatString_fuel_irrel`: the lifter's totalised
`decreases`, `if n <= 0 then 0 else n`, spliced under `( .. < fuel)%nat`
has its literals read in nat scope, "The term n has type Z while it is
expected to have type nat"; fixed after this grading by restating an
`ite` measure in Z scope, gated on the `ite`, so every committed task's
text is unchanged, `hashes_branch6.json` 546 of 546). Re-lowered and
compiled by hand (`rocq_fix/`): `Multiply` now reads unproved, its
`sf_repeatString_fuel_irrel` lemma's `lia` not seeing through the `if`
in the measure (an honest no-proof where a malformed file was);
`concatenate` hits the next gap, a spec_fun whose parameter is a NESTED
seq (`strings_v : seq<seq>`) gets a binder with no `_len` companion
("The reference strings_v_len was not found"), which is the nested
parameter's own gap in `emit_spec_funs`, reachable by an int-valued
spec_fun over a nested seq exactly the same way, and left as found.
Verus on 3 and SPARK on 2 were not read here (the same tasks refuse
elsewhere; named in the table).

None of the 55 is clean in seven. That is the check stage's and the
kernels' existing gaps meeting the string programs this feature admits,
not the construct failing: the fixtures above are clean in six with
Frama-C's named abstain, and the two lifted tasks that reach six do so
the same way.

## What is left and why

- **Frama-C**: the `\list` route, above. Effort: the bridge predicate and
  its use at every seq site of a spec value; the buffer model stays.
- **The check stage's `L_fun` lemmas** (47 of the 104): the token names
  the lemma that did not prove, and 41 of the 47 are the helper's own
  `L_fun_<name>` equivalence (seven of them one recursive `str2Int` over
  a string's code points, then `isSubstring`, `validBitString`,
  `reverse`, `starts_with`, `innerDepthsPositive`, and one each of 20
  more); three are `L_ens` and three `L_inv_0`. These are the check
  stage's own gap, the same one rows 43 and 44 measured for their
  helpers: Dafny relates a recursive source function over `string` to
  the lifted spec_fun over its code-point view only with induction it
  does not find unaided. Not this feature's to close; the tasks are
  named in `checked/*.outcome.json`.
- **Nested-seq results** (`seq<string>`, 45 methods): the same feature one
  level up, a `{"seq": "seq"}` result; Lean's and Rocq's nested models
  (`t/DESIGN-lean-seq-composition.md`, `t/DESIGN-framac-nested-seq.md`)
  set the cost.
- **Reals, sets, tuples, bitvectors** as results: each is its own feature
  of the track (sets are feature 9 there), not a spec_fun question.
- **The committed matrix**: t/AGREEMENT.md is the record of every
  committed task in seven kernels and t/preflight.py fails while a task
  has no row, so double_all needs the whole matrix regraded with no
  cache (`t/run_par.py --table t/AGREEMENT.md`, run_par's own rule for
  the committed table). It was regraded on the desktop after the
  grading above (`matrix/`, 248 cells, 1,488 kernel runs, 2026-09-27
  19:46Z); the branch's last commit carries the table. Against the
  2026-09-25 lab regrade, two rows differ: double_all is new (six
  verified / refuted, Frama-C abstain / abstain), and min_max's Rocq cell
  reads verified / refuted where the lab read timeout / refuted (the
  desktop finished the proof inside the budget; nothing in this branch
  touches min_max's text, byte identity above). 32 of 36 tasks are clean
  in seven; of the 2 in six, both are Frama-C alone.
- **t/CONFORMANCE.md**: a full conformance run regenerates it with the
  four probes; the probes' cells are graded above by the same machinery.

## Tests run

- The CI step "t/ unit tests that need neither provers nor torch"
  (`.github/workflows/tests.yml`, the same ignore and deselect lists, run
  from `t/` with a python shim on PATH): 1,430 passed, 3 failed, 53
skipped, 25 deselected, 1 xfailed, 102 subtests passed, 229 s (the final
tree; the same step on the first tree read 1,428 passed, 4 failed, the
fourth being the `spec-fun-result` coverage row added since). The three
  `test_loop_train.py` failures are `ModuleNotFoundError: No module named
  'datasets'` on this machine, the same three before this branch; CI
  installs it.
- After the review's fix, the same step (`fix/ci_step2.log`): 1,432 passed, 3 failed, 53 skipped, 25 deselected, 1 xfailed, 102 subtests passed, 152 s; the three failures the same `datasets` ones.
  On the tree as reviewed it read 4 failed, 1,431 passed: the fourth was
  t/test_twin_hints.py's exemplar `min_max` for "a program with a
  timeout column is not a source", which the committed-matrix regrade
  (4cb7e5b4, min_max's Rocq cell verified / refuted on the desktop) had
  made a source; the test now names count_vowels, whose row still
  carries a timeout in spark and fstar (the rule under test unchanged).
- `python3 t/test_seq_spec_fun.py`: 7 tests, 560 lowerings of the
  committed tasks; `--slow` adds dafny's and F*'s own `refuted` on the two
  seeded-fault probes. `python3 t/test_lift_seq_fun.py --slow`: 6 tests plus the check stage on
  three of its programs under dafny (DropFirst, DoubleAll, MakeOnes: each
  checked, the differential harness agreeing on 47, 87 and 41 points).

## How to reproduce

```
# baseline and branch lift, no check stage (8 jobs, ~16 min each)
git checkout r12-blockers
python3 t/lifter.py --dir <staged> --out ~/scratch/seqfun/base --skip-check --jobs 8
git checkout feat/seq-spec-fun
python3 t/lifter.py --dir <staged> --out ~/scratch/seqfun/new2 --skip-check --jobs 8
# the tally, the newly lifting files, the still-refused tokens
python3 measure.py ~/scratch/seqfun/base ~/scratch/seqfun/new2
# the check stage over the newly lifting files (dafny on PATH, DOTNET_ROOT set)
python3 t/lifter.py --dir ~/scratch/seqfun/newly --out ~/scratch/seqfun/checked --jobs 4 --timeout 120
python3 summarize_check.py ~/scratch/seqfun/checked ~/scratch/seqfun/newly_lifted_methods.txt ~/scratch/seqfun/grade_tasks
# the seven-kernel grading of the checked tasks
T_SPARK_JOBS=1 python3 t/run_par.py --jobs 3 --tasks ~/scratch/seqfun/grade_tasks --out ~/scratch/seqfun/grade --table ~/scratch/seqfun/COVERAGE-seqfun.md
# the fixtures
T_SPARK_JOBS=1 python3 t/run_par.py --jobs 2 --tasks ~/scratch/seqfun/tasks_fix --out ~/scratch/seqfun/fix7 --table ~/scratch/seqfun/fix7.md
# byte identity: hash every committed task's lowering on both trees
git archive r12-blockers t | tar -x -C ~/scratch/seqfun/base_src
python3 hash_lowerings.py ~/scratch/seqfun/base_src/t hashes_base2.json
python3 hash_lowerings.py t hashes_branch5.json
# the review's seeded faults and the two probes, real side with the
# interpreter's witness, flake_check n=3 per kernel (fix/seeded/)
python3 seeded.py verify
# the corpus's 55 checked tasks in the two columns the fix touches
python3 t/run_par.py --jobs 3 --no-cache --kernels dafny,fstar --tasks ~/scratch/seqfun/grade_tasks --out ~/scratch/seqfun/fix/grade_df --table ~/scratch/seqfun/fix/grade_df.md
```

`seeded.py` lowers each task with `harness.real_witness` (the conformance
suite's own no-twin path) in every kernel and runs `verifiers.flake_check`
over each kernel's `verify` three times; it is the reviewer's own script
with the tree it imports changed.

`measure.py`, `summarize_check.py` and `hash_lowerings.py` are the tally
scripts described in the text: the first reads every `<stem>.outcome.json`
of two runs and counts methods by `refusal.reason`, writing the newly
lifting stems and methods to two text files; the second reads the check
stage's outcome files for those methods and copies each checked task into
the grading directory; the third hashes `tlib.lower` over
`t/{tasks,lemmas,nested}` for every kernel, real and twin.
