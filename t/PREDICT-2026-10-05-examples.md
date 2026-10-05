# `dawnr ask` without tests: examples proposed for the person to approve; registered before any panel question is asked

Registered 2026-10-05 12:15Z. `t/examples.py` is written and unit-tested, and has been tried by hand on four plain
questions against the base model (a palindrome, counting even numbers, a sum up to n, the largest of a list); on the
last the drafts disagreed about `[1, 2, 3]` and the question was put. It has been run on no panel question.
Research receipt 3a589b025171; shift 2 of `internal/RESEARCH-2026-10-05-what-to-steal.md`.

## What it is for

`dawnr ask` holds everything to `assert f(arguments) == value` lines, and a person who does not program cannot
write them. TiCoder (arXiv:2404.10100) shows the person the test that splits the model's candidate programs most
evenly and prunes by the answer. Here the base model writes five Python drafts from the words alone, each is run in
the sandbox on small drawn inputs, the input the drafts split on most evenly is put first, and what the person
accepts or types becomes the tests the existing gate uses. At most four questions; once the drafts no longer
disagree it stops at three approved examples.

## What is measured

The wider 111 (`heldout_audit.wider_clean()`), each problem's words alone: its tests are withheld from the model
and from the flow. **The person is the problem's reference solution** (TiCoder's idealised user): asked what an
input should give, it answers with what the reference returns, and where the reference raises it says the input
is not allowed. Then `ask`'s gate as it stands (five answers, consistency 5, Dafny alone), the published model at
Q8_0 and the base at 4 bits on a lab card. The comparison is `ask` given the benchmark's own tests, on the same
card from the same commit's gate (the `ask` half of V4 in `t/PREDICT-2026-10-05-verify-python.md`).

- **E1, examples can be made.** For at least 70% of the 111 questions the flow ends with at least two approved
  examples. (It ends with none when no draft runs, or when the drafts take other inputs than the reference does,
  so that the reference can answer none of the questions.)
- **E2, what is lost without written tests.** `ask` with the approved examples shows an answer for at least 60% as
  many questions as `ask` with the benchmark's tests shows, and for at least 5.
- **E3, what is shown is still right.** Of the answers shown this way, at least 70% agree with the reference on
  drawn inputs with a complete specification (the scorer of W4, `~/scratch/wider/score.py`).

## What each outcome changes

- All three hold: `dawnr ask "QUESTION"` with no `--test` is documented as the way in for someone who does not
  write tests, with these counts beside the with-tests counts, and the same dialogue goes into the page.
- E1 fails: the drafts' prompt is the fault (they do not take what the question's function takes); read twenty by
  hand before changing it.
- E2 fails: said with the counts; the flow stays as an option and the README leads with `--test`.
- E3 fails: examples drawn on small inputs pin the meaning down less than a benchmark's tests do; the flow then
  asks more questions before it is documented, and is measured again.

## Not measured here

A real person. The reference never hesitates, never misreads a call, and knows the answer for every input; a
person will approve an example that is wrong, or not know. TiCoder's user study (15 programmers) is the nearest
evidence, and it is not about people who do not program.
