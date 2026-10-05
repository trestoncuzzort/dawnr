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

## What the first 31 questions showed, and the flow as changed (2026-10-05 13:55Z)

The registered run is still going and is read whole when it ends. Its first 31 questions (in id order) were read
by hand, as the rule for a failing E1 says, and E1 is failing there: **8 of 31** ended with two or more approved
examples and 12 with none. Why, from the drafts themselves (155 of them):

- **50 of the 155 drafts were empty.** The request ended "It reads no input and prints nothing", and a third of
  the replies were a function that takes nothing or does nothing (`def swap(a: int, b: int) -> None: pass`). The
  fault was the sentence.
- **The reference could not stand in for the person.** The words of a benchmark problem do not say what the
  function is called or takes; in 8 of the 31 the drafts took other parameters than the reference does, so it
  rejected every input put to it. TiCoder gives the model the function header with the words (arXiv:2404.10100,
  section III); this measurement had not.
- **Annotations went unread**: tuples, `List[Tuple[int, ...]]`, type variables, a helper beside the function.
- **The inputs asked first were the ones half the drafts fail on**, each was answered "not allowed", and the four
  questions ran out. TiCoder's score leaves the failing drafts out; the first form counted them as a group.
- **The dialogue ended as soon as no draft agreed with the person**, with one example approved.

Changed, in `t/examples.py` and `t/verify_py.py`: the request reworded; annotations read by structure (lists and
tuples of any depth, a type variable as numbers; Hypothesis's `from_type` is the model, receipt ca5ca66b9df4);
drafts that differ only in tuple or list run side by side; the header is given when the caller has one; inputs
every draft answers come first and the ones some draft fails on last; with no draft left the plainest inputs are
still put; and the model is asked for six calls someone would try, of which only the inputs are kept (no small
drawn matrix is a magic square, and a result the model wrote is a guess). On the same 31 questions, flow only:
27 with two or more examples before the suggested inputs were added, and 21 of the 22 finished with them when
this was written.

## E4 to E6, registered before any question after the 31st has been read under either form

The 80 questions after the 31st of the wider 111, the changed flow from this commit, the reference as the person
and its header given, then `ask`'s gate as it stands (five answers, consistency 5, Dafny alone) on a lab card.
The comparison is `ask` with the benchmark's own tests on the same 80 (the run of V4, same gate; it showed an
answer for 6 of them, known when this was written).

- **E4, examples can be made.** At least 75% of the 80 end with two or more approved examples.
- **E5, what is lost without written tests.** `ask` with the approved examples shows an answer for at least 4 of
  the 80.
- **E6, what is shown is still right.** Of the answers shown, at least 70% agree with the reference on drawn
  inputs with a complete specification (the scorer of W4).

All three hold: `dawnr ask "QUESTION"` with no `--test` is documented as the way in for someone who does not
write tests, with these counts and the note that the measurement gave the function's name and parameters. E4
fails: the failures are read by hand before anything else changes. E5 or E6 fails: said with the counts; the
dialogue stays, and the README leads with `--test`.

