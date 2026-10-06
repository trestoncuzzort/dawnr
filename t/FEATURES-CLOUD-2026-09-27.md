# The cloud features track, 2026-09-27

The operator asked for the t features track (`t/FEATURES-TRACK.md`) to be
worked in order on a cloud machine, without stopping: install the seven
kernels without root, then grow the language and the lifter so that the
lifter (`t/lifter.py` and its front ends) stops refusing published verified
programs, one feature at a time, each measured on the public corpora. This
file is the record: what landed, the status of every kernel for every
feature, the Phase 2 counts, and what is left and why. Every count below
names the run that produced it; the runs live under the measuring machine's
`lift-runs/` directory (not committed) and the tally scripts are described
in the text.

Branch `cloud/fable-t-features`, from `r12-blockers`. Commits, in order:
2f8b460 (seq decreases), 7bdd7aa (quantifier bounds), dd62bdb (multi-return
calls), fec4de6 (arrays read by functions), 6ee8bfb (nested string
sequences), 7078b9a (Lean strings, `function-result`, a Dafny-lowering
fix), 9c9813c (tuples), 4aa93d3 (lemmas in Rocq), adaec5b (decision rows
39 to 44 and the track's Done entries), then this report.

## Phase 0: the seven kernels, and the conformance suite

All seven installed without root, as `t/RUN-ON-LINUX.md` records, with the
routes the machine's network allowed (GitHub release assets and the Nix
binary cache; the opam mirrors, the dotnet CDN and several release hosts
were blocked, so Frama-C, Alt-Ergo and Rocq came from Nix, the Rocq standard
library was built from its release tarball, and the Lean toolchain was
unpacked by hand under elan):

| kernel | version |
|---|---|
| dafny | 4.11.0 (fcb2042d) |
| verus | 0.2026.08.30.b432e82, rustc 1.97.1 |
| spark | gnatprove FSF 16.1.0, Why3 1.8.2, alt-ergo 2.6.1, cvc5 1.3.2, z3 4.15.4 |
| framac | Frama-C 33.0 (Arsenic), Alt-Ergo 2.4.3-free, Why3 1.8.2 |
| lean | 4.33.1 |
| rocq | 9.2, stdlib 9.2.0 |
| fstar | F* 2026.08.30 (OCaml 5.3.0) |

Two things about the machine matter for reading the counts. It has no
dotnet, so `dafny run` cannot compile and the lifter's differential arm
(the third arm of the check stage) reads `arm-unavailable` on every task
here: it is never a pass and never a refusal, and "checked" below means the
equivalence lemmas verified with the arm unavailable. And it has no systemd
user bus, so `T_PROVER_MEMCAP=0` is needed for any prover run.

`python3 t/conformance.py --jobs 3`: 66 tasks (53 probes, 13 metamorphic),
kernels present 7 of 7, tripwire bugs 0. The run, made while lifter jobs
shared the four cores at load 30, showed 6 FAIL cells: the two committed
Frama-C timeouts (`fz_p_biglen`, `fz_p_seqlen`, the same two
`t/CONFORMANCE.md` records) and four SPARK timeouts (`fz_p_ret_first`,
`fz_p_ret_falsens`, `fz_p_seqeq_false`, `fz_p_str_tab`). The four SPARK
cells re-run one at a time on the quiet machine (`verifiers.spark.verify`
on the run's own `.ads` files) read verified/refuted, refuted/refuted,
refuted/refuted, verified/refuted, exactly the committed table, so the
suite's outcome is the committed one: 2 FAIL cells, both Frama-C. The
seven-kernel walk-through (`AGREEMENT.md`'s procedure) agreed on every
task tried before any feature work began.

## What landed

Every feature was designed by copying an established construct and citing
it in its commit (Dafny first: its reference manual for decreases, method
calls with out-parameters, lemmas, strings and tuples; Gries and Schneider's
one-point rule; Lean core's String definitions; Amin, Leino and Rompf's
fuel-one unfolding for the Rocq lemma proofs). Soundness held as the task
required: no assume, admit, sorry or axiom anywhere; nothing discharges a
goal without a proof; the grader, the twin generator, the lift check filter
and the corpus gates are untouched. Every committed task, method, lemma and
conformance fixture lowers byte for byte as before in all seven kernels
(`sha256` of `tlib.lower` for 48 fixture tasks, real and twin, before and
after each feature), except the eight lemma fixtures' Rocq real sides,
which feature 5 changes on purpose.

Six of the seven features are lifter-only (no kernel changes: t already had
the construct). Per kernel, therefore, their status is that of the construct
they lift to, which every kernel already lowers: seq lengths, bounded
quantifiers, pairs, nested seqs, method calls. Feature 5 changes the Rocq
lowering alone.

| feature (task numbering) | track entry, decision row | what changed | kernels |
|---|---|---|---|
| 1 seq `decreases` on spec functions | Done 3, row 39 | lifter: `decreases s` lifts as `len(s)`; the check stage proves the order (length-ordered induction hint, slice bridges) | none |
| 2 arrays read by functions | Done 4, row 42 | lifter: a read-only array passed to a lemma or a read-only callee is no escape; lemmas take array params as seqs | none |
| 3 quantifier bounds | Done 5, row 40 | lifter: bounds through a predicate's body, a chain, a nat binder, the one-point rule; unbounded stays refused | none |
| 4 multi-return calls | Done 6, row 41 | lifter: `a, b := M(x)` binds the callee's pair, projects it | none |
| 5 lemmas in Rocq | Done 2 (rocq column) | Rocq lowering: a theorem per lemma, fuel induction for a recursive one, each call's instance posed and fed where the proof needs it; the refutation certificate unchanged | rocq (the other six unchanged) |
| 6 strings: nested string sequences; Lean front end | Done 7, row 43 | lifter: `seq<string>` as a nested seq of code-point rows, row kinds, checker views, nested points; `function-result` refusal; Lean reader: String/Char and their core operations | none |
| 7 tuples | Done 8, row 44 | lifter: a two-component tuple is t's pair (return, param, local, literal, projections) | none |
| 8 in-place array / `&mut Vec` writes | first shape only; survey below | lifter: a mutated array read by a closure predicate is no alias (decision 22's `aliased`); the check stage's own re-derivation of the mutated shape now sees lemma calls | none |
| 9 finite sets, datatypes | not started | | |

Tests, all without a prover unless `--slow`: `t/test_lift_seq_decreases.py`
(4, plus 2 slow), `t/test_lift_array_functions.py` (5, plus 3 slow),
`t/test_lift_quant_bounds.py` (7, plus 6 slow fixtures),
`t/test_lift_multi_return_calls.py` (4, plus 3 slow),
`t/test_lift_nested_strings.py` (7, plus 4 slow), `t/test_lift_tuples.py`
(5, plus 4 slow), `t/test_lemmas.py` (16; the Rocq case now asserts the
stated lemma, the posed instance, the unchanged twin certificate, an
untouched lemma-less task; the no-axiom test covers lower_rocq),
`t/test_lift_lean.py` (29). Every slow fixture passed the check stage under
dafny on this machine (equivalence lemmas verified, differential arm
unavailable). The lifter and lowering suites (`test_lift_rules.py`,
`test_lift_check.py`, `test_lift_lemmas.py`, `test_lower_rocq.py`,
`test_names.py`, `test_methods.py`): 217 passed, 11 skipped, and the same
two failures as before any change (`test_seed_acceptance`, `test_infragment`,
both needing a corpus directory this machine does not have). The whole
suite (`pytest t --ignore=t/test_lab_gui.py`, which needs tkinter), run
before any change and again after the last one: 1396 passed, 51 failed,
28 skipped after; the 51 are a subset of the 52 that failed before (every
one needs a corpus directory, a lab machine, a training run or a split
this machine does not have), no test newly fails, and the one that
stopped failing (`test_cli`'s abstain case) did so because a kernel it
runs was installed in between.

Seeded-fault tests per kernel, for the one kernel change: the five
`t/lemmas_probe/` programs (a false inductive lemma, a false nonlinear fact,
a circular induction, a false `assert` step, a false nonlinear step under a
guard) all read unproved in Rocq 9.2, never verified and never a timeout
counted as success; the three `t/lemmas/` fixtures read verified with their
twins refuted (two of them, `pow2_pos` and `sum_loop`, read unproved before).

## Phase 2: the corpora, per feature

The 2026-09-26 lift (`t/LIFT-2026-09-26.md`, 1886 staged Dafny files of
HumanEval-Dafny and vericoding-benchmark, resolved with dafny 4.11) was
re-run on this machine with the check stage skipped, to get the baseline
per-method refusals with the same lifter (`lift-runs/base-skipcheck`:
2068 methods, 867 lifted). For each feature, the files whose methods the
baseline refused for that feature's reason were re-lifted with the new
code, first with the check stage skipped, then with it on for the methods
that lifted. "Pass the gate" counts methods no longer refused for that
reason (they may refuse later, by another name); "lift" counts methods
that reach a t task; "checked" counts tasks the check stage kept
(equivalence lemmas verified; the differential arm unavailable here).

| feature | refused (baseline) | pass the gate | lift | checked | what still refuses |
|---|---:|---:|---:|---:|---|
| 1 seq decreases | 93 methods whose task failed check_wf on `decreases is not int` | 93 | 93 | 24 | 47 equivalence lemmas unproved, 18 check-wf-failed (string-returning helpers, since `function-result`), 3 differential timeouts (dotnet), 1 error |
| 2 arrays read by functions | 88 `array` | 21 | 14 | 12 | 67 `array` (element types char/real/bool/bv32/generic/array, array results, the in-place sorts), 1 check-wf, 1 lift-check |
| 3 quantifier bounds | 88 `unbounded-quantifier` | 50 | 24 | 10 | 38 still unbounded, 11 equivalence lemmas unproved, 3 check-wf, 2 `seq-return` |
| 4 multi-return calls | 5 `method-call-multi-return` (+12 `multi-return-nested`) | 5 | 0 | 0 | each callee refused on its own (`seq-typing` 2, `return-not-assigned-on-all-paths` 2, `seq-update` 1); the 12 nested ones have array/real/char/datatype components |
| 6 nested string sequences | 79 `nested-seq-string` | 37 | 37 | 3 | 25 `function-result` (a string-returning helper), 5 lift-check, 3 check-wf (`multiset`, an empty ensures), 1 differential timeout; 42 other refusals by name at the rewrite stage |
| 6 Lean strings | 119 Lean files `string`/`char` (of 626 vericoded Lean files) | 33 render | 18 | 0 proved equivalent | 10 `function-result`, 5 `unbounded-quantifier`; the Lean harness stops at `grind` on the code-point range clause (below) |
| 7 tuples | 27 `tuple` | 10 | 10 | 7 | 8 `function-result` (a tuple-returning helper), 2 check-wf, 1 lift-check, 6 other |

Feature 5's measurement is different in kind: the kernel changed, so the
question is what Rocq now verifies. The 181 lemma-carrying tasks of the
baseline lift lower through the new path as follows: 90 stated (their
lemmas proved in the file and posed), 7 stripped (a body shape with no
site), 69 abstain on a quantifier in computational position and 9 on a
loop under a conditional (both pre-existing Rocq refusals, unrelated), 5
raise on a seq in int position inside a spec_fun (pre-existing, the same
five raise without lemmas). The 90 stated tasks were verified with rocq 9.2
twice, without their lemmas (the lowering before this feature) and with
them:

| without lemmas -> with lemmas | tasks |
|---|---:|
| unproved -> unproved | 33 |
| verified -> verified | 23 |
| malformed -> malformed | 12 |
| unproved -> verified | 6 |
| timeout -> timeout | 5 |
| timeout -> unproved | 2 |
| malformed -> unproved | 2 |
| unproved -> timeout | 2 |
| verified -> unproved | 2 |
| verified -> timeout | 1 |
| timeout -> verified | 1 |
| unproved -> malformed | 1 |

90 tasks: verified without lemmas 26, with lemmas 30; gained 7 (DA0101, DA0113, DA0123, DA0157, DA0368, DA0585, DJ0118), lost 3 (DA0429, DA0472, DA0476); the rest unchanged (23 verified both ways). The one timeout among the losses (DA0429) reproduces on the quiet machine (180 s with the lemmas posed, 25 s without): the posed instances slow the proof search past the cap. The two other losses are lemma proofs whose steps Rocq's automation cannot close (DA0472's `ceilDiv` monotonicity, a division fact lia cannot reach; DA0476 likewise), so per SPEC.md the whole file reads unproved. Net: 26 verified without lemmas, 30 with; 7 gained, 3 lost, 23 verified either way.

## What is left, and why

**Strings, the binding gap: a spec_fun that returns a sequence.** A t
spec_fun's result is int or bool (SPEC.md). Every string program with a
helper function returning a string, or a sequence, stops there: 135
methods of the 2026-09-26 lift failed check_wf on it, 25 of the 37
nested-string lifts and 8 of the 17 tuple refusals hit it, 10 of the 33
rendered Lean-string files too. It now refuses by name, `function-result`,
at the stage that decides it. Lifting it needs seq-valued spec_funs in the
language and all seven lowerings (Rocq's fuel fixpoints return `Z` or
`bool`; the others are similar); that is a feature of the same size as
pairs were.

**Lean strings: one fact away.** The Lean equivalence harness
(`t/lift_check_lean.py`) views a `String` as its list of code points and
proves nothing yet because the lifted requires carries the code-point range
clause the Dafny lifter adds for its differential harness
(`string-elements-requires`), and the fixed tactic cascade does not prove it
over the mapped list's `!` index. A standalone probe proved the char bound
(`(c.toNat : Int) <= 1114111` from `Char.valid`, in four lines) and the
length half (`String.length_toList`, `List.length_map`); `grind` did not
connect the two through `List.getElem!` on a `List.map`. Either that lemma
in the cascade, or dropping the clause on the Lean track (which never runs
`dafny run`), should turn the 18 lifted files into proved equivalences.

**Feature 8, in-place writes: the first Dafny shape landed, the rest is
measured.** The Dafny half is decision 22's `modifies`-parameter shape,
already lifted; what stayed refused was `aliased`, the mutated array
passed to a predicate in an invariant (`IsSorted(a, 0, i)`), 11 methods,
all sorts. Passing a mutated array to a pure function is not an escape
(the function reads the value at the point of evaluation, which the
threaded seq is), and the exemption landed (`_array_passed_to_call`); but
9 of the 11 state their permutation spec with `multiset(a[..])`, which t
has no word for, and the two that do not (`insertionSort` of DD0274,
`sorting` of DD0276) lift and then fail the check stage on the predicate's
own equivalence over the mutated array (`L_inv_0`, `L_fun_insertionSorted`
unproved: the checker relates the source's array-reading predicate to the
lifted seq-reading spec_fun for read-only arrays, not yet for the threaded
mutated one). A fixture for this shape also caught a real bug in the
check stage: it re-derived decision 22's shape without the module, so a
lemma call still counted as an alias there and the checker typed the
synthesised return `int` ("size operator expects a collection"); the alias
checks now read lemma names from the closure too, and the fixture passes.
The Verus half: 68 vericoded
Verus files take a `&mut Vec` or `&mut [..]` parameter (`lift_verus.py`
refuses `mut-ref-param`); their specs read `old(v).len()`, `old(v)[i]`,
`v[i]`, `v@.len()`, and their bodies use `.set` (23 occurrences), `.push`
(18), `.clear` (11), `.truncate`/`.pop` (2 each). Rendering such a parameter
as a Dafny `array<int>` with `modifies` covers the `.set`-only files
through decision 22; the length-changing ones need a seq-valued out
parameter instead. The Verus equivalence harness would then have to state
the source's `old(v)`/`v` as two sequence values, which it does not do today.

**Feature 9, sets and datatypes, not started.** The plan for them is in
`t/FEATURES-TRACK.md` ("The features ahead"); the `multiset` gap above adds
multisets to the set question.

**Checker gaps the measurements found**, each named at its site: an inner
loop's invariant lemma does not carry the outer loop's guard, so an
`nums[i]` in it reads "index out of range" (a nested-loop fixture for
tuples; the fixture was replaced, the gap left as measured); an `exists n:
nat :: n <= |s| && ..` reads unproved against its bounded form in two
quantifier tasks whose own sum lemma was also dropped
`lemma-dropped-unproved`; check_wf types an empty display `[]` flat where
the other branch of an `ite` is nested (`ite branches differ: seq vs
{"seq": "seq"}`, 7 of the nested-string check failures); a Dafny `multiset`
still reaches check_wf as an unknown function in two files.

**Rocq lemmas, the honest cost.** SPEC.md says a kernel that states a lemma
must prove every lemma in the file or the file reads unproved. Some lifted
lemma proofs lean on facts Rocq's automation does not have (DA0472's
`ceilDiv` monotonicity step, `(a + b - 1) / b >= a / b`, a division fact
lia cannot reach), so a task that verified without its lemma can read
unproved with it. The table above counts both directions. SPARK's
alternative, leaving an unprovable step out, is spec-legal for a kernel
that cannot place a cut; Rocq can, so the strict reading was kept and the
trade-off is reported rather than hidden.

## How to reproduce

    export PATH="$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$HOME/.local/fstar/fstar/bin:$HOME/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin:$HOME/.local/verus/verus-x86-linux:$PATH"
    export T_PROVER_MEMCAP=0
    python3 t/conformance.py --jobs 3 --out CONFORMANCE.md
    python3 t/test_lift_seq_decreases.py --slow; python3 t/test_lift_array_functions.py --slow
    python3 t/test_lift_quant_bounds.py --slow; python3 t/test_lift_multi_return_calls.py --slow
    python3 t/test_lift_nested_strings.py --slow; python3 t/test_lift_tuples.py --slow
    python3 t/lower_rocq.py t/lemmas/pow2_pos.t t/lemmas/sq_bound.t t/lemmas/sum_loop.t
    for p in t/lemmas_probe/*.t; do python3 t/lower_rocq.py $p; done
    python3 t/lifter.py --list <files> --corpus-dir / --out <dir> --force --jobs 2 [--skip-check]

The per-feature file lists are the baseline run's refusals by reason
(`<method>.outcome.json`, `refusal.reason`), joined by source file and
method name with the re-lift's outcomes.
