# PREDICT 2026-10-16 — model proposer for spec strengthening (t/spec_propose.py)

**What it is.** The full ExVerus/SpecSyn loop (arXiv:2603.25810, arXiv:2604.21570): for an
under-constrained task, a model is shown the spec + body (surface.print_task) and the surviving
mutants with their separating witnesses (real vs twin output), and asked for t boolean expressions
that, added as `ensures` conjuncts, exclude those wrong behaviours while staying true for the real
program. Each proposal is parsed with surface.parse_expr and run through spec_refine.check; a
proposal is kept ONLY if the gate accepts it (real body still verifies, strictly fewer survivors).
The model proposes; the interpreter gate decides. Model: `~/.local/bin/fable` (Fable on the Console
credits) by default; AWS Bedrock is an alternative.

**Prediction, with the number that falsifies it.**

- Run on the 6 under-constrained t/humanevaldafny specs. At least 1 (beyond the hand-proven is_prime)
  is strengthened by a model-proposed clause that PASSES the gate (real_ok, survivors_after < before).
  FALSIFIED IF zero model proposals pass the gate — recorded honestly as: a single-shot surface-clause
  proposer is insufficient for these specs, and (importantly) the gate correctly rejected every
  unsound proposal (no weak/breaking clause was ever accepted). A negative result is valid.

**Success for THIS step.** The automated proposer runs end-to-end, every accepted strengthening is
gate-verified (never trusted from the model), and the accepted count is reported with the exact
clauses. Accepted clauses are candidate spec fixes for the imported benchmark tasks, not training
data; nothing the model emits is trusted without the interpreter gate.

## Result (measured 2026-10-16)

Proposer run over the 6 under-constrained t/humanevaldafny specs with Fable (`~/.local/bin/fable`);
every accepted clause passed spec_refine.check (real body still valid, survivors strictly reduced).
All 6 strengthened — 4 to strength 1.0, 2 partial:

  is_prime            0.96 -> 1.00  (1 -> 0)    result ==> k >= 2   (model re-derived the hand clause)
  can_arrange         0.93 -> 1.00  (2 -> 0)    pos >= -1
  make_palindrome     0.89 -> 1.00  (4 -> 0)    forall m in [0,len(result)-len(s)) . not is_palindrome(s[m..len(s)])
  specialFilter       0.61 -> 1.00  (13 -> 0)   forall k ... ==> exists j ... r[j]==s[k]
  generate_integers   0.49 -> 0.96  (25 -> 2)   forall x in [2,9) ... ==> exists j ...   [partial]
  parse_nested_parens 0.24 -> 0.41  (45 -> 35)  max_depth <= len(s)                      [partial]

Prediction CONFIRMED (>=1 strengthened; 6/6 improved, 4 fully). Partials are reported as partial: a
single extra conjunct did not close parse_nested_parens (needs a result<->paren-structure relation)
or generate_integers (a tighter even-in-range characterisation). Survivors across these 6 specs
dropped 90 -> 37; every real body still satisfies its strengthened spec (the gate rejected anything
that broke it). Nothing was trusted from the model. Deterministic gate test: t/test_spec_propose.py.
Persisting accepted clauses back and re-scoring the corpus false-accept floor is step 4.
