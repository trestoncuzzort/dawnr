# `dawnr verify` and the certificate: registered before either is run on a panel

Registered 2026-10-05 09:05Z. Two builds of `internal/PLAN-2026-10-05-usable-for-everyone.md` (rows 1 and 3) are
written and unit-tested; nothing below has been measured. What has been run: `dawnr prove largest.t --certificate`
and `dawnr check` once each on the desktop (reproduced in 6 s; a wrong body with fresh digests failed in 1 s), and
`dawnr verify` on no panel problem.

## What is measured

**The panel** is the wider 111 (`heldout_audit.wider_clean()`, pool v7), the panel W4 of
`PREDICT-2026-10-05-wider-reader.md` asks through `dawnr ask`. No training row of any published model matches one
of its problems.

**The model** is the published one (dawnr v5, `student-v5` at Q8_0, as the installer puts it), with Dafny alone as
the prover, the condition of a fresh install.

**`verify`'s input** for a problem is what a person who had already written the function would hold: the
problem's reference solution as the Python file, the problem's own tests as the examples, the problem's words as
the docstring. Three specifications and three bodies a supported specification at most (`t/verify_py.py`
defaults).

**The comparison** is W4 on the same panel, model, quantisation and prover: `dawnr ask` given the words and the
tests and no solution.

## Predictions

- **V1, a function you already have is easier than a question.** `verify` shows a proved twin for at least as many
  of the 111 as `ask` shows an answer for, and for at least 5. (The reason to expect it: the model is shown a
  correct solution at both stages, the rows it was trained on for exactly that, and no question is refused as
  ambiguous because the function says what is meant. The reason it could fail: `ask` draws five whole answers and
  `verify` at most three bodies a specification.)
- **V2, a certificate travels.** Every certificate these runs write (`verify`'s and, from a rerun of W4's shown
  answers with `--certificate`, `ask`'s) is replayed by `dawnr check` on a machine other than the one that produced
  it, with that machine's own Dafny: every one reads `REPRODUCED`. An `UNDECIDED HERE` counts against the
  prediction; a `FAILED` is a defect in the certificate or the check and is read by hand.
- **V3, an altered certificate does not pass.** Each of those certificates is forged three ways, every digest taken
  again so that only the content is wrong: (a) the program's body replaced by the gate's own sabotaged twin of it
  (`harness.twin_for`, a near miss by construction); (b) every `ensures` replaced by one that says nothing
  (`r == r`) with the body and the recorded measurements kept; (c) the recorded Python given an off-by-one. No forged certificate reads
  `REPRODUCED`. For (a), at least 90% read `FAILED` and the rest `UNDECIDED HERE`.

## What each outcome changes

- V1 holds: `verify` is documented as the way in for people with code, and its route (specification first, the
  function shown) is the candidate for `ask` itself wherever a tested Python solution exists.
- V1 fails: the specification-first route with three draws is weaker than five whole answers; `verify` then asks the
  one-shot question as `ask` does, with the person's function standing where the independently written Python
  stands, and is measured again before it is documented.
- V2 or V3 fails: the certificate is not yet what the README says it is; the README's paragraph is corrected the
  same day and the defect fixed before any other build.

## Not measured here

Whether a person reading the specification catches a function that does not do what they meant. The check cannot
know intent; the output says so, and the one planted case tried by hand (a sum that stops one short of its
docstring) is reported with its output, as an anecdote.
