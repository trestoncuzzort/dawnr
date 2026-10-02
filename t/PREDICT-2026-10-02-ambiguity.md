# Several Python solutions, not one: registered 2026-10-02 08:01Z, before any sample is drawn

## Why

The gate without a reference shows 56 answers across the three seeds' held-out sets, and 45 are right (80%,
counted against MBPP+'s corrected references where they keep the problem's tests, t/PREDICT-2026-10-02-reference-plus.md).
Of the 11 wrong, 768 is shown wrong on every seed, and read by hand it is the gate's blind spot: "check for odd
parity of a number" means an odd count of one bits, both the student and the independent Python read it as "the
number is odd", and the problem's three tests (13, 21, 18) cannot tell the readings apart. One Python solution
cannot disagree with a specification that shares its misreading.

ClarifyGPT (Mu et al., arXiv:2310.10996) detects such requirements with a code consistency check: sample several
solutions at temperature 0.8, run them on generated inputs, and call the requirement ambiguous when their outputs
differ (140 of MBPP-sanitized's 427 problems were). Here the inputs are the specification check's own draws.

## The change

`spec_gate.judge_all`: the answer is held to the greedy test-passing Python solution as before, and then to every
further distinct test-passing solution sampled at 0.8 (`python_beside.py --samples 5`, the base at Q4_K_M through
llama-server, as `dawnr` runs it). It is refused if any of them finds the specification false at its answer; the
refusal names that input and the other solution's answer, the test that would settle the question. An extra
solution's own domain or a weak check does not count against the answer.

## The measurement

The 28 problems shown on any seed get five samples each. Every shown answer is judged again with `judge_all`; the
rest of the gate file is unchanged (an answer the gate refused stays refused). Counted against the corrected
references, beside the original ones.

115. 768 is refused on all three seeds.
116. At least 4 of the 11 wrong answers shown are refused.
117. At most 5 of the 45 right answers shown are refused.

## The 11 wrong answers, read by hand (2026-10-02 08:06Z, after registering and before any sample; one reader)

| problem | seeds | the answer | the reference | read as |
|---|---|---|---|---|
| 768 odd parity | 1, 2, 3 | the number is odd | an odd count of one bits | the answer misreads the question |
| 680 increasing trend | 1, 2 | strictly increasing | `sorted(s) == s`, equal neighbours allowed | ambiguous; either reading fits the tests |
| 665 shift the first element to the end | 1, 3 | `s[1:] + [s[0]]` | moves every copy of the first element | the reference's own reading is the odd one |
| 891 same number of digits | 2, 3 | `len(str(a)) == len(str(b))` | float division; says 9 and 11 have the same length | the reference is wrong |
| 454 a word containing 'z' | 3 | contains a z | needs a character after the z ("fz" is not matched) | the reference is narrower than its question |
| 644 reverse up to position k | 2 | at k = 0 nothing is reversed | `input[-1::-1] + input[0:]` at k = 0 | an input outside what the question means |

So on this reading 5 of the 56 shown are wrong (91% right), not 11 (80%). The registered count stays the
reference's; this table is reported beside it and is not a measurement.

## Outcome, 2026-10-02 08:34Z

Five samples at 0.8 for each of the 28 problems gave 116 distinct test-passing solutions (the base at Q4_K_M on
the desktop CPU). Every shown answer judged again (`~/scratch/ambiguity/report.json`):

| three seeds, at least one kernel | shown | right | right share |
|---|---:|---:|---:|
| one Python solution (before) | 56 | 45 | 80% |
| every test-passing sample too (after) | 47 | 41 | **87%** |
| the same, against MBPP's original references | 56 -> 47 | 44 -> 40 | 79% -> 85% |

115. **768 refused on all three seeds: holds.** A sampled solution reads "odd parity" as an odd count of one bits
     and answers f(8) with True.
116. **At least 4 of the 11 wrong refused: holds** (5: 768 three times, 644, 454 on seed 3).
117. **At most 5 of the 45 right refused: holds** (4: 53 twice, 375, 454 on seed 2).

The four right answers were lost to sampled solutions that pass the question's tests and are wrong elsewhere:
for 53 ("are the first and last characters equal") one says a one-character string is "Not Equal"; for 375
("round to the nearest multiple") one rounds 482 down to 476 instead of to 483. In `dawnr` such a refusal ends with
the input and asks for a test that settles it, so the cost is a question to the person, not a wrong answer shown.
On the hand reading above, 2 of the 47 shown are wrong (680 twice: strict or not), 96%.

`dawnr ask` now holds every answer to five sampled solutions (`--consistency 5`).
