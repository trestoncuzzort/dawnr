# Lifting vericoding's Verus and Lean solutions into t, 2026-09-26

The Dafny track of vericoding-benchmark (arXiv:2509.22908, MIT) was lifted on 2026-09-26
(`t/LIFT-2026-09-26.md`). This lift covers the benchmark's other two languages: 962 verified
Verus solutions (`vericoded/V*_vericoded.rs`) and 626 verified Lean 4 solutions
(`vericoded/L*_vericoded.lean`). Each solution is a program with its specification.
`specs/` holds the specifications alone, and by the README some of those do not compile.
This lift reads `specs/` for one thing only: to check that a solution did not change the
specification it was given. A follow-on applies the same Verus front end to
verus-lang/verus's own `examples/` and to its `vstd` library.

Everything below was measured in this run. The tables are at `t/COVERAGE-lifted-vericoding-verus.md`,
`t/COVERAGE-lifted-vericoding-lean.md` and `t/COVERAGE-lifted-verus-examples.md` (vstd:
see its section). The lifted tasks are in `t/out/lifted-tasks-vericoding-{verus,lean}`, with
each lift's records in the `.meta` beside it.

## The pipeline, and what is reused

    vericoded file -> select -> front end (render Dafny) -> t/lifter.py -> native equivalence
      -> weak-spec probe -> gates (lift_corpora.screen) -> lifter check stage (lab) -> seven kernels (lab)

- **Front ends.** `t/lift_verus.py` and `t/lift_lean.py` read the file and render the gradable
  program as Dafny text, together with every definition its contract reaches. The lifter's
  intermediate form is the Dafny AST (`t/lift_ast.py`). Rendering into it means resolve,
  parse, classify, rewrite, the equivalence lemmas and the differential run of
  `t/lift_check.py` all run unchanged, and none of them is forked. Dafny's resolver also
  type-checks every rendering.
- **Native equivalence.** The rendering itself is not trusted.
  - `t/lift_check_verus.py` proves in Verus, on the source's own parameter types, that the
    source requires is equivalent to the lifted requires. It then proves that, under the
    requires, the source ensures is equivalent to the lifted ensures. The source's
    declarations are included verbatim, and the lifted contract is printed by
    `t/lower_verus.py`.
  - `t/lift_check_lean.py` does the same in core Lean 4.33.1, using `t/lower_lean.py`'s
    `Lower` printer, a fixed tactic cascade, and a `#print axioms` audit of both theorems.
  - A task whose equivalence is not proved is refused. Its English head describes the
    source problem, and nothing else ties the lifted spec to that problem.
  - Negative controls: one clause of a lifted spec was corrupted by hand in VA0002 and in
    LA0017. Each harness then fails, naming the lemma that guards the clause.
- **Weak-specification probe.** A task is refused if a constant result (0, 1, -1, true,
  false, [], [0], or pairs of these) satisfies every ensures on every admissible input the
  t interpreter draws. This is the benchmark's own `inspection/WEAK.md` failure mode. For
  example, `largest_prime_factor` has an ensures that admits 1, and VV0003
  `longest_increasing_subsequence` is "solved" by returning 0.
- **Gates.** `lift_corpora.screen` runs unchanged: held-out ids under every alias, the dev
  split, a HumanEval index that names a gated problem, and the behavioural twin on drawn
  inputs. Clever's `clever_N` is read as HumanEval N, the same numbering as the benchmark
  README.
- **Dedupe.** Problems are deduplicated by source and source id from
  `vericoding_benchmark_v1.csv`. The Verus track is checked against the three Dafny lifts
  (`lifted-tasks-2026-09-26`, `-let`, `-recovered`). The Lean track is checked against those
  and against the Verus lift. A second member of one of the benchmark's near-duplicate
  groups is also skipped.
- **Lab stages.** The lifter's own check stage and the seven kernels ran on the lab, as for
  the Dafny lift. The steps: `bash t/r12_data_queue.sh lift-vericoding-verus`,
  `lift-vericoding-lean`, `lift-verus-examples`, `lift-vstd`. This run was driven by hand
  with the same commands, at `--jobs 2` (12 kernel processes).

## Counts

| | Verus | Lean |
|---|---:|---:|
| vericoded files (the verified solutions) | 962 | 626 |
| of which the results CSV records a successful run | 802 | 538 |
| refused at selection: already lifted (Dafny track; Lean also against Verus) | 189 | 176 |
| refused at selection: near-duplicate group | 26 | 21 |
| refused at selection: specification changed by the vericoder | 12 | 9 |
| refused at selection: manual inspection (weak / mistranslated) | 6 | 2 |
| refused at selection: issue list | 0 | 0 |
| **new problems after dedupe and selection** | **729** | **418** |
| rendered by the front end | 262 | 79 |
| lifted by t/lifter.py | 208 | 58 |
| equivalence to the source proved in the source's prover | 169 | 39 |
| refused as a weak specification | 39 | 8 |
| refused by the gates (behavioural twin of a held-out / same-task-exclusion problem) | 51 (35 / 16) | 8 (6 / 2) |
| **accepted** | **79** | **23** |
| with an English head (the source's own statement) | 65 | 8 |
| passed the lifter's Dafny check stage on the lab | 66 | 16 |
| **clean in all seven kernels** | **15** | **5** |
| **clean in six of seven (gap)** | **8** (framac 5, lean 2, fstar 1) | **3** (framac 2, spark 1) |

Of the clean tasks, 12 of the 15 Verus ones and all 5 Lean ones carry an English head. In
the clean-in-six rows, 7 of 8 Verus and 1 of 3 Lean do.

Clean in seven, by source:
- Verus: numpy_triple 6, dafnybench 5, verina 3, apps 1.
- Lean: verina 3, dafnybench 1, verified_cogen 1.

The check stage refused 13 Verus tasks (6 lemma failures, 6 differential disagreements,
1 checker error) and 7 Lean tasks (all lemma failures).

## Trust, per language, as recorded in each task's `trust.jsonl` row

- **Verus: `verus-equivalence`.**
  - The lifted requires and ensures are proved equivalent to the source's in Verus, over
    every value of the source's own types. Machine integers are widened to mathematical
    ones, so the equality holds on the source's domain, and the kernels prove the program
    on the wider one.
  - After that, the lifter's Dafny lemmas and differential run passed (`lifter_check`).
  - The record also holds the task's seven-kernel row, with `clean_in` and the columns
    that were not clean (`not_clean`), so a task can be admitted as clean in six of seven
    with the gap named.
- **Lean: `lean-equivalence`.** The same, with the theorems proved in core Lean 4.33.1
  (`simp`, `omega`, `grind`) and audited free of `sorryAx`. The harness drops the
  source's `import Mathlib`: 10 lifted tasks got no harness and are refused. Most of these
  are lifted definitions that `grind` could not prove terminating or well-defined without
  Mathlib.
- **Verus examples: `verus-equivalence`.** Each source file is re-run through Verus here.
  A file with any error lifts nothing (22 candidates). Some `examples/` files fail on
  purpose, or fail on this Verus version.
- **vstd: `verus-equivalence, lemma-as-task`.**
  - The source is trusted as the crate Verus's own build verifies; it is not re-run file by
    file here, and the census says so.
  - A lemma `requires P ensures Q` becomes a task `returns (ok: bool) requires P ensures ok
    <==> Q` with body `ok := true`. The program verifies exactly when the lemma holds, and a
    twin returning false would be refuted wherever Q is satisfiable.
  - None of these tasks is graded yet, in either encoding. The grader's twin generator
    finds "no `if` and no invariant, nothing to mutate" in `ok := true`, so run_par records
    `no-twin` for all 129 and runs no kernel at all: 0 kernel runs. What they carry is the
    Verus equivalence and the lifter's Dafny check. They are not admissible as clean
    documents until the twin generator has a rung for a constant body (negate the
    literal); that rung is item 1 of "What would unlock", below.

## Why files were refused (these feed the t features track)

Front end (render), Verus:

| reason | files |
|---|---:|
| float (f32/f64) | 159 |
| calls-other-method (a helper exec fn) | 72 |
| mut-ref-param (`&mut` in place) | 32 |
| trust-hole (assume / admit / external_body) | 31 |
| tuple (not a two-scalar result) | 31 |
| datatype (struct, enum, Option) | 30 |
| zero-ensures | 18 |
| match | 12 |
| verus-unparsed | 11 |
| as-cast (signed to usize) | 10 |
| higher-order (closures other than an identity cast) | 10 |

The lifter, after rendering (Verus): unbounded-quantifier 29, nested-seq-string 9,
seq-return 6, seq-of-bool 4, char-cast-unbounded 2.

Front end (render), Lean:

| reason | files |
|---|---:|
| string | 85 |
| higher-order (fun, foldl, map, filter) | 44 |
| trust-hole (sorry, axiom, instance, notation) | 42 |
| hoare-triple (numpy_triple's monadic specs) | 38 |
| tuple | 25 |
| lean-unparsed | 21 |
| match | 10 |
| unknown-function | 10 |

The lifter after rendering (Lean): unbounded-quantifier 20.

Most Lean instance holes are `local instance` overrides in solution code; one redefines `≤`
on Int to be always true.

The equivalence was not proved for:
- **Verus: 39.** In 21 the ensures lemma fails: set-like specs, rotations, and recursive
  spec fns whose lifted image the induction step does not reach. 5 have a quantifier with
  no trigger term. 8 lifted contracts do not type-check in Verus. In the one inspected
  (VA0561), a lifted spec_fun is typed `int` but returns a string: a lifter typing bug
  worth its own fix.
- **Lean: 19.** In 9 the tactic cascade fails; 10 got no harness.

## The kernels, per column (Verus, 66 graded rows)

dafny 54, spark 51, fstar 47, verus 41, rocq 32, framac 24, lean 24 rows read `verified /
refuted`. The real side verifies more often than that suggests: dafny 56, verus 52, spark 52,
fstar 47, rocq 35, lean 30, framac 26. The rest is lost as follows:
- framac: 16 timeouts and 18 abstains.
- lean: 9 abstains, 14 unproved, 7 timeouts.
- rocq: 14 abstains, 9 unproved.
- verus: 11 rows verify the real program but leave the twin `unproved` rather than
  `refuted`.
- Six rows are `no-twin` in every column.

Lean track, 16 graded rows: dafny 14, fstar 14, verus 13, spark 12, lean 10, rocq 8,
framac 6.

## Follow-on: verus-lang/verus's examples/ and vstd (MIT, The Verus Contributors)

`t/lift_verus_corpus.py` (queue steps `lift-verus-examples`, `lift-vstd`). Every exec fn
or value-returning proof fn with an ensures is a candidate. With `--lemmas`, so is every
proof fn with an ensures and no result. Trust holes are judged per function. Identical
tasks from two files are kept once. None of these tasks carries a head.

| | examples/ | vstd |
|---|---:|---:|
| .rs files | 156 | 130 |
| candidates (in files that verify here / all, for vstd) | 49 | 285 |
| rendered | 23 | 158 |
| lifted | 21 | 147 |
| equivalence proved | 21 | 147 |
| duplicates of another file's task | 7 | 11 |
| weak / twin refusals | 3 / 2 | 0 / 0 |
| accepted | 9 | 136 |
| passed the lifter check stage | 8 | 129 |
| clean in seven / six | 6 / 0 | 0 / 0 (every row `no-twin`, see below) |

vstd's refusals:
- generics 60: every seq, set and map lemma in vstd is generic over its element type.
- std-call 18, bitvector 17, bodyless-spec-fn 16.

All 136 accepted vstd tasks are arithmetic lemmas (div_mod, mul, power, internals). On
vstd, three harness fixes took the equivalence from 94 of 147 to 147: a leading
`#![trigger ...]` on an ensures clause, `#![` kept glued, and `reveal` for opaque spec fns.

AutoVerus, Verus-Bench, SAFE and AlphaVerus were not read. They are MBPP- or
HumanEval-derived and collide with the held-out pool one hop removed.

## What would unlock the most remaining documents

0. **A twin for a constant body** (`ok := true` to `ok := false`). This is one rung in the
   twin generator. It would let the 129 checked vstd lemma tasks be graded at all; they
   hold 0 documents today only because nothing is graded.
1. **Seven-kernel conversion of what already lifts.** Of 66 checked Verus tasks, 15 are
   clean in seven and 23 in six or seven. Framac (timeouts and abstains on sequence
   specs), Lean and Rocq lose the most rows. These tasks are all lifted, checked and
   gated already, so every kernel fix converts directly into documents.
2. **Calls to another function (72 Verus files).** This is the same wall as the Dafny
   track's 139. A t task that may call a verified helper would open these files, and
   most of the Verus APPS solutions.
3. **Lean strings (85) and higher-order list code (44).** t already has strings (SPEC.md,
   "Strings as sequences of code points"). The Lean reader does not yet map `String`
   operations onto them.
4. **In-place `&mut Vec` (32 Verus).** These would lift as a returned sequence, the rewrite
   the Dafny lifter already makes for arrays (`array-length-return-ensures`).
5. **Floats (159 Verus, all numpy_triple).** No t encoding exists; these are refused by
   name.

## What is not measured

- Whether the corpus builder admits these tasks: that needs
  `loop_locallm.py corpus --lifted-set t/out/lifted-tasks-vericoding-verus=t/COVERAGE-lifted-vericoding-verus.md --heads <meta>/heads.jsonl`.
  The same `held-out/dev/decontamination` gates run there again.
- Re-verification of the vericoded source files themselves. Only the equivalence harness
  (source declarations verbatim) and, for `examples/`, the whole file were run through the
  source prover. The lifted program is proved independently by the kernels, so a hole in a
  source proof cannot make a lifted document wrong. It can only make its English head
  describe a problem the source never actually solved.
