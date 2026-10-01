# The gate without a reference: what it passes, and how often that is right. Registered 2026-10-01 08:37Z

## What was found, and why it matters more than any count

The provers say a program meets its specification. They do not say the specification is what
the question asked. In evaluation that second question is put to the problem's reference
solution (`t/spec_check.py`). A person asking a question has no reference solution, so the gate
as built shows an answer when it passes the question's own tests and a proof. Counted on the
fine-tuned 4B's dev answers (the 4B on v4, every arm; `t/PREDICT-2026-10-01-several-answers.md`):

| | problems |
|---|---:|
| the gate as built passes an answer (tests and a proof by at least one kernel, none refuting) | 10 |
| of those, the specification is right and complete by the reference | 4 (113, 377, 727, 892) |
| the specification is true and weak | 4 (449, 459, 549, 634) |
| the specification is of another function that fits the question's three tests | 2 (67 the Bell numbers, by six kernels; 92 "is it undulating", by five) |

So on unseen problems this gate was right four times in ten. "Nothing it says is relied on until
it is proved" needs the thing proved to be the thing asked, and nothing in the gate checked
that without a reference.

## What it stands on

- Our own shelf, 2026-09-20: `locallm/FINDINGS-exploit-2026-09-20.md` found exactly this answer
  ("remove the whitespace" proved as "the result holds only letters and digits and is no
  longer") among the from-scratch model's clean answers, and
  `locallm/FINDINGS-completeness-2026-09-20.md` decided not to gate on it because that model's
  specifications were wrong far more often than weak. Both instruments were built then
  (`spec_check.exploit`, the mutants in `spec_check.check_task`) and left as reports.
- SAFE (arXiv:2410.15756, 3.2): a specification is usable when it holds on 80% of test cases and
  rejects 60% of mutated ones. `t/spec_quality.py` computes both from the question's own tests.
- AlphaVerus (arXiv:2412.06176): a specification a trivial program satisfies is discarded.
- Clover (arXiv:2310.17807, HTML v4 read 2026-10-01): generated code is accepted only when
  independently produced artifacts are consistent; code regenerated from the docstring is
  compared with the original **by its outputs on a set of inputs**. 87% of correct instances
  accepted, no adversarial incorrect one; stated limit: an edge case every artifact misses.
- CodeT (arXiv:2207.10397, HTML v2 read): a sample is trusted by its agreement with
  independently generated samples and tests (HumanEval pass@1 47.0 to 65.8).

## The stage (`t/spec_gate.py`)

The second artifact is a Python solution written for the same question by a model, kept only if
it passes the question's own tests in the sandbox (`t/py_sandbox.py`; model-written code runs
nowhere else). The stage is the reference check itself with that Python standing where the
reference stands (`spec_check.check_task(oracle=...)`): on 100 inputs drawn in the shapes of the
question's own examples,

1. the specification holds at the Python's output on every draw inside the `requires`, at least
   10 of them;
2. the `requires` admits at least half of the drawn inputs the Python answers (our own number:
   a real precondition excludes some draws, a `requires` cut down to the examples excludes
   nearly all; what the floor costs is measured below);
3. the specification rejects at least 60% of the mutated outputs on those draws (SAFE's floor).

An answer with no test-passing Python beside it is refused. What differs from Clover: inputs
are drawn, not shipped; no language model judges anything; one second artifact, not five.

**Checked before anything else:** with the reference's own code handed in as "the Python", the
stage returns the reference check's verdict on 57 of 57 of the answers above. The sandbox, the
value crossing and the rule add nothing of their own.

Reported beside it and deciding nothing: SAFE's scores on the question's tests alone (on the
answers above they pass 5 problems, 3 of them right) and the trivial-program check (6 passed, 4
right). Neither can see the two wrong functions; only a second artifact can.

## Measurements and predictions

The Python writer for A and B is the untrained base, Qwen3.5-4B at 4 bits (Q4_K_M) on the lab's
CPU (the card is training; llama.cpp built without GPU support): one greedy attempt and two
sampled at 0.7, the first that passes the tests is kept (`t/python_beside.py`).

**A. The ten dev problems above** (the reference's verdicts on them are known; the stage's are
not, no Python has been written for them yet).

39. The base model's Python passes the tests on at least 60 of the 100 dev problems. Falsified
    below 60.
40. Of the six problems whose only passed answers are weak or wrong, the stage shows none.
    Falsified by any.
41. Of the four right problems it still shows at least 3. Falsified below 3.

**B. At scale, on the training side.** Every stored answer to a training problem that passes its
tests and is proved by at least one kernel with none refuting: 1,038 answers over 397 problems,
of which the reference calls 823 right and complete, 43 weak, 146 wrong, 25 unsettled (fewer
than ten agreeing draws) and 1 unchecked. Counted before any Python exists for them.

42. Of the answers the stage shows, at least 95% are right and complete by the reference.
    Falsified below 95%.
43. It shows at least 70% of the answers the reference calls right and complete (Clover: 87% of
    correct instances). Falsified below 70%.
44. The half-domain floor (item 2) refuses at most 3% of the right answers that pass items 1
    and 3. Falsified above 3%.

**C. The 4B on v5's dev answers**, with its own Python (the Python-first arm now stores it), and
**D. the held-out run**: the student and the reference are each given the stage with their own
Python, and three numbers are reported for each beside the registered levels table: problems
shown, problems shown and right by the reference, and their ratio. The held-out rule itself is
not changed again; it picks the route as amended at 08:16Z.

What would make B fail for a reason that is not the idea: the base model writes the same wrong
function the `t` answer did (a shared misreading of the English; Clover's stated limit), or its
Python is right and returns a value `t` reads differently (a tuple against a list is handled; a
float that is not whole is skipped).

## Outcome of A, 2026-10-01 09:08Z: the ten dev problems

The base Qwen3.5-4B at 4 bits on the lab's CPU (about 20 tokens a second a server) wrote a
Python solution that passes the question's tests for **72 of the 100** dev problems, and for all
ten problems in question. The stage, answer by answer (57 answers):

| the reference calls it | answers | the stage shows | refused: false at the Python's answer | refused: weak |
|---|---:|---:|---:|---:|
| right and complete | 30 | 25 | 5 | 0 |
| weak | 18 | 0 | 0 | 18 |
| wrong | 9 | 0 | 9 | 0 |

By problem:

| | the gate as built | with the stage |
|---|---:|---:|
| problems with an answer shown | 10 | 3 (113, 377, 727) |
| of those, right and complete by the reference | 4 | 3 |
| shown and not right | 6 | **0** |

39. **The base model's Python passes the tests on at least 60 dev problems: holds.** 72.
40. **None of the six weak-or-wrong problems is shown: holds.** Both wrong functions (67, 92)
    fall to the Python; the four weak ones to the mutants.
41. **At least 3 of the 4 right problems are still shown: holds, at exactly 3.** The one lost is
    892 (collapse runs of spaces). The student's answer follows the reference
    (`re.sub(' +', ' ', text)`); the Python is `' '.join(s.split())`, which also treats a control
    character as a space, and a drawn input held one (code point 30). The second artifact is a
    slightly different function on an input no question would contain, and the stage cannot tell
    which of the two is the question's.

One thing the reference check cannot see and the stage can: on problem 113 ("does the string
represent an integer") the reference returns None for the empty string, so the reference check
skips that input. The Python returns False there, and four of the twelve answers the reference
calls right say something else. They are refused; the other eight are shown.

**Reading.** On these answers the gate as built was right 4 times in 10; with the stage it is
right 3 times in 3 and shows one right answer fewer. That is ten problems. B is the measurement
with enough answers to carry a percentage.
