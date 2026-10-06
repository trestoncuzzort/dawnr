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

## Outcome, 2026-10-05 11:40Z (K1 to K5)

Run on the lab from commit 9278405e, one llama-server (build b11325, the base model at 4 bits), 300 problems, four
requests a problem. `locallm/calc_eval.py report`:

| arm | shown, of 300 | right | right, of shown | wrong shown |
|---|---|---|---|---|
| prose | 300 | 279 | 93.0% | 21 |
| one | 284 | 239 | 84.2% | 45 |
| agree | 207 | 197 | 95.2% | 10 |
| calc | 203 | 192 | 94.6% | 11 |

- **K1: holds, at its upper edge.** `prose` is right on 93.0% (the range was 70% to 93%).
- **K2: fails.** `one` is right on 239 of 300, 13.3 points fewer than `prose` (the bar was 5).
- **K3: fails on the share right.** `calc` shows an answer for 67.7% (the bar was 60%), and 94.6% of them are right
  (the bar was 95%).
- **K4: holds.** Of the 21 problems `prose` gets wrong, `calc` shows a wrong answer for 5 (24%; the bar was 25%),
  the right one for 6, and refuses 10.
- **K5: fails on its first clause.** `calc`'s share right among shown is 0.6 points below `agree`'s; it shows 4
  fewer answers.

**What the registered rules say.** K3 fails on the share right: the answers are called "computed exactly from the
working shown" and nothing more. K5 fails: the rule about the question's own numbers becomes a note printed beside
the answer, not a filter. K2 fails: the problems were read by hand before anything was changed.

**The 48 problems prose gets right and the first working does not, read by hand** (twelve in full, all 48 tallied).
In 14 the working could not be computed, and in every one the model was trying to do what the grammar does not
offer: algebra (`amy = jackson + 5` with `jackson` not yet known), a loop or a condition (`while = budget - ...`,
`if = 0`, written as names because only assignments are allowed), or it initialised `answer = 0` and the grammar,
which ends a working at its first assignment to `answer`, stopped it there. In the other 34 the working computed a
wrong number from a set-up the prose answer gets right: held to assignments, the model starts writing lines before
it has reasoned about the problem. Whole-number division written where a fraction was meant (`2 // 5`) is in 19
of the 48 but decides only one of them. The grammar is not costing arithmetic; it is costing the reasoning.

## What the command does now, registered 2026-10-05 11:46Z before it is run on any new problem (K6 to K9)

The two routes are made to check each other (`calc.settle`): the model answers once in prose, step by step, with
the `prose` arm's prompt word for word; it is asked three times for a working under the same grammar, without
being shown its prose; the number the prose ends on is shown only when at least one working, computed exactly,
gives the same number, and that working is printed. A number the question does not state is noted beside the
working and no longer disqualifies it.

On the 300 problems above, computed afterwards from the replies already kept (so the rule was chosen with these
in view and this is not a result): `settled` shows 269 with 262 right (97.4%), 7 wrong; with two workings
required (`settled2`) 236, 232 right (98.3%), 4 wrong.

**The sample.** 300 problems of GSM8K's test split, seed 2027, none of them among the first 300. Same model,
server build, prompts, grammar and temperatures. The four arms above are scored again, with `settled` and
`settled2`.

- **K6, more answers than the first build.** `settled` shows an answer for at least 80% of the 300.
- **K7, and they are more often right than the model alone.** At least 96% of the answers `settled` shows are
  right, and at least 2 points more than `prose`'s share right on the same problems.
- **K8, it withholds where the model errs.** Of the problems `prose` gets wrong, `settled` still shows a wrong
  answer for at most half.
- **K9, whether a second agreeing working is worth its refusals.** `settled2` shows at most half as many wrong
  answers as `settled`. (On the first sample: 4 against 7, which is not half.)

What each outcome changes:

- K6 and K7 hold: `dawnr calc` is documented with this sample's numbers for `settled`, beside `prose`'s.
- K7 fails: the README says the command's answers are about as often right as the model's own and that what it
  adds is the working, computed exactly, printed beside the answer.
- K8 fails: said in DISCLAIMERS with the count; a misreading shared by the reasoning and the working is the known
  way this check is blind.
- K9 holds: `--needed 2` becomes the default. K9 fails: it stays 1, and `--needed 2` is documented as the stricter
  setting with its measured cost.

## Outcome, 2026-10-05 12:31Z (K6 to K9)

Run on the lab from commit 4f916515, two llama-servers (build b11325, the base model at 4 bits), 300 problems none
of which was in the first 300. `locallm/calc_eval.py report`:

| arm | shown, of 300 | right | right, of shown | wrong shown |
|---|---|---|---|---|
| prose | 300 | 282 | 94.0% | 18 |
| one | 283 | 226 | 79.9% | 57 |
| agree | 204 | 195 | 95.6% | 9 |
| calc (the first build) | 189 | 182 | 96.3% | 7 |
| settled (`dawnr calc`) | 260 | 254 | 97.7% | 6 |
| settled2 | 223 | 219 | 98.2% | 4 |

- **K6: holds.** `settled` shows an answer for 260 of the 300 (86.7%; the bar was 80%).
- **K7: holds.** 97.7% of them are right (the bar was 96%), 3.7 points above `prose` on the same problems (the bar
  was 2).
- **K8: holds.** Of the 18 problems `prose` gets wrong, `settled` still shows a wrong answer for 6 (a third; the
  bar was at most half).
- **K9: fails, as the first sample suggested.** `settled2` shows 4 wrong answers against 6, which is not half, and
  37 fewer answers. `--needed` stays 1; `--needed 2` is the stricter setting at that cost.

**What `dawnr calc` is measured to do, then.** Against the same model simply answering in words: of every three
wrong answers it shows one, and it withholds about one right answer in ten (254 against 282). The first sample,
read afterwards, gave 269 shown and 97.4%. The six wrong answers that get through are problems the reasoning and
the working misread the same way, which no agreement between them can see.

