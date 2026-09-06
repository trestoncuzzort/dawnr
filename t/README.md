# t

**t is a specification interlingua, not (yet) a programming language.** A task is
written once in t, with a typed signature, preconditions, postconditions and for
now a small body, then lowered mechanically to established verifiers, whose kernels
supply every verdict. t itself proves nothing and is trusted for nothing; that is
the design, not a temporary weakness. The trust always bottoms out in a kernel
with decades of adversarial history (today: Dafny 4.11.0 / Z3; next: Verus,
SPARK, the WS-7 tier-A list).

Prior art this stands on rather than beside: Why3 (one spec language, many
provers) and Viper (one intermediate verification language, many frontends).
If t ever grows its own checker, that checker gets verified inside Rocq or Lean
(the CakeML path) before anything trusts it, since a homemade language certifying a
homemade system is two unaudited instruments signing each other's receipts, and
it is refused here in advance (ROADMAP.md, "The far field").

## v0, honestly scoped

- Types: `int`. No arrays, no quantifiers, no heap, no loops. v0 exists to prove
  the pipeline, task to lowering to kernel verdict to witness, not expressiveness.
- A task is JSON (`tasks/*.json`): no parser to write means no parser to trust.
- `lower_dafny.py` emits Dafny; `dafny verify` decides. Exit codes as measured
  on 4.11.0: 0 verified, 2 malformed, 4 could-not-prove, which reads UNPROVED
  (TIMEOUT on "out of resource"). Until 2026-09-02 exit 4 was read as refuted;
  it is not a countermodel and is no longer read as one
  (WITNESS-2026-09-02-dafny-door.md).
- Every lowering also emits a BROKEN TWIN (the body's first `if` collapsed to
  its then-branch). A task only counts when the real lowering VERIFIES **and**
  the twin is REFUTED: one witness for "the spec is provable," one for "the
  spec has teeth." Since 2026-09-02 the twin's REFUTED means the kernel accepted
  a certificate lemma restating the measured witness, not a bare failing exit.
  A twin that still verifies is a vacuous spec and the task is
  refused. This is dafny_pairs.py's measured-flip rule, applied to t from birth.

## Files

| File | What it is |
|---|---|
| `SPEC.md` | The v0 task format and expression grammar, complete. |
| `lower_dafny.py` | t → Dafny lowering + twin generation + verdict collection. |
| `tasks/` | Tasks in t. |
| `out/` | Lowered .dfy files and verdicts (regenerated; witnesses are committed). |
