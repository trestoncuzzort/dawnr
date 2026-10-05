# `dawnr calc`: arithmetic written down, computed exactly, shown only when workings agree; registered before any measurement

Registered 2026-10-05 09:22Z. `locallm/calc.py` is written and unit-tested and has been run on three questions typed
by hand (one of them GSM8K's first test problem, as a plumbing check; it is not in what is scored unless the seed
draws it, and nothing was changed after seeing its answer except the grammar's ending, which had let the model run
on after its result). It has been run on no sample of a benchmark. Plan row 5 of
`internal/PLAN-2026-10-05-usable-for-everyone.md`; research receipt f8e8dafb74c0.

## What is measured

GSM8K's test split (arXiv:2110.14168), 300 problems drawn with seed 2026 (`locallm/calc_eval.py`). One model: the
base Qwen3.5-4B at 4 bits, as the installer puts it. For each problem the model is asked once in prose, step by
step, at temperature 0, and three times for a working under `calc.py`'s grammar (one at 0, two at 0.7).

| arm | what is shown |
|---|---|
| prose | the number the step-by-step answer ends on: the model answering as it does |
| one | the first working, computed exactly (PAL, arXiv:2211.10435) |
| agree | shown when at least two of the three workings compute and all that compute give one number |
| calc | `dawnr calc`: as agree, and a working that uses a number the question does not state is not used |

Right means equal to the problem's final number.

## Predictions

- **K1.** `prose` is right on between 70% and 93% of the 300.
- **K2, the interpreter does not cost answers.** `one` is right on no fewer than `prose` less 5 points.
- **K3, what is shown is right.** `calc` shows an answer for at least 60% of the 300, and at least 95% of the
  answers it shows are right.
- **K4, it refuses where the model errs.** Of the problems `prose` gets wrong, `calc` shows a wrong answer for at
  most 25%.
- **K5, the question's own numbers.** `calc`'s share right among shown is not below `agree`'s, and `calc` shows at
  most 15 points fewer of the 300 than `agree` does.

## What each outcome changes

- K3 holds: `dawnr calc` is documented with these numbers.
- K3 fails on the share shown (under 60%): the rule becomes "two of three agree" and is measured again from the
  same replies before it is documented, as a new line in this file, marked as chosen after seeing the first result.
- K3 fails on the share right (under 95%): the README states the measured share and does not call the answers
  checked beyond "computed exactly from the working shown".
- K5 fails: the rule about the question's own numbers becomes a note printed beside the answer, not a filter.
- K2 fails: the grammar or the prompt is costing set-ups the model gets right in prose; read ten such problems by
  hand before changing anything.

## Not measured here

Questions that are not grade-school arithmetic (interest over time with compounding, units, dates); a person's
own phrasing. The gate does not know the right reading of a question; the working is printed for that.
