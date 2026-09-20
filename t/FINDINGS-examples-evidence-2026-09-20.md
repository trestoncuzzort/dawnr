# The problem's own examples as a second evidence path: +15, and two falsified predictions

Predictions registered in `t/PREDICT-2026-09-20-examples-as-evidence.md` before
any column was read. Three held, **two were falsified**, and one of the two is the
more useful result.

## The three numbers, and why they differ

| build | positives | what it is |
|---|---:|---|
| `sft-r6.jsonl`, published 2026-09-18 20:23 | **87** | built before the evidence gate existed |
| same 35 tags, current gate, draws only | **75** | the honest figure under the gate as it stood this morning |
| same 35 tags, current gate + examples path | **90** | this change |

The 87 was not wrong when it was written; the gate that requires a current,
agreeing specification-check result landed in `899045f6` at 2026-09-19 05:36,
nine hours after that file was built. Rebuilding today under the gate drops 14
answers and gains 2, which is the 75.

**The 90 is a strict superset of the 87.** All 87 return, plus
`apps_3582__is_digit`, `mbpp_354__tn_ap` and `mbpp_498__gcd`, which gained
reference-draw evidence that did not exist on 2026-09-18.

## What the 14 were, and why they were dropped

Every one is a string problem: `remove_splchar`, `replace_blank`,
`remove_whitespaces`, `remove_lowercase`, `fill_spaces`, `replace_spaces`,
`remove_extra_char`, `replace_specialchar`, `is_allowed_specific_char`,
`countSegments`, `is_vowel`, `switcheroo`, `remove_chars`, `dog_age`. Each passed
its problem's own tests and read `verified / refuted` in all seven kernels.

`t` has no string type, so `check_task` cannot draw an argument the problem's
reference solution will accept, and the status reads `no valid draws`. They were
rejected for **want of evidence, not for being wrong** — a distinction the gate
could not express until now.

`spec_check.check_points` needs no reference run: it evaluates the specification
at the input/output pairs the problem itself states. All 14 hold at every example
they have, 1 to 6 each, none failing, none over-constrained. **14 of 14
recoverable**, so prediction 1 (at least 8) held with room.

## Falsified: the examples check is weaker than the draws, not stronger

**Prediction 4 said at least one answer would be newly rejected** — a
specification that agrees on 100 random draws and fails an example its problem
states. Across 332 rows now carrying these columns, that count is **0**. The
examples check has never once contradicted the draws on this corpus.

Worse for the naive version of this change, and this is the finding: of the 12
specifications **known to disagree** with their reference solution that carry
these columns, **6 hold at every example their problem states**.

| answer | draws refute it at | examples held |
|---|---|---:|
| `phi4-mini-v3/mbpp_20__is_woodall` | `n=63`, problem says True | 3 of 3 |
| `locallm-r9-seed42/mbpp_541__check_abundant` | `n=2`, problem says False | 3 of 3 |
| `qwen3.8-27b-fp8-v3/mbpp_179__is_num_keith` | `n=4`, problem says True | 3 of 3 |
| `qwen3.8-27b-fp8-v3/mbpp_195__first` | `[[0,1,2],0,0]`, problem says -1 | 3 of 3 |
| `qwen3.8-27b-fp8-v3-s2/mbpp_908__find_fixed_point` | an 11-element sequence | 3 of 3 |
| `qwen235-heldout/mbpp_355__count_Rectangles` | `n=4`, problem says 41 | 3 of 3 |

Three stated examples do not catch what a hundred reference draws catch. A rule
that let the examples answer *for* the draws would have readmitted every one of
those six. So the implemented rule is narrow: the examples may supply a **missing**
verdict and may never overturn a negative one. `NO_REFERENCE_VERDICT` is exactly
`{"no valid draws", "reference result has no t value"}`.
`arity differs from the problem` and `interpreter refused` are deliberately
excluded — the first means the answer is shaped for a different problem, the
second that the specification could not be evaluated, and neither is a missing
verdict. 0 rows in either status hold at their examples anyway, so excluding them
costs nothing and keeps a real signal.

This runs against the direction the literature pointed. Coins reports its
positive-acceptance funnel as where the discrimination lives (`Pass_first` 60.98%
to `Pass_all` 28.05%) and found mutation-based rejection added nothing beyond it;
VeriAct gates on the same signal as `PostCorr`. On this corpus the ordering is the
other way round: acceptance at the problem's own examples is the weaker
instrument, and the reference-solution draws are the stronger. The likely reason
is denominator — those papers use 5 curated pairs and full positive test suites,
where MBPP problems here state about 3 assertions.

**Prediction 3 was also falsified**, at 90 against a registered band of 83 to 89.
The miss is instructive rather than marginal: I modelled one source of change,
75 + at most 14 recovered = 89, and three problems had separately gained draws
evidence since 2026-09-18. A prediction that accounts for only one moving part
gets the total wrong even when it gets its own mechanism exactly right.

## Prediction 5, and what did not move

Registered as "the 232 held-out problems are untouched, falsified by any change to
an eval count". `loop_dataset.py`'s eval-split positive count moved from 15 to 18.
That column is the sampler diagnostic the r6 dataset file describes as measuring
"the sampler, not training data", and **no scored evaluation number changed**:
`score_heldout.py` over `locallm-r4`, `r5`, `r7-92m`, `r7b-headed2`, `r8`,
`r9-seed42` and `phi4-mini-eval2` is byte-identical before and after, because it
reads `status` directly and never consults `positive_rejection`. So the claim the
prediction was protecting holds, and the prediction as literally written does not.
Both are recorded rather than the convenient one.

## What this buys and what it costs

The supervised pool is the binding constraint on every locallm round, and it goes
from 75 to 90, a fifth more data, with no model, no GPU and no new problems. The
cost is that 14 of the 90 carry weaker evidence than the other 76: their
specification is known to hold at the three or so points their problem states,
not against a reference solution on a hundred draws. Anyone comparing a round
trained on 90 against r6's 87 is comparing sizes, not provenance.

Two things follow. A string type in `t` would let all 14 be checked properly and
is now a WS-13.1 construct item with a measured 14-example price rather than a
guess. And the honest next measurement is whether a round trained on the 90 beats
one trained on the 75 — the 15 are all one shape, string problems, so they may
teach a narrow thing well and nothing else.
