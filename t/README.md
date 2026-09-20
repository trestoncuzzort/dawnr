# t

**t is a specification interlingua, not a programming language.** A task is
written once in t, with a typed signature, preconditions, postconditions and a
small body, then lowered mechanically to established verifiers, whose kernels
supply every verdict. t itself proves nothing and is trusted for nothing; that
is the design, not a temporary weakness. The trust always bottoms out in a
kernel with decades of adversarial history.

**Seven kernels are live**, and a task counts only when all seven agree:

| kernel | backend as measured |
|---|---|
| Dafny | 4.11.0 / Z3 |
| Verus | 0.2026.08.30 |
| SPARK | gnatprove FSF 16.1.0 / Why3 1.8.2 |
| Frama-C | 33.0 (Arsenic) / alt-ergo 2.4.3 |
| Lean 4 | 4.33.1 |
| Rocq | 9.2 |
| F\* | 2026.08.30 |

Prior art this stands on rather than beside: Why3 (one spec language, many
provers) and Viper (one intermediate verification language, many frontends).
If t ever grows its own checker, that checker gets verified inside Rocq or Lean
(the CakeML path) before anything trusts it: a homemade language certifying a
homemade system is two unaudited instruments signing each other's receipts, and
that is refused here in advance ([`../ROADMAP.md`](../ROADMAP.md), "The far
field").

## What t covers

Integers, booleans, sequences, pairs, and strings as character sequences.
Loops with invariants, `decreases` clauses, quantifiers (`forall`, `exists`),
and recursive specification functions. **No heap, no floats, no concurrency.**

A task is written as a `.t` file in the surface notation
([`SYNTAX.md`](SYNTAX.md)), parsed and printed by `surface.py`. The JSON that
older documents call "the format" is the AST that notation parses to; it is
derived from the `.t` text and never edited by hand.

## The twin rule

Every lowering also emits a **broken twin**, and a task counts only when the
real lowering VERIFIES **and** the twin is REFUTED: one witness that the
specification is provable, one that it has teeth. A twin that still verifies is
a vacuous specification and the task is refused.

REFUTED means the kernel accepted a certificate lemma restating a measured
witness, not a bare failing exit code. That distinction was learned: until
2026-09-02, Dafny's exit 4 (could-not-prove) was read as refuted. It is not a
countermodel and is no longer read as one
([`WITNESS-2026-09-02-dafny-door.md`](WITNESS-2026-09-02-dafny-door.md)).

[`twins/`](twins/) ships 426 pairs over 90 programs as a standalone artifact:
each a verified program, a near-miss one deliberate edit away, the concrete
input at which the near-miss breaks the specification the program keeps, and
seven independent refutations at that input. A pair is written only when both
halves are on the record.

## Where the verdicts come from

- **One matrix.** 35 committed tasks, 31 verified with the twin refuted in all
  seven ([`AGREEMENT.md`](AGREEMENT.md)), regenerated on a second machine from
  a clean clone with no cell moved.
- **Nested loops, closed 2026-09-18.** A `while` inside a `while` was an
  abstain in Lean, Rocq and F\* and a timeout in Frama-C; all seven now verify
  it with its twin refuted. Two of those fixes were honesty defects rather than
  gaps: Lean could leave a goal unsolved that `sorryAx` then discharged, so a
  lowering that proved nothing could read as verified, and Frama-C was not slow
  at all, the lowering was emitting an invariant of its own that is false.
- **A grammar that is the notation.** [`t.gbnf`](t.gbnf) is t's syntax as a
  grammar a generator can decode against, with identifier rules generated from
  the lexer's keyword set. [`grammar_check.py`](grammar_check.py) proves it
  accepts all 4,208 programs the parser accepts and refuses 590 of 590 replies
  the parser refuses.
- **Specifications are checked against the problems.** [`spec_check.py`](spec_check.py)
  evaluates an accepted specification at the problem's own solution and at the
  problem's own assertions. Across 36 graded answer sets and 650 clean answers,
  13 disagree: tests passed, seven proofs held, twin refuted, and the
  specification still does not say what the problem asked
  ([`SPEC-CHECK-2026-09-18.md`](SPEC-CHECK-2026-09-18.md)).
- **Preflight.** [`preflight.py`](preflight.py) refuses to let a round start on
  a checker whose version cannot be read, a held-out problem in a training set,
  a clean answer resting on a flake or a timeout, or a specification that
  disagrees with its problem.

## Using it

`python3 t/cli.py <subcommand>` is the entry point for working on a single
task: `parse`, `check`, `format`, `lower`, `verify`, `twin`, `explain`. Text
output by default, `--json` for JSON Lines, one record per diagnostic.
Documented with a real example per subcommand in [`COMMAND.md`](COMMAND.md).
`cli.py verify t/tasks` writes a byte-identical `AGREEMENT.md` modulo the
timestamp.

Running a whole grading pass is [`run_par.py`](run_par.py); setup is
[`RUN-ON-LINUX.md`](RUN-ON-LINUX.md).

An editor integration lives in `editors/vscode/`: a plain JavaScript extension
with a TextMate grammar covering every `surface.KEYWORDS` and
`surface.STR_METHODS` entry (checked by `test_vscode.py`), a client that starts
`lsp.py` over stdio, and a "t verdicts" TreeView fed by the `t/verdicts`
notification. This machine has no display, so the window itself is unverified
here; `editors/WALKTHROUGH.md` measures everything reachable without one.

## Files

| Path | What it is |
|---|---|
| `SPEC.md`, `SYNTAX.md` | the task format and the surface grammar |
| `surface.py`, `check_wf.py` | parser, printer, well-formedness |
| `lower_*.py` | one lowering per kernel, plus twin generation |
| `verifiers/` | one driver per kernel, each collecting its own verdict and version |
| `tasks/` | the 35 committed tasks, as `.t` |
| `twins/` | 426 verified/near-miss pairs with separating inputs |
| `run_par.py`, `cli.py` | the grading driver and the single-task entry point |
| `spec_check.py`, `preflight.py` | the checks that decide what counts |
| `out/` | lowered sources and verdicts, regenerated; witnesses are committed |

Results and caveats for the whole project are in
[`../SCOREBOARD.md`](../SCOREBOARD.md) and [`../LIMITS.md`](../LIMITS.md).
