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

## Outcome, 2026-10-05 (V1 to V3)

**V1: holds on the count, fails on the comparison.** `verify` (three specifications, three bodies a supported
one, the published model at Q8_0 on a lab card, Dafny alone, the gate with the larger-input rule; commit 35c2b88e)
found a proved twin for **9 of the 111** (the bar was 5). `ask` in W4 showed an answer for 12, so "at least as
many as `ask`" fails. The first batch found no sandbox in its fresh checkout and refused all 111 without asking
the model anything; it is discarded and the run of record is the second, which was the same script with the lab's
sandbox named.

Where `verify` stopped: for 88 of the 102 it refused, no specification the model wrote held at the function's
answers and pinned them down; for 14, no body was proved. Of the specifications refused for being false at the
function's own answer, 80 were false at one of the problem's given examples and 11 at an input drawn afterwards;
about 60 more did not parse. The two commands agree on 7 problems; `verify` alone reached 2 (106, 206) and `ask`
alone 5.

The comparison is not like for like, in three ways that were not foreseen: W4 ran on the desktop's CPU and
`verify` on a lab card (the same weights sample differently); W4's gate predates the larger-input rule (re-judged
from what it recorded, 11 of its 12 answers would still be shown); and when the 12 questions W4 answered were
asked again on the lab with today's code, 7 were shown. V4 below compares the two commands in one run.

**One refusal is worth reading.** Problem 889's words are "reverse each list in a given list of lists" and its
reference solution sorts each list in descending order. Given that function and those words, `verify` refused:
every specification the model wrote from the docstring is false at an answer the function gives,
`reverse_list_lists([[2, -1, -3], [-4, 2, 2], []]) == [[2, -1, -3], [2, 2, -4], []]`, "either the model misread
the docstring, or the function does not do what it says". The function does not do what it says. `ask`, given
the words alone, proved a program that reverses.

**V2: holds.** 16 certificates were replayed on a machine other than the one that wrote them, with that machine's
own Dafny (`t/certificate_eval.py`): the 9 `verify` wrote on the lab, replayed on the desktop, and the 7 `ask`
wrote when W4's 12 answered questions were asked again on the lab with today's code, replayed on the desktop.
All 16 read `REPRODUCED`.

A first attempt at the `ask` half is recorded because it failed informatively. Certificates were assembled today
from the answers W4 had recorded that morning, by the function `--certificate` calls; 6 of those 12 read `FAILED`
on the lab, every one at the step that runs the recorded Python beside the proved program. The Python W4
recorded was written before the hand-back refused inputs outside what was proved, so it no longer answers as
today's check requires. Those were not certificates any command wrote, and the replay refused them for a real
difference; they are not counted in V2.

**V3: holds.** Each of the 16 was forged three ways with every digest taken again: 16 with the gate's own
sabotaged twin as the body, 16 with every `ensures` replaced by `r == r`, 13 with the recorded Python made to
answer one off (three carry no Python). All 45 read `FAILED`; none read `REPRODUCED` or `UNDECIDED HERE`. The
twin forgeries stopped at a recorded test (15) or at an input where the program breaks its own specification
(1), before any prover ran; the empty specifications at the measurement that the specification says too little;
the Python forgeries at the comparison with the proved program.

## The command with both routes, registered 2026-10-05 12:02Z before it is run on the panel (V4 to V6)

By the rule above ("V1 fails: ... `verify` then asks the one-shot question as `ask` does, with the person's
function standing where the independently written Python stands, and is measured again before it is
documented"), `verify` now asks first for five whole answers from the docstring and the examples, the function
not shown (`verify_py.by_answers`): an answer's specification must hold at the function's own answers and pin
them down, the program must answer as the function does, and it must be proved. When none is shown it writes the
specification first, as V1 measured (`by_specification`), because that route reached two functions the other
command did not.

**The run.** The wider 111, the published model at Q8_0 and the base at 4 bits on one lab card, Dafny alone,
today's gate, one commit for both commands: `ask` as in W4 (five answers, consistency 5), and `verify` with the
problem's reference as the function, its words as the docstring and its tests as the examples.

- **V4, a function you already have is at least as easy as a question.** `verify` finds a proved twin for at
  least as many of the 111 as `ask` shows an answer for in the same run, and for at least 10.
- **V5, the function is a better oracle than a model's Python.** The first route alone shows at least as many as
  `ask` does: the question to the model is the same, and what the specification is held against is the
  function itself where `ask` has only a Python solution the base model wrote.
- **V6, the second route still earns its place.** Of the twins `verify` finds, at least one comes from the
  specification route.

What each outcome changes:

- V4 holds: `verify` is documented as the way in for people who already have code, with this run's two counts.
- V4 fails: the README says `verify` is not easier than `ask` and what it adds is the comparison with your own
  function (the input where the two differ, or the docstring the code does not keep).
- V5 fails: read the questions `ask` answers and the first route does not, by hand, before changing anything.
- V6 fails: the specification route is removed (it costs up to twelve model calls a function).

