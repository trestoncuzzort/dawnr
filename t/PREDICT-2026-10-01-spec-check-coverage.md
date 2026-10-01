# The specification check gives up, or asks the wrong reference: a repair, registered 2026-10-01 04:04Z

## What was found, by counting where proved answers stop

`t/spec_check.py` decides whether an answer's specification is the problem's: it draws inputs,
calls the problem's own Python solution, and asks whether the `ensures` holds of what the
solution returned. An answer is counted, and admitted for training, only on `agrees`. Two faults
in how it calls that solution, both found on 2026-10-01 while tracing answers that every kernel
had proved and no table counted:

1. **A list of strings is handed over as lists of integers.** `t` represents a string as a
   sequence of code points. Since 2026-09-30 the check passes a `str` where the problem's
   assertion passes a `str` literal; it does not do so for a LIST of strings. MBPP 91's solution
   is `any(sub_str in s for s in str1)`; handed lists of integers it asks whether a string is an
   ELEMENT of a list of numbers and answers False. Eight held-out answers to that problem are
   proved by up to six kernels, pass its tests, state `exists i . words[i].find(sub) != -1`, and
   read `disagrees` at a witness built that way. 135 of the pool's 3,003 problems pass a list of
   strings as an argument: 5 held-out (74, 91, 201, 757, 947, all on the clean 200), 10 dev, 120
   on the training side. Every verdict on them so far, `agrees` as much as `disagrees`, was
   computed against the wrong function. The draws for such an argument are also integers from
   -4 to 4, where every other kind is drawn in the shape of the problem's example.
2. **One draw ends the whole check.** If the solution returns a float on one drawn input
   (MBPP 78 returns `(n + 1) / 2`, which Python makes `3.0`), returns None (MBPP 605 on small
   inputs), or does not finish in five seconds (a recursive Catalan number), the check stops with
   `reference result has no t value` or `reference did not finish` and the answer is never
   counted. On the training side 550 of 2,666 checked tasks ended as "could not be checked"; of
   the 672 tests-passing training answers some kernel proves, 17 stop here. On the clean 200,
   six problems (78, 313, 583, 605, 814, 935) have a proved, tests-passing answer and nothing
   counted for this reason; four of them have an answer proved by all seven kernels.

## The repair, and what it stands on

EvalPlus (github.com/evalplus/evalplus, `evalplus/gen/type_mut.py`, `gen/util/__init__.py`,
`eval/__init__.py`; arXiv:2305.01210) grows test inputs for these same benchmarks. Its rules,
read from the source: types are kept element by element (a list of str stays a list of str); a
new input is kept only if the ground truth runs on it within the time limit without raising,
otherwise it is dropped and generation goes on; outputs are compared with Python equality, so
`3.0 == 3`.

1. A position where the problem's assertion passes a list of str literals gets a list of `str`,
   and its draws are shaped like the problem's example (row count, row length and code points
   near the example's), as every other kind already is.
2. A draw on which the solution does not finish, or returns a value `t` cannot represent (None,
   a float that is not a whole number), is skipped and counted; the check goes on. A float equal
   to an integer is read as that integer, which is how the problem's own assertions compare it.
   If no draw gives a usable value the status stays what it was.
3. Nothing else changes: 100 draws, seed 1, the same `ensures` evaluation, the same mutation
   probes, the verdict bound to the task's hash. An `agrees` records how many draws agreed and
   how many were skipped and why.

## What is re-checked, and how

Only answers the faults touch: every answer to a problem with a list-of-strings argument, and
every answer whose recorded status is `reference result has no t value` or `reference did not
finish`. They are checked in runs of their own, so no other answer's draws move (the check
threads one random generator through a run). Every other verdict stands as measured. The
registered tables are not rewritten: counts under the repaired check are printed beside them and
labelled, and a published count that changes gets an entry in `CORRECTIONS.md`.

Order: this file is committed before the repaired check has been run on any answer.

## Predictions

17. On the clean 200, at least 3 of the 11 touched problems (78, 313, 583, 605, 814, 935 and 74,
    91, 201, 757, 947) end with an answer that passes the tests, is proved by at least one kernel
    with none refuting, and agrees under the repaired check. Falsified by fewer than 3.
18. The fault cut both ways: on the 135 list-of-strings problems, at least one answer that read
    `agrees` reads `disagrees` once the solution is called with strings. Falsified if none
    does. (No prediction on the net change in training rows.)
