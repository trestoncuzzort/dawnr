# GRADER.md: what t's grader measures, and how to run it

ROADMAP WS-19 move 1. `t/grade.py` is the one entry point: it grades a
directory of t task files, or a model's replies, through the same seven
kernels, the same twin ladder, the same flake rule and the same coherence
gate that `t/run_par.py` has always used on the committed corpus. This
document is the semantics written down once, so a reader who has never
seen the repo can run a model against the grader and read the table
without reading the seven verifier modules first.

## What a verdict is

Every cell in the table is `real outcome / twin outcome`. The outcome
vocabulary has two layers: the seven kernel-level outcomes any backend can
return for one file (`t/verifiers/__init__.py`'s `Outcome`), and three
driver-level statuses that mean no kernel ran at all for that cell. Each
is named here with what it means and, as important, what it never means.

**VERIFIED.** The kernel produced a positive, checkable proof of the
file's obligations, never merely "no error was printed." Every adapter
demands its own positive evidence beyond exit 0: Dafny's own finish line
with at least one obligation discharged and zero errors (an empty file
exits 0 printing "0 verified, 0 errors" and does NOT count); Verus's
`verified >= 1` plus a non-spec function carrying a real `ensures`; SPARK's
per-unit `.spark` audit showing at least one `info`-severity proof entry
with none unproved or excused; Frama-C's `[wp] Proved goals: N / N` with
`N >= 1`; Lean's and Rocq's kernel-checked audit (`#print axioms` /
`Print Assumptions`, run by the adapter itself, never trusted from the
source) showing no non-allowlisted axiom and no open assumption; F*'s
count of solver-logged `unsat` queries in its own query log, not a stdout
string the source could forge. VERIFIED never means the specification
says anything useful about the problem the task was meant to solve; that
is a separate question, answered by the twin and, for a model's reply, by
its own tests (see "The submission protocol" below).

**REFUTED.** A kernel-checked proof that the file's own obligation FAILS
at a witness point the twin ladder measured. This is never a plain proof
failure: on every one of the seven kernels REFUTED has exactly one door,
the refutation certificate (see "The twin" below), and a bare
"could not prove," "unsolved goals," or nonzero exit is UNPROVED, never
REFUTED. REFUTED never means "the kernel disagreed with the spec" in some
general sense; it means one specific ground fact, the witness's negated
obligation, was proved.

**UNPROVED.** The kernel stopped without exhausting its budget and
without producing a countermodel: SPARK's `gave_up` and `unknown`
`unproved_status` values, Verus's and F*'s "no model, no proof" exit,
Lean's and Rocq's "tactic failed"/"unsolved goals," Dafny's bare exit 4.
This outcome exists because the pre-2026-09-02 adapters minted REFUTED
from exactly these signals and ground-truth fuzzing (`t/fuzz_lower.py`)
measured that as false: a task true by construction (Dafny's `gt_q_ex_lit`,
`ensures r == 0 and exists i in [0,3). i == 2`) exits 4 because Z3 does
not instantiate the existential unprompted, not because the theorem is
false. UNPROVED never means the property is false, and never means it is
true; it means this budget, on this kernel, settled nothing.

**TIMEOUT.** A pinned, deterministic budget was exhausted (SPARK's
`--steps`, Frama-C's per-goal `Timeout`/`Stepout`, or any adapter's own
wall backstop), or an unproved goal's own status names a resource limit.
TIMEOUT is a strict subset of "not knowledge," disjoint from UNPROVED only
by which signal the kernel gave for stopping; it never means REFUTED and
never means VERIFIED.

**MALFORMED.** The file does not parse or resolve (a syntax or
name-resolution error), or a positive-evidence requirement was violated in
a way that indicates zero real obligations were ever in scope: zero
theorem/lemma declarations, an empty file, a certificate discharged on a
file whose own main obligations ALSO fully verified (the coherence gate,
see "What counts" below). MALFORMED is explicitly NOT a proof failure;
t's own docstrings are emphatic that a rejected-half of the taxonomy
teaches syntax, not proof. A model's reply that fails at MALFORMED never
means its idea was wrong, only that the kernel could not even state the
obligation.

**VACUOUS.** The kernel accepted the file, but for the wrong reason: the
specification itself is unsatisfiable or content-free, so the acceptance
proves nothing about the program. Detected by kernel-native instruments,
never by a regex alone: Verus's `--no-cheating` flag and its own
precondition smoke probe (an appended proof function that tries to derive
`false` from the function's own `requires`), SPARK's proof-warning channel
(`VC_INCONSISTENT_PRE/_POST/_ASSUME`) plus a havoc oracle that replaces the
result with an arbitrary value and re-asks whether the postcondition still
holds, Frama-C's smoke tests plus a complementary-pair consistency probe
for recursive definitions, Lean's and Rocq's axiom-and-assumption audit,
F*'s admit/assume/tactic-admit family plus its own `--report_assumes`
channel. VACUOUS never means REFUTED (a vacuous spec is accepted, not
rejected) and never means the program is wrong; it means the theorem
proved is not the one that was supposed to matter.

**TOOL_ERROR.** Anything else: the binary is absent or crashed, its output
did not parse, or an instrument the adapter depends on (Verus's vacuity
probe, SPARK's havoc oracle) itself failed to run. TOOL_ERROR is never
counted as evidence of anything, for or against.

**ABSTAIN** (driver-level, not a kernel `Outcome`). The lowering itself
raised `NotImplementedError` before any kernel ever saw a file: the
backend's lowering has no honest translation for something this task
uses. `run_par.py`/`grade.py` print the reason and record `abstain /
abstain` for that cell. ABSTAIN never means the kernel looked at the task
and gave up; the kernel was never invoked.

**no-twin** (driver-level). The twin ladder (`harness.twin_for`) found no
operator, on any rung, whose mutation is a measurable flip; see "The
twin" below for the four named reasons (`no-operator`, `no-witness`,
`no-input`, `real-undefined`, plus `candidate-budget` when the search
itself was cut off). Every kernel column reads `no-twin / no-twin` for
that task, and the task counts nowhere: an unmeasurable twin is reported
as such, never passed off as a flip.

One more driver-level status appears in the raw rows though it was not on
the request list above: **lower-error**, when a lowering raises any other
exception (a bug, not a deliberate abstention). Recorded the same way as
ABSTAIN, `lower-error / lower-error`, and, like ABSTAIN, is never evidence
about the kernel.

## What counts

A column counts for one task when, and only when, all three hold: the
REAL file's outcome is VERIFIED, the TWIN file's outcome is REFUTED, and
the two flake-checked runs behind those outcomes agreed (see "The flake
rule" below; a flaked cell never counts even if its last-observed outcome
happens to be verified/refuted). This is exactly the tuple
`(Outcome.VERIFIED, Outcome.REFUTED, True)` `run_par.py` and `grade.py`
both test for.

Because REFUTED itself is minted, on every one of the seven kernels, if
and only if the twin's refutation certificate was declared and accepted
(never from a bare proof failure), "twin REFUTED" and "that kernel
accepted a certificate proving the spec fails at the measured witness"
are the same fact under two names. `grade.py`'s `verdicts.json` records
this per column as `certificate_accepted`, computed as exactly `twin ==
REFUTED`; nothing about the certificate's internal shape is reimplemented
or re-derived, because each kernel's own `verify()` already decided it.

**The coherence gate.** A file that carries the certificate's name (the
exact identifier `t_refutation_certificate`) and whose OWN main
obligations also fully verify is never allowed to also mint REFUTED:
proving a fact both true (the main obligations) and false (the
certificate's negated instance of the same fact) in the same file is
incoherent, so every adapter demotes that case to MALFORMED instead. This
rule lives inside each `verifiers/<kernel>.py` module (dated 2026-09-07
across the columns that added it), applied before the outcome is ever
returned; the grader calls each kernel's `verify()` and receives an
outcome the gate has already been applied to. There is no separate gate
value to compute afterward.

**"In all seven"** (or "in all N present," when fewer than seven kernels
answered, or `--kernels` restricted the run) means the task's row counts
in EVERY column that ran: `columns_counting == kernels_present` for that
row. This is exactly AGREEMENT.md's own stated definition of Agreement
("Agreement means `verified / refuted` in every present column"), and
`grade.py`'s per-task `gate` boolean in `verdicts.json` is that same test,
named once and reused, not recomputed with different rules.

## The twin

A twin is a deterministic, single mutation of a task's BODY (never its
`requires`, `ensures`, `spec_funs`, or the surviving `decreases`
clauses): the spec is the fixed instrument, the body is what gets broken.
Selection is a fixed ladder, tried in this order, first candidate with a
measured witness wins, sites enumerated in pre-order:

1. INVARIANT-DROP: delete one invariant of one loop.
2. COLLAPSE-IF: replace one `if` with its then-branch.
3. NEGATE-COND: swap one `if`'s branches.
4. COMPARE-FLIP: `<` <-> `<=`, `>` <-> `>=` at one comparison.
5. BOUNDARY-SWAP: swap the operands of one order comparison.
6. OFF-BY-ONE: +/-1 on one literal, index, loop bound, slice endpoint, or
   `fill` length.
7. WRONG-VAR: swap one variable for another of the same type in scope, or
   (SPEC.md "Pairs") swap a pair's two components or a `fst`/`snd`
   projection.
8. DROP-GUARD: drop one conjunct of an `if`/`while` condition.

**The witness is a measurement, not an assumption.** `t/interp.py` runs
the real body and the candidate twin over a bounded, enumerated domain and
only accepts a candidate that carries one of two kinds of witness:

- a VALUE witness: a concrete input satisfying `requires` on which the
  real body and the twin compute different values, or the twin is
  undefined where the real body has one;
- a PROOF witness (INVARIANT-DROP only, since its twin computes the exact
  same value by construction): a loop state satisfying `requires` and the
  SURVIVING invariants that either falsifies `ensures` with the guard
  false ("exit" entailment) or breaks a surviving invariant in one more
  iteration ("preservation").

This matters because it was measured to matter: over 1395 fuzzer-generated
tasks, 129 of them, 9.2%, had a naive twin (the v0/v1 rule's single fixed
mutation) that computed an IDENTICAL value to the real program on every
input tried. On those tasks a REFUTED verdict would be luck and a VERIFIED
twin would be indistinguishable from a vacuous spec. **This is why a spec
that merely restates its body cannot count**: a twin with no behavioral
difference from the real program is, for measurement purposes, the same
situation as `ensures true` or `ensures r == <the body's own expression>`,
because in both cases no kernel-checked fact separates the real claim from
a false one. The ladder's fix is to keep climbing until some rung produces
a witness, and to refuse the task by name (`no-witness`, `no-input`,
`real-undefined`, `no-operator`, or `candidate-budget`) when none does,
rather than reporting an unmeasured flip.

A second, weaker case exists and is tagged rather than hidden: a witness
that merely shows the real body and the twin DIFFER is not by itself
grounds for a refutation, because a loose `ensures` can be satisfied by
both values. The ladder therefore prefers a witness that FALSIFIES
`ensures` at the twin's value, and only falls back to a merely-differing
witness when nothing on the whole ladder falsifies anything; that fallback
is named in the task's operator tag with a `+nonrefuting` suffix (visible
in `grade.py`'s `op` field), so a reader can tell a fully-grounded flip
from the weaker case that produced it. Accepting on difference alone,
measured 2026-09-04, produced 88 cells across all seven kernels whose twin
came back VERIFIED, every one a collapse-if, clustered by task rather than
by kernel: the signature of an unrefutable twin, not of seven adapters
being wrong.

**The certificate**, the one door to REFUTED on every kernel: when the
ladder found a witness, the lowering appends to the TWIN file one
parameterless, otherwise-unadorned obligation named exactly
`t_refutation_certificate` (a Dafny/Verus/Rocq lemma, an F* lemma, a
Frama-C or SPARK ground goal, a Lean theorem) restating the witness as a
ground claim: the negated `ensures` instantiated at the concrete input, or
the loop-state fact the witness names. REFUTED is minted if and only if
that one obligation is declared and the kernel accepts it in an isolated
or targeted re-check; a certificate the kernel rejects reads UNPROVED,
never REFUTED, and (the coherence gate) a certificate on a file that
otherwise fully verifies reads MALFORMED, never REFUTED. Planting the bare
name in an honest program can therefore only ever demote that program, not
promote it. What no adapter can check is that the asserted ground formula
IS the negated spec at the witness; that binding is made once, in the
trusted lowering, the same trust already extended to every other lowered
obligation.

## The flake rule and the budgets

Every verdict is `flake_check`ed: the same file is verified `n` times
(default 3, `verifiers.flake_check`'s and `verifiers.cell_pair`'s own
default; `grade.py --flake N` changes it, `run_par.py` never does) and the
result is trusted only if all `n` runs agree on the outcome; a
disagreement returns the LAST result with `agreed=False`, shown in
AGREEMENT.md-format tables as `(FLAKED)` and in `grade.py`'s
`verdicts.json` as `"agreed": false`. A flaked cell never counts, even if
its last-observed outcome happens to read verified/refuted. This applies
uniformly, including to the kernel-checked backends (Lean, Rocq), which
are architecturally deterministic: re-measuring a determinism claim is
cheap, so nobody is exempted by construction. Since 2026-09-09 the `n`
runs, and the real and twin flake checks of one cell, run concurrently
(threads; each kernel call is its own subprocess and scratch directory),
so a cell's wall time is one budget, not six; `T_CELL_SERIAL=1` restores
the serial form for comparison.

Every kernel's budget is a deterministic resource bound, never a bare
wall clock, except where the kernel offers none; a wall backstop exists
everywhere as a hang guard only and is never itself evidence. Versions
below are read from AGREEMENT.md's own Backends block (2026-09-10 run);
budgets are read from each `verifiers/<kernel>.py` module's own constants.

| kernel | version pin | deterministic budget | wall backstop |
|---|---|---|---|
| dafny | dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2 | `--resource-limit 500000` (Z3 units) | 120s |
| verus | verus 0.2026.08.30.b432e82 | `--rlimit 10` | 120s |
| spark | gnatprove FSF 16.1.0 / Why3 for gnatprove 1.8.2+git | `--steps 20000` (`--ce-steps` pinned to the same value) | 180s |
| framac | frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free | `-wp-steps 20000`, `-wp-timeout 10s`, `-wp-smoke-timeout 5s`, `-wp-par 4`, `-wp-model Typed+nat` | 240s (60s for the print pass, 120s for the vacuity probe) |
| lean | Lean (version 4.33.1) | `-DmaxHeartbeats 400000` | 180s |
| rocq | The Rocq Prover, version 9.2 | none (no deterministic resource flag exists at the CLI) | 180s |
| fstar | F* 2026.08.30 / OCaml 5.3.0 / commit 2b82aefeff37 | `--z3rlimit 50`, `--z3seed` and `--z3version` pinned | 120s |

## The submission protocol

A submission is one t task per problem: for `--tasks`, one JSON file per
task in `t/surface.py`'s parsed form; for `--replies`, one model reply per
problem, from which the grader extracts the FIRST fenced ` ```t ` block
(or, failing that, a bare line starting `t 0` or `t 1`, the same
`spec_experiment.find_block` two-step search). Only the first block is
read; anything else in the reply (explanation, a second attempt) is
ignored.

**The record layout**, PATH given to `--replies`, is either:

- the spec experiment's raw record directory
  (`out/spec-experiment/<tag>/raw/<task_id>.json`, one file per problem):
  `{"task_id", "fn", "model", "digest", "pool_version", "prompt_version",
  "options", "messages", "reply", "prompt_tokens", "reply_tokens",
  "eval_s", "wall_s", "done_reason"}`; when this form is given, optional
  tests come from `spec_experiment.pool(pool_version)`'s own parsed MBPP
  assertions for that `task_id`, exactly what `spec_experiment.py`'s
  `tests` stage already uses; or
- a plain JSONL file, one object per line, `{"id": ..., "reply": "...",
  "tests": [...optional MBPP-style assert strings...]}`; when `"tests"` is
  given here, each string is parsed with `mbpp_dfy.parse_assertion` (the
  shape `assert f(a, b) == expected`, or the bare/`not` form for a
  boolean answer) and a string that does not parse that way is refused
  and does not count as a test point.

Each extracted block is parsed with `surface.parse`, renamed to a name
unique to its record id (fixing every self-call the same way, so a
recursive task's own calls still resolve), and checked with
`fuzz_lower.check_wf`. A record is refused, and the reason named, at one
of exactly three stages, mirroring `spec_experiment.cmd_extract`:

- `no-block`: no fenced or bare-header t block was found in the reply at
  all;
- `parse:<message>`: the block does not parse as t surface syntax, most
  often (measured on the qwen2.5-coder-1.5b-r2 replies below) an operator
  or construct outside t's fragment leaking from the model's Python habit
  (`&`, `^`, `|`, `/`, a `for` comprehension, a bare `.` method call);
- `wf:<messages>`: the parsed task fails `fuzz_lower.check_wf` (an
  unbound name, a `decreases` on a task with no self-call, a call to a
  function t does not have such as `sqrt`, `sum`, or `max_prime_factor`).

Only a record that reaches neither refusal is written to `--out/tasks/`
and graded. Nothing is dropped silently: `verdicts.json`'s `extract` block
(present only for `--replies`) names the stage and reason for every
record, well-formed or not, and `tests` records the interpreter's verdict
for every well-formed task whose test points could be resolved.

Optional tests are never part of what counts in the kernel table; they
are a second, independent signal (SPEC.md's own point: a task can VERIFY
with a REFUTED twin and still not be the program the problem asked for,
and a task can pass its tests and still not verify). `spec_experiment
.run_point`, called unchanged, reports one of `pass`, `fail`,
`requires-excluded` (the model's own precondition rejects a test input),
`undefined`, `budget`, `arity`, or `type` per point, rolled up per task to
`pass` only if every point passes, else `signature` beats `fail` beats
`requires-excluded` beats `undefined`.

## How to read the table

`table.md` is byte-for-byte AGREEMENT.md's format (produced by the same
`run_par.format_table` function, not a second writer kept in sync by
hand): a UTC timestamp header, one row per task, one column per kernel.
Each cell is `real / twin`, for example `verified / refuted` (counts),
`verified / unproved` (a real proof, but the twin's certificate did not
convince this kernel: does not count), `timeout / refuted` (the real
lowering ran out of budget: does not count even though the twin did
refute), `no-twin / no-twin` (the ladder found nothing to measure),
`abstain / abstain` (this backend has no lowering for something the task
uses). A `(FLAKED)` suffix means the three flake runs disagreed; a `—`
means that kernel was not probed or was excluded by `--kernels`. Below
the table, "Kernels present: N of 7 (...)" names which kernels answered
at all, and the Backends block gives each one's exact version string, the
same strings tabulated above.

The columns-counting histogram (worked example, the ninth sweep over 209
lifted DafnyBench/MBPP-DFY tasks, `t/COVERAGE-lifted-785.md`, already
committed, not reproduced by this task) reads a table's rows into "how
many of the present columns counted" and tallies tasks by that count:

| columns counting | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|
| tasks | 42 | 61 | 23 | 16 | 5 | 10 | 24 | 28 |

`grade.py`'s `verdicts.json` carries the same histogram as
`summary.histogram_columns_counting`, and each task's own
`columns_counting` and `gate` fields are what the histogram is built
from; "42 of 209 count in all seven" is `hist[7]`, exactly this row's
first entry.

## How to run it

    python3 grade.py --tasks DIR [--out DIR] [--jobs N] [--kernels a,b,c] [--flake N]
    python3 grade.py --replies PATH [--out DIR] [--jobs N] [--kernels a,b,c] [--flake N]

`--out` defaults to `t/out/grade`; every run writes `table.md`,
`verdicts.json`, and `summary.txt` there (plus, for `--replies`,
`extract.json` and `tests.json`, and the extracted task files themselves
under `--out/tasks/`). Exit code matches `run_par.py`'s convention: 0 on
full agreement, 1 on any disagreement, 2 on an operational refusal (fewer
than 2 kernels answered, by default, or neither/both of `--tasks` and
`--replies` were given).

Measured wall times, this run (2026-09-10, `--jobs 8`, PATH including
`$HOME/.cargo/bin` for verus, run under `tjob` after the shared kernels'
`pairs-final` job finished):

- `python3 grade.py --tasks tasks --out out/grade-committed --jobs 8`:
  314s (5m 14s) over 21 tasks, about 15.0s of wall time per task.
- `python3 grade.py --replies out/spec-experiment/qwen2.5-coder-1.5b-r2/raw --out out/grade-r2 --jobs 8`:
  102s (1m 42s) over 161 replies (23 reached the kernels), about 4.4s of
  wall time per reply, or 4.4s per graded task by the same division.

Both numbers are wall time for the WHOLE run (kernel probing, lowering,
and every flake-checked cell), not a per-cell average; a run with more
ABSTAIN/no-twin/lower-error rows is faster per task because those never
reach a kernel.

## What the grader does NOT claim

Everything SPEC.md's v1 states as a gate rather than an apology: t (and
therefore the grader) has no unbounded quantifiers; no heap or aliasing
(a `seq` is a value, an "array" is a functionally-updated `seq`); no
overflow semantics (mathematical integers; a bounded backend's own range
obligations are a separate, unstated claim); exactly one return value; no
mutual recursion, no higher-order functions, no nested seqs; a string is
sugar for a `seq` of code points with no string library beyond that
(`split`, `upper`, `strip`, `join` do not exist); a pair is one value,
never a pair of pairs or a seq of pairs. A task using any of this is
outside what the grader can even state, not merely outside what it
proved.

Beyond SPEC.md's own list: a VERIFIED/REFUTED counting column is not a
claim that the task's spec describes the ORIGINAL natural-language
problem correctly; a model's reply can verify with a fully refuted twin
in all seven kernels and still specify the wrong function (an
`ensures` that is a real, load-bearing, kernel-checked theorem, about the
wrong thing). The optional tests are the only signal that speaks to that
question at all, and they are reported separately, never folded into the
kernel count. A `+nonrefuting`-tagged witness (see "The twin") is a
strictly weaker measurement than a falsifying one and is named as such,
not silently counted the same. TIMEOUT, UNPROVED, and ABSTAIN are never
evidence that a property is false, true, or unprovable in general, only
that this budget, on this kernel, or this lowering, settled nothing.
Finally, the certificate protocol trusts one binding it cannot itself
check on any kernel: that the ground formula the lowering asserts really
is the negated spec at the measured witness; that binding is made once,
by the lowering, and inherits the same trust every other lowered
obligation already carries.
