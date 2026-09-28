# The cloud features track, round 2, 2026-09-27

The operator asked for a second round of the t features track on the same
cloud machine, without stopping: confirm the seven kernels still give the
committed conformance table, then work the round-2 list in order (the four
refusal buckets the round-1 census left and finite sets), each measured on
the staged corpora the way round 1 measured (baseline refusals by reason,
then pass-the-gate / lift / checked), with a decision row, a Done entry and
tests per feature; and, outranking the features, grade the 2026-09-27
features re-lift in all seven kernels once its data branch appeared. This
file is the record, in the shape of round 1's `t/FEATURES-CLOUD-2026-09-27.md`.
Every count names the run that produced it; the runs live under the
measuring machine's `lift-runs/` directory (not committed).

Branch `cloud/features-r2`, from `r12-blockers` (1b3c4cc). Commits, in
order: a4322ab (the return default, feature B2), aa78327 (sequence elements
named, B1), 8083e2a (zero-return methods named, B3, with decision rows 46
and 47 and Done 9 and 10), a9a4426 (merge of `cloud/features-r2-sets`:
66f8e4c the set type, core and three lowerings, bf9d70b the Rocq lowering,
the two committed tasks and Done 11), a22a1ad (decision row 45 and Done 12),
then the grading table and this report.

## Phase 0: the committed conformance table still holds

`python3 t/conformance.py --jobs 3` on the merged base before any change:
66 tasks (53 probes, 13 metamorphic), kernels present 7 of 7, tripwire bugs
0. The run shared the four cores with a lifter census (load 25 to 34) and
showed 10 FAIL cells: the two committed Frama-C timeouts (`fz_p_biglen`,
`fz_p_seqlen`, the same two `t/CONFORMANCE.md` records) and eight SPARK
real-side timeouts (`fz_p_ret_first`, `fz_p_ret_falsens`,
`fz_p_seqeq_false`, `fz_p_nest_cell`, `fz_p_nest_rowlen`, `fz_p_nest_lit`,
`fz_p_nest_eq`, `fz_p_str_tab`). The eight SPARK cells re-run one at a time
on the quieter machine (`verifiers.spark.verify` on the run's own `.ads`
files) read verified, refuted, refuted, verified, verified, verified,
verified, verified, in 21 to 70 s each: exactly the committed table. So the
suite's outcome is the committed one, 2 FAIL cells, both Frama-C, and the
SPARK timeouts were load, as round 1 found. Kernel versions are round 1's
(dafny 4.11.0, verus 0.2026.08.30, gnatprove 16.1.0, Frama-C 33.0, lean
4.33.1, rocq 9.2, F* 2026.08.30); the machine still has no dotnet, so the
lifter's differential arm reads `arm-unavailable` throughout and "checked"
below means the equivalence lemmas verified with that arm unavailable.

## The census the round started from

The 1886 staged Dafny files of the 2026-09-26 lift, re-lifted on this
machine with the MERGED lifter (`r12-blockers` after round 1) and the check
stage skipped (`lift-runs/r2-base0-skipcheck`, 2404 s wall at 4 jobs):
2068 gradable methods, 850 lifted. The refusals the operator's list named,
and the ones above them:

| reason | methods |
|---|---:|
| `function-result` (a seq-returning helper function; being built elsewhere, not touched here) | 305 |
| `nested-seq-other` (B1) | 113 |
| `parse:higher-order` | 91 |
| `set` (B4) | 77 |
| `datatype` | 73 (+56 files the parser refuses) |
| `return-not-assigned-on-all-paths` (B2) | 69 |
| `array` | 56 |
| `zero-returns` (B3) | 39 |

The four counts match the operator's brief exactly (113, 69, 39, 77).

## What landed

Soundness held as the brief required: no assume, admit, sorry or axiom
anywhere; nothing discharges a goal without a proof; the grader, the twin
generator, the lift check filter (`t/loop_filter.py`) and the corpus gates
are untouched; no test was weakened or deleted. Every committed task,
method, lemma and conformance fixture lowers byte for byte as before in
all seven kernels, real and twin (`sha256` of `tlib.lower` over the 48
fixture tasks, taken on the base worktree and after every feature: 0
differing cells each time; the merged tree adds the two set tasks and
changes nothing else). Every commit cites the design it copies or says
`INVENTED:` and what was searched.

| feature | track entry, decision row | what changed | kernels |
|---|---|---|---|
| B1 nested-seq-other | Done 9, row 46 | lifter: a `seq<X>` whose element t has no value for refuses under X's own name (`seq-of-real`, `seq-of-datatype`, `seq-of-bitvector`, `seq-of-pair`, `seq-of-bool`, `seq-of-set`, `seq-of-map`); a cast inside a display is an int element, so `[c as char]` lifts when the cast is safe | none |
| B2 return-not-assigned-on-all-paths | Done 12, row 45 | lifter: the body opens with the return type's default and the check stage runs `dafny verify --filter-symbol M` on the source method (`verify-source`), refusing `return-default-unverified` unless dafny's own definite-assignment check accepts it; `char` returns refuse `return-default-char` | none |
| B3 zero-returns | Done 10, row 47 | lifter: the bare name is retired for why decision 22's shape did not apply: a named mutation issue stands alone, a `modifies` without an index assignment refuses `array-mutation` (`modifies-via-call` or `modifies-no-index-assign`), a method with neither return nor `modifies` refuses `lemma-shaped` | none |
| B4 finite sets | Done 11, SPEC.md "Finite sets (v1)" | the type `set` and six total operations (display, `in`, `card`, `union`, `inter`, `diff`), the notation, check_wf, interp, nine probes, two committed tasks; lowered in dafny, verus, fstar, rocq; lean, framac, spark abstain by name | 4 lower, 3 abstain |
| B5 datatypes | Done 15, row 48 | lifter: the blanket `datatype` refusal is split by what the method touches (`seq-of-pair`, `tuple-projection`, `array2`, `real`, `type-decl`, `opaque-type`, `member-access`) and a real datatype use is named by the shape of the file's declarations (`datatype-enum`, `-record`, `-sum`, `-real`, `-generic`, `-recursive`), read from the skipped declaration's tokens; the parser names a `match` on a literal `match-literal`; no t datatype built (measured reach: 11 methods, at most 8 files) | none |
| B5b match on int literals | Done 16, row 52 | lifter: a `match` whose cases are int literals with a `_` default is parsed as the if-chain it is (statement and expression form), logged `match-literal-if-chain`; a char or string literal keeps `match-literal`, no `_` refuses `match-no-default` | none |

The measurement of B2 changed a belief written in `t/LIFTER-DESIGN.md`
section 4.7: Dafny does not "accept such a method with an unspecified
return value". Measured on dafny 4.11.0, definite assignment of an
out-parameter is a verification obligation ("out-parameter 'r', which is
subject to definite-assignment rules, might be uninitialized at this return
point"): a `while true { .. r := i; return; }` body, an if-case and a `break`
followed by a guarded assignment all verify while the syntactic walk refused
them, and a method that truly leaves the return unassigned verifies only
under `--relax-definite-assignment`, which nothing here passes. The section
now says so.

### Finite sets, per kernel

Measured on this machine with the nine `fz_p_set_*` probes (expected verdict
on the real, twin refuted where a twin exists) and the two committed tasks
`tasks/set_toggle.t` and `tasks/set_collect.t`:

| kernel | representation | probes | tasks |
|---|---|---|---|
| dafny | `set<int>`; the empty display let-bound to a typed name (`\|{}\|` is underspecified, a false-ranged comprehension is rejected as not finite, measured) | 9 of 9, twins refuted | 2 verified, twins refuted |
| verus | `vstd::set::Set<int>`; `insert`/`remove` for a singleton union/difference; vstd's three broadcast groups plus one prelude lemma (empty difference is inclusion) in its own module; `==` bridged to `=~=`; the ground certificate over sets closed by the SMT arm (`compute_only` cannot evaluate a cardinality, measured) | 9 of 9, twins refuted | 2 verified, twins refuted |
| fstar | `FStar.FiniteSet.Base` with `FStar.FiniteSet.Ambient`; a task using sets is lowered in the Ghost effect (`cardinality` is GTot, equality the ghost decision of `equal`); union with a singleton spelled `insert` | 9 of 9, twins refuted | 2 verified, twins refuted |
| rocq | Stdlib 9.2 `MSetList.Make Z_as_OT` with `MSetProperties`; prelude lemmas and `t_inv1` arms for membership, negative membership, the four cardinality laws and set equality, each fact posed once behind the prelude's persistent marker | 9 of 9 real; 9 of 9 twins refuted (`fz_p_set_eq`'s twin ran to the 180 s wall until the certificate computed its closed set atoms) | both verified, both twins refuted (the set-valued twin result is certified by `S.Equal`, proved by computing `S.equal`, since MSetList values are not Leibniz-equal across computations) |
| lean | none: core Lean 4 without Mathlib has no finite set | abstain by name | abstain |
| framac | none: C has no set value | abstain by name | abstain |
| spark | none yet: `SPARK.Containers.Functional.Sets` exists but has no difference function and its cardinality laws are unmeasured here | abstain by name | abstain |

The corpus-facing half of finite sets is not built: the lifter does not yet
map Dafny's `set<int>` onto the type, and the comprehension `set i | lo <=
i < hi && P(i)` (39 of the 77 methods, always under `|..|` as a count) is
not in v1 (SPEC.md says how it will be stated: a defunctionalised
predicate, so that SPARK and Frama-C can name it).

Tests, all without a prover unless `--slow`: `t/test_lift_seq_elements.py`
(3), `t/test_lift_return_default.py` (6, plus 2 slow: one accepted source
checked end to end, one refused `return-default-unverified` with dafny's own
message), `t/test_lift_zero_returns.py` (2). The set probes and tasks were
run through each kernel directly (the tables above). The lifter suites
(`pytest t/test_lift_*.py`): 334 passed, 15 failed after the last lifter
change, the same 15 as before the first (14 need a corpus directory or a lab
machine this machine does not have; one, `test_lift_acsl`'s WP end-to-end,
timed out under load 25 and is environment-bound). Whole suite: see below.

## Phase 2: the corpora, per feature

The baseline is the merged-base census above (`r2-base0-skipcheck`); each
feature's files were re-lifted with the new code, skip-check first, then
with the check stage on for the methods that lifted.

| feature | refused (baseline) | pass the gate | lift | checked | what still refuses |
|---|---:|---:|---:|---:|---|
| B1 nested-seq-other | 113 | 113 (every method now carries a name) | 0 | 0 | 84 `seq-of-real`, 20 `seq-of-datatype`, 5 `seq-of-bitvector`, 2 `seq-of-bool`, 1 `seq-of-pair`, 1 `char-cast-unbounded`: none is a t value, so none can lift |
| B2 return-not-assigned-on-all-paths | 69 | 8 | 4 | 1 | 61 `assume` (specification stubs, foreseen by the track's table); 4 refuse elsewhere (`array`, `unbounded-quantifier`, `seq-typing`, `array-mutation`); of the 4 that lift, dafny accepts all four sources (`verify-source` exit 0), 1 checks (ChooseOdd), 3 fail lemmas unrelated to the default (`L_inv_1` twice, a closure function's well-formedness once) |
| B3 zero-returns | 39 | 39 (every method now carries a name) | 0 | 0 | 34 `array-mutation` (23 of them the DJ family writing two arrays; 6 `modifies-via-call`; 5 `modifies-no-index-assign`), 4 `lemma-shaped`, 1 `array` |
| B4 set | 77 | 0 (no lifter mapping yet) | 0 | 0 | 39 comprehensions, 30 displays, 8 typed names |
| B5 datatype | 78 methods, 56 files | 78 (every method now carries a name); 56 (every file) | 0 | 0 | methods: 18 `seq-of-pair`, 17 `datatype-real`, 9 `function-result`, 8 `type-decl`, 8 `datatype-record`, 5 `tuple-projection`, 4 `datatype-generic`, 3 `array2`, 2 `datatype-sum`, 1 each `datatype-enum`, `set`, `opaque-type`, `real`; files: 41 `datatype` (constructor patterns), 15 `match-literal` (12 int, 7 with a `_` default; 2 char; 1 string) |
| B5b match-literal | 15 files | 15 (every file carries a name) | 1 | 1 | 9 `match-literal` (a char or string match in the file), 5 `match-no-default`; the 1 that lifts (DD0831 FibonacciIterative, through its spec_fun) passes the check stage with every lemma verified |

Three of the five buckets were, on measurement, buckets of names rather
than of liftable programs: nothing in `nested-seq-other` is a t value,
nothing in `zero-returns` is a task under SPEC.md's own rule for a method
with no return (its mutated array is the return, or it is a lemma), and 42
of the 78 `datatype` methods touch no datatype (26 of them project a pair
out of a sequence element). What the work bought there is a census that
ranks the real gaps: reals (84 more than the `real` bucket showed, plus 17
real-valued datatypes), a seq of pairs (18 + 1 methods), a pair-of-seqs
return for the 23 two-array methods, `match` on an int as an if-chain (7
files with a `_` default), a record of ints as an n-ary pair (8 methods), a
range analysis for `(lit + e) as char`. A t datatype proper, non-recursive
and without reals or type parameters, would reach 11 methods and at most 8
files; that is why it was named and not built. The if-chain lift was
built and reaches 1 file here, checked.

## Task A: the 2026-09-27 features re-lift, graded

The data branch `data/features-lift-2026-09-27` appeared during the round
(d50caae, 140 tasks past the check stage under
`t/out/lifted-tasks-2026-09-27-features/`). Graded from this branch's
lowerings with `T_SPARK_JOBS=1 python3 t/run_par.py --jobs 4 --tasks <the
data worktree's task directory> --out lift-runs/features-grade --table
t/COVERAGE-lifted-2026-09-27-features.md` (three flake runs per side, 4794
kernel runs, 2 h 53 min); the table is committed on this branch, the tasks
stay on the data branch.

| | tasks |
|---|---:|
| graded | 140 |
| no twin (the ladder found no refuting move) | 8 |
| clean in seven (`verified / refuted` in every kernel) | 19 |
| clean in six | 16 |
| of which the gap kernel is lean | 8 |
| framac | 4 |
| spark | 3 |
| fstar | 1 |

The six-clean gaps by cause: lean `unproved / refuted` 6 (the real side
unproved, the twin refuted) and `abstain / abstain` 2 (the two `modExp`
tasks, a construct the Lean lowering abstains on by name); framac
`malformed / malformed` 3 and `timeout / refuted` 1; spark `timeout /
timeout` 2 and `verified / timeout` 1; fstar `unproved / refuted` 1.

Per kernel, `verified / refuted` cells out of 132 twinned tasks: dafny 92,
fstar 73, verus 60, rocq 42, framac 41, spark 39, lean 35. The run shared
the four cores with this round's own re-lifts, probe runs and test suites
(load 25 to 76 for most of it), and the timeouts say so: spark 54 cells
timed out on both sides and 14 more on the twin side, framac 32 on the real
side, dafny 9 on the real side and 4 on both, fstar 10 on both. Those are
the wall's verdicts, not the kernels'; `run_par` does not cache a timeout,
so a rerun of the same line on a quiet machine recomputes exactly those
cells and keeps the rest (the cache lives under `t/out/cache`). Frama-C's
47 abstentions and Lean's 27 are the lowerings' own refusals by name (sets,
strings, nested sequences), and Verus's 4 `malformed / malformed` and
Frama-C's 7 are cells the harness could not parse a verdict from, listed in
the table.

## What is left, and why

- **Finite sets, the corpus half.** The lifter's mapping of Dafny `set<int>`
  (a typed parameter or return, a display, `in`, `|s|`, `+`, `*`, `-`) onto
  the new type would reach 38 of the 77 methods; the other 39 are the
  comprehension, which needs the defunctionalised predicate SPEC.md names.
  Three kernels abstain: Lean needs a sorted duplicate-free `List Int`
  encoding proved equivalent (core has no `Finset`); Frama-C needs a
  sorted-array encoding with WP proofs; SPARK needs the
  `Functional_Sets` instantiation and a difference function the library
  lacks. No Rocq set cell is open any more: `set_toggle`'s twin was
  unproved until the value certificate learned to state a set-valued result
  as `S.Equal` rather than Leibniz equality (an MSetList value carries a
  sortedness proof, so `cbv; reflexivity` cannot identify two computations
  of one set), and `fz_p_set_eq`'s twin ran to the wall until the same
  certificate computed the closed set atoms every witness leaves
  (`t_set_ground`: membership by `S.mem`, cardinality by `vm_compute`);
  both refute now.
- **Two arrays written in one method.** 23 vericoding DJ methods
  (`a[i] := 0` and `sum[0] := total` under `modifies a, sum`) are one
  construct short: a task returning a pair of seqs, which t's pair already
  holds. Named in row 47, not built.
- **`(lit + e) as char` under a `requires` bound on `e`.** The int-to-string
  helpers (`IntToString`, `int_to_string`) refuse `char-cast-unbounded`
  where a two-line interval analysis would prove the cast in range.
- **`function-result`, 305 methods**, is the binding refusal of the census
  and is being built elsewhere (`feat/seq-spec-fun`); this branch did not
  touch it, as instructed.
- **A t datatype (B5)** was measured and not built: after row 48's names,
  a non-recursive datatype without reals or type parameters reaches 11
  methods (8 `datatype-record`, 2 `-sum`, 1 `-enum`) and at most 8 of the
  56 `match` files, against a declaration form in seven kernels and twin
  moves over constructors. 17 datatype methods carry a real field and 4 a
  type parameter; 41 of the 56 files match on constructors. The two cheaper
  levers the census exposed were `match-literal` on an int with a `_`
  default as an if-chain, since built (B5b: 1 of the 15 files lifts and
  checks; the other int matches share their file with a char match or have
  no default), and a record of ints as an n-ary pair (t's pair covers two
  fields already), not built.
- **The differential arm** still needs dotnet; `dafny run --target:py`
  works on this machine (measured while checking Dafny's auto-init
  defaults: 0, false, [], "", 'D' for char) and would give the check stage
  its third arm here, but the check filter was out of scope.

## The whole suite against round 1's 51

The whole suite (`pytest t --ignore=t/test_lab_gui.py`, which needs
tkinter), run on this branch after the sets merge and alongside the Task A
grading (load 25 to 76 on four cores, 15 min 07 s): 1428 passed, 56 failed,
34 skipped, 1 xfailed, 113 subtests passed. Round 1 closed at 51 failed,
1396 passed, 28 skipped. Set against round 1's 51 by test name, none of
the 51 stopped failing and five are new:

- Four in `test_dawnr_english.py` (`WidenedProtectedSetTest`, three cases,
  and `FlaggedIdsUncappedTest`, one) come with tests the base gained on
  2026-09-27 after round 1's run (`6f988e8`, `f875427`) and fail here with
  `gzip.BadGzipFile: Not a gzipped file (b've')`: `nl/data/mbpp.jsonl.gz`
  and `nl/data/humaneval.jsonl.gz` are 130-byte git-lfs pointers on this
  checkout, the same cause as the baseline's `test_mbpp_dfy` failure.
  Environment-bound, not this branch's.
- One, `test_vscode.py::test_grammar_covers_keywords_and_string_methods`,
  was this branch's: the five set keywords `surface.py` gained (`set`,
  `card`, `union`, `inter`, `diff`) had no pattern in the TextMate
  grammar. Fixed in the same commit as the Rocq set certificate; the four
  `test_vscode` tests pass again.

So the suite stands at 55 environment-bound failures on this checkout: round
1's 51 plus the four new lfs-pointer cases, and no failure caused by round 2.
The 12 tests this round added (`test_lift_return_default.py`,
`test_lift_seq_elements.py`, `test_lift_zero_returns.py`) are in the 1428;
the finite-set coverage lives in `conformance.py`'s nine `fz_p_set_*`
probes and `surface.py --check`'s four written examples, not in pytest.

## How to reproduce

- Conformance: `T_PROVER_MEMCAP=0 python3 t/conformance.py --jobs 3`; the
  SPARK re-measurement is `verifiers.spark.verify` on each timed-out
  probe's `.ads` under the run's workdir, one at a time.
- The census: `python3 t/lifter.py --dir <staged> --out <dir> --jobs 4
  --force --skip-check` from the merged base (the baseline) and from this
  branch; tally the `*.outcome.json` by refusal reason and join the two by
  (source, method).
- Per feature: re-lift the baseline's files for the reason with
  `--list <files> --corpus-dir /`, skip-check, then without `--skip-check`
  for the methods that lifted; `verify-source` exit codes are in each
  `.lift.json` sidecar.
- Finite sets: `python3 t/surface.py --check` (26 of 26 written examples,
  1846 of 1846 corpus tasks round-trip), the `fz_p_set_*` probes and the
  two `tasks/set_*.t` files lowered with `lower_<kernel>.lower` and
  verified with `verifiers.<kernel>.verify`, real and twin (`harness.
  twin_cached`, `harness.real_witness`), as `t/conformance.py` does.
- Byte identity: hash `tlib.lower(task, kernel, twin_body=...)` for every
  file under `t/tasks`, `t/methods`, `t/methods_probe`, `t/lemmas`,
  `t/lemmas_probe` and all seven kernels before and after.
- Task A: the `run_par.py` line above, from this branch, against the data
  worktree's task directory.
