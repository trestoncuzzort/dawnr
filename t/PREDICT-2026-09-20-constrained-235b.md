# Does decoding against t's grammar help the strongest model available?

**Written 2026-09-20, before the arm ran.** `t/out/spec-experiment/qwen235-heldout-g1`
did not exist when this was written. The arms, the metrics and the decision rule
below are fixed now.

This extends `t/PREREG-2026-09-18-constrained.md`, whose decision rule ("the number
that decides this is **clean answers**, not parse rate") is adopted unchanged, to
the largest model this project has run.

## Why now

WS-21 lists three moves and the first is "a grammar the generator decodes against".
WS-22 step 22.4 is the same step. The existing evidence is a 30B pair, and it is
strong on syntax and silent on the thing that matters:

| arm | n | parse fail | check_wf fail | well formed |
|---|---:|---:|---:|---:|
| `qwen3-coder-30b-apps-s1`, unconstrained | 1130 | 803 (71.1%) | 138 | 189 (16.7%) |
| `qwen3-coder-30b-apps-g1`, constrained | 213 | **2 (0.9%)** | 146 (68.5%) | 65 (30.5%) |

Constrained decoding all but removes the parse wall and the failures move to
well-formedness. That arm is incomplete, 213 of 1,133, and the model is not the one
now loaded.

## The arms

Same 232 held-out problems (`t/out/loop/eval-ids.txt`), same model
(`QuantTrio/Qwen3-235B-A22B-Instruct-2507-AWQ`), pool v3, prompt v3, temperature 0,
seed 1, `num_ctx` 8192, `num_predict` 8192. **Nothing differs but the constraint.**

| arm | tag | generation |
|---|---|---|
| control | `qwen235-heldout` | already generated, unconstrained |
| constrained | `qwen235-heldout-g1` | the same request plus `--grammar t/t.gbnf` |

The control, measured: 67 well formed, 53 passing their tests, **11 clean**, 11/53
conversion (21%), 8 surviving the specification check, 140 parse failures, 25
well-formedness failures.

## Predictions

1. **Parse failures fall below 10, from 140.** Falsified at 10 or more. This is
   guaranteed by construction if the constraint is applied at all, so it is a
   check that the experiment ran, not a result. If it fails, the grammar was not
   passed or vLLM ignored it, and nothing else here may be read.
2. **Well-formed answers land between 90 and 160, from 67.** Falsified outside.
   The 30B roughly doubled, 16.7% to 30.5%, but the 235B *starts* at 28.9%, which
   is already the level the constraint lifted the 30B to. So the headroom is
   smaller and a doubling should not be expected. Below 90 means the constraint
   buys almost nothing on a model that already writes mostly-parseable `t`; above
   160 would be a bigger effect than the 30B pair supports.
3. **Well-formedness failures rise above 60, from 25.** Falsified at 60 or fewer.
   The 30B's moved from 12.2% to 68.5% of answers: a constraint that forbids
   unparseable output does not make the output *mean* anything, so the failures
   should relocate rather than vanish.
4. **Clean answers are at least 11 and at most 25.** This is the prereg's deciding
   metric and the prediction that matters. Falsified below 11, which would mean the
   constraint actively costs clean answers, or above 25, which would be a larger
   gain than any syntax intervention here has produced. My honest expectation is a
   small gain, 12 to 16, because the 2026-09-18 preregistration already named the
   failure mode: a constrained model can be "syntactically perfect, semantically
   empty", and locallm is the existence proof, writing `t` the parser accepts 98%
   of the time and passing 2 tests in 464 answers.
5. **Conversion does not improve.** The control converts 11 of 53, 21%. Falsified
   if the constrained arm converts a higher *percentage*. The constraint acts on
   notation and conversion is a property of whether the specification says what the
   problem asked, so there is no mechanism by which decoding should move it. If it
   does move, something other than the constraint changed.

## What would make this a reason to change the pipeline

Prediction 4 landing at 16 or above, with prediction 5 held. That would mean the
constraint buys clean answers through coverage alone — more problems reaching the
gate — without pretending to improve specification quality, and grammar decoding
should then become the default for every generation arm.

If prediction 4 lands at 11 or 12, the constraint is a wash on this model and the
honest conclusion is that the parse wall was never the binding constraint for the
235B, only for smaller models. WS-21 would then be closed as measured rather than
implemented, and WS-21 move 3 ("whether anything can hold both ends") becomes the
live question.

## What this cannot settle

Cost. xgrammar's mask, measured on this grammar today, is 101.3 ms per token
against llguidance's 0.602 ms (`t/FINDINGS-constrained-decoding-2026-09-20.md`).
This arm runs on whichever backend the loaded server has and its wall-clock is
therefore not a measurement of what constrained decoding must cost. Throughput is
a separate arm on a server started with `--structured-outputs-config.backend
guidance`, and it is not this one.
