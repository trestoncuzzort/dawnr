# Negatives from specification disagreements, and a preference loss that keeps the positive

Written 2026-09-25, r12 data build, track W7. Every number below names the
command that produced it. Nothing here ran on a GPU.

## What this is for

locallm's dominant failure is proven-but-wrong: a program all seven kernels
verify against the specification the model wrote, whose tests still fail
(59 to 204 a round, `internal/RESEARCH-NEXT-2026-09-20.md`). Between a third
and a half of those are corpus programs recited for the wrong problem
(`internal/research/r12-2026-09-21/data-growth-lit.md`, recommendation 5). The
specification check (`t/spec_check.py`, verdicts in `t/out/spec-disagree.json`)
already names such answers: a clean answer whose `ensures` disagrees with the
problem's own reference solution on random draws is exactly a plausible,
verified, wrong specification for that problem. Recommendation 5 is to train
a preference for the verified positive over that recitation, with a
likelihood term and never as plain DPO:

- Smaug (arXiv:2402.13228, ar5iv.labs.arxiv.org/html/2402.13228, receipt
  1d464135d4a6): when the two completions share most tokens, DPO lowers the
  preferred one; tokens after the edit went from -0.37 under the reference to
  -1.82 under DPO and -0.26 under DPOP. Their Eq. 3 keeps a hinge on the
  chosen side's log-probability inside the log-sigmoid, under beta.
- Iterative RPO (arXiv:2404.19733, receipt 3e49668fe951): plain DPO 61.8 on
  GSM8K against 63.5 for SFT; DPO with a likelihood term on the winner 73.1
  after one iteration, 81.6 after four; the chosen sequence's log-probability
  falls without the term and rises with it.
- This project's own round 2 (`internal/ROADMAP-LOG.md`): DPO on twins,
  reward accuracy 1.0, tests passing on the held-out 161 down from 5 to 3.

## What was built

| file | what |
|---|---|
| `t/negatives_from_spec_disagreements.py` | pairs `{task_id, prompt, chosen, rejected, provenance}` from the disagreeing verdict rows, through the r12 gates; a duplicate pair (the same program under a second tag) refused by name |
| `t/test_negatives_from_spec_disagreements.py` | 8 tests, no torch: the pair, each refusal by name, the duplicate, the two contradictions that stop the build |
| `locallm/data.py` | `PairBatches`: one pair per row, the head masked, the same bytes as the corpus document for the positive |
| `locallm/continue_from_checkpoint.py` | `--pairs`, `--pref-loss {none,dpop}`, `--pref-beta`, `--pref-lambda`, `--pair-batch-size`; a reference frozen from `--init`; the pair pass without dropout; every pair's chosen side checked against `--data`; every setting in `run.json` |
| `locallm/test_r12_preference.py` | 15 tests on the lab CPU: layout, the loss, bit identity under `none`, the DPOP property at dropout 0 and 0.1, the gates, the corpus check, resume |

The prompt of a pair is `loop_locallm.problem_head` for the problem, so the
pair's chosen side is byte for byte the corpus document the language-model
loss trains on (`t/loop_locallm.py corpus` writes `head + program`). The
chosen side is the pool file's raw fenced block, as the corpus builder takes
it; the rejected side is the program `spec_check` stored beside its verdict,
re-parsed and re-hashed against that verdict before use. Since the review of
2026-09-25 the trainer enforces the identity instead of assuming it: `load_pairs`
refuses, by line, a pair whose `prompt + chosen` is not a substring of the
`--data` text, naming whether the head or the program is missing (a corpus
built with `--examples` against pairs built without, or pairs from another
pool file). DPO's own recipe fits the reference on the preferred completions
"to mitigate the distribution shift" (Rafailov et al., Section 4,
ar5iv.labs.arxiv.org/html/2305.18290); here the likelihood term is the corpus
loss, so the corpus has to hold the winners. Checked on the lab: all three
pairs' `prompt + chosen` occur in `corpus-r8.txt` (and in `corpus-r8-headed.txt`);
`run.json` records `pairs.chosen_in_corpus: true`.

## The data, measured on the lab

    python3 t/negatives_from_spec_disagreements.py --split t/out/loop/split-v5.json \
        --pool-file t/out/loop/sft-r8.jsonl --spec-disagree t/out/spec-disagree.json \
        --out t/out/loop/pairs-negatives-2026-09-25.jsonl --report t/out/loop/NEGATIVES-report-2026-09-25.md

Inputs read only: split-v5 (sha256 49103716b2ed), `t/out/spec-disagree.json`
of 2026-09-21 (sha256 2bc190415bc1, identical on both machines), sft-r8 (79
positives, sha256 d45077f592e8), 232 held-out ids, 100 dev ids. Output
sha256 e50457ea8da0.

| count | |
|---|---:|
| disagreeing verdict rows | 81 |
| **pairs written** | **3** |
| refused: held-out (the answer is to a held-out problem) | 74 |
| refused: pool-mismatch (verdict under pool v3, the split is v5) | 4 |
| refused: dev-split, same-task, names-refused-id, no-positive, positive-not-spec-checked, identical-programs, duplicate | 0 each |

Disagreeing rows by tag: locallm-r7b-greedy 66, locallm-smoke 6, prover-train
2, qwen3.8-27b-fp8-v3 2, and one each from locallm-r9-seed42, phi4-mini-v3,
qwen235-heldout, qwen235-heldout-p5, qwen3.8-27b-fp8-v3-s2. The 74 held-out
refusals are locallm-r7b-greedy 66, locallm-smoke 6, qwen3.8-27b-fp8-v3 1
(mbpp_179) and qwen3.8-27b-fp8-v3-s2 1 (mbpp_908). The 4 pool-mismatch
refusals (verdicts under pool v3: locallm-r9-seed42 541, phi4-mini-v3 20,
qwen235-heldout and qwen235-heldout-p5 both 355) also name held-out ids; the
pool check runs first, so they are counted there. 78 of the 81 disagreeing
rows name held-out problems, which no training row may name; the three that
do not are the three pairs. (Re-derived from the verdict file and split-v5 on
2026-09-25 after a review found the first version of this sentence attributed
the 74 to the locallm arms alone.) Every refusal is by key in the report, not
dropped, and a disagreeing program graded again under a second tag (355
above, once its pool is v5) is refused as `duplicate` with the key that first
wrote the pair, so the counts add up: disagreeing = pairs + refusals.

The three pairs:

| task_id | positive | negative | where the specification disagrees |
|---:|---|---|---|
| 509 | sft-r8.jsonl:38 | prover-train/mbpp_509__average_Odd | the negative has no `requires` and states `r == (n + 1) / 2` for every n; at n = 16 the reference answers "Invalid Input" |
| 890 | sft-r8.jsonl:52 | prover-train/mbpp_890__find_Extra | the negative states `r == n` (the index is the length); at ([0, 4], [5], 3) the reference answers 0 |
| 195 | sft-r8.jsonl:13 | qwen3.8-27b-fp8-v3/mbpp_195__first | the negative ranges over the whole sequence where the problem bounds the search by n; at ([0, 1, 2], 0, 0) the reference answers -1 |

These three problems are not new to the pipeline: `t/out/loop/pairs-r8.jsonl`
already holds them as 5 rows of kind `spec-disagrees`
(`loop_dataset.negatives_for_positive`, tier a3), in the Qwen chat format that
locallm's trainer cannot read. What is new is the locallm format, the gates,
and a trainer that can use the pairs at all.

**Three pairs is not a training set.** With `--pair-batch-size 4` a 300-step
run would see each of them about 400 times; that is memorization of three
programs, not a preference over attractors. The count can only grow from the
train-side tags the r12 queue is grading now (`t/r12_data_queue.sh spec`:
qwen235-train, qwen235-train-p4, prover-train2, qwen235-v6new-p4). Among the
train-side clean answers spec-checked so far the disagree share is 2 of 31
for prover-train (`t/out/spec-disagree.json`, `runs`); at that rate the
roughly 190 to 210 positives section B of the plan expects would bring 10 to
20 disagreeing train-side answers, and each is a pair only where a positive
for the same problem exists. That is an estimate, not a count.

## The trainer, measured on the lab CPU

    cd locallm && CUDA_VISIBLE_DEVICES= nice -n 19 ~/.venv-vllm/bin/python -m unittest test_r12_preference

Two-layer, width-32 model, character tokenizer, 8 synthetic pairs whose
sides differ by one character and share the rest (Smaug's low-edit-distance
case). Since the review of 2026-09-25 the fixture's corpus holds every pair's
chosen document, laid out as `t/loop_locallm.py corpus` writes it, as the
r12 corpus holds the real positives; the init is first fitted to that corpus
for 300 steps (Smaug and RPO both measure after supervised fitting; from a
random init the corpus loss lifted both sides, chosen +9.1 and rejected
+5.1 nats in 30 steps, and only the margin separated them). The numbers of
the first version of this note were measured on a fixture whose chosen
programs were foreign to the corpus; they are replaced below.

- `--pairs` with `--pref-loss none`: all 29 weight tensors and every metrics
  row equal a run without `--pairs`; `run.json` records the pairs file, its
  sha256, the loss name, beta, lambda, the batch size, the pair pass's
  dropout (0.0), `chosen_in_corpus` and the reference's checkpoint hash,
  with `scored: false`.
- `--pref-loss dpop`, beta 0.3, lambda 50, lr 1e-3, 30 steps, corpus loss
  on, `--dropout 0` (the trainer's default): every chosen side ended above
  its reference (+2.5 to +3.1 nats, mean -8.46 against -11.25), every
  rejected side far below (-40.4 to -42.7, mean -69.9 against -28.1); reward
  accuracy 1.0, margin positive, hinge 0 at every logged step,
  `pairs_chosen_below_reference` 0.0 and `pairs_chosen_deficit` 0.0.
- The same under `--dropout 0.1`, the r12 recipe's setting, which the pilot
  arm copies: chosen -0.09 to +1.25 (mean -10.77 against -11.25), rejected
  -25.4 to -27.8 (mean -55.2 against -28.1), reward accuracy 1.0; the hinge
  fired at one of three logged steps (0.048). The control with the same seed
  and `--pref-loss none` shows what the term is holding against: under
  dropout the corpus loss alone pulled every chosen side 6.7 to 8.0 nats
  BELOW its reference in those 30 steps (and 7.0 to 8.9 on a second seed), so
  DPOP ends +7.7 to +8.1 above the control on the chosen side and -22.3 to
  -23.6 below it on the rejected side. One pair 0.09 below its reference is the
  hinge's slack, not a failure: the hinge sits inside the log-sigmoid under
  beta, and at a margin of 28 nats and lambda 50 the term does not bite
  until the deficit nears margin / lambda, 0.5 nats. At 60 steps every chosen
  side is above its reference (+0.03 to +0.70) and every rejected side 36 to
  39 below. Second seed at 30 steps: chosen +0.18 to +0.87, rejected -38 to
  -41. The test asserts the per-pair slack bound, the means, and the two
  control comparisons.
- Preference loss alone, same fitted init, the trainer's optimizer and clip:
  DPOP (lambda 50) chosen minimum +3.5 above reference, rejected maximum
  -48.1 below; plain DPO (lambda 0) took every chosen side DOWN, minimum
  -84.5, with the rejected side at -121.9. **Smaug's failure reproduces at
  width 32 once the chosen side is a fitted corpus document one edit away
  from the rejected one**; in the first fixture (chosen programs foreign to
  the corpus) plain DPO left the chosen side at +20 and the note said the
  test could not show the hinge mattering. It does now, and the test asserts
  plain DPO's fall as well as DPOP's hold.
- A pairs file naming a held-out id, a dev id or a same-task source is
  refused by line before torch is imported; a pair whose head or chosen
  program is not in `--data` is refused by line and named; `--pref-loss dpop`
  without `--pairs` is refused; a resumed run keeps the reference values it
  started with and refuses a changed lambda.

**Dropout, found in review.** The first version scored the reference once
in eval mode and ran the policy's pair pass in train mode. With the
trainer's default `--dropout 0` that is the same network; under the recipe's
`--dropout 0.1` the policy's log-probabilities sat below the reference's by
the dropout deficit on every step, the hinge fired on that noise, and its
gradient lifted the REJECTED side 6.0 to 8.7 nats above its reference while
`pairs_chosen_below_reference` read 0.0 and reward accuracy 1.0 (the
reviewer's probe on the old fixture): both pilot criteria as first written
said success for a run doing the opposite of what it was for. TRL's
DPOTrainer disables dropout in the model and the reference model for the
whole run by default (`DPOConfig.disable_dropout`,
raw.githubusercontent.com/huggingface/trl/main/trl/trainer/dpo_config.py).
Here only the pair pass runs in eval mode (`pair_forward`): dropout off,
nothing drawn from the generator, autograd unaffected; the corpus loss keeps
the recipe's dropout and `--pref-loss none` stays bit-identical. `run.json`
records `pairs.dropout: 0.0` beside the recipe's `dropout`, and the property
test now runs at both settings.
- Existing tests of the two files touched: `test_r12_continue`,
  `test_r12_doc_batches`, `test_r12_split`, `test_r12_decode`, `test_release`
  (65, one skipped as before) and `test_bpe`, `test_checkpoint`,
  `test_token_cache`, `test_tokenizer_drops`, `test_tokenizer_integrity`,
  `test_audit_example_masks`, `test_train_factorial`, `test_train_distributed`
  (48, one skipped as before) all pass; `t/test_preflight_run_json` and
  `t/test_r12_problem_id` (24) pass.

One departure from the track's wording, on purpose: the task text described
the term as "the DPO loss plus lambda times max(0, log p_ref(chosen) - log
p_theta(chosen))". Smaug's Eq. 3 puts that hinge inside the log-sigmoid and
under beta, and that is what is implemented, with the paper's defaults
(beta 0.3, lambda 50). The likelihood term RPO adds on the winner is, in this
trainer, the language-model loss on the corpus that already contains every
positive; it is on every step whether or not `--pairs` is given.

Two gradient artefacts worth knowing before anyone tunes lambda: with a bare
AdamW and no gradient clip, the hinge's one large gradient set Adam's
momentum for the next twenty steps and lifted both sides by 33 nats
(measured in the first version of the in-process test); the trainer's
`clip_grad_norm_ 1.0` and betas (0.9, 0.95) are what make lambda 50 behave.
The trainer's settings are the ones the tests use.

## Decision for r12

**Not in r12 unless a pilot supports it.** The evidence against running it
blind is the project's own: round 2's DPO had reward accuracy 1.0 and lost
two test-passing answers, and today's pair count is three. What would
support it, in order:

1. The queue's spec checks finish and `t/negatives_from_spec_disagreements.py`
   is rerun with `--pool-file t/out/loop/sft-r12.jsonl` over the updated
   `t/out/spec-disagree.json`: at least 30 pairs over at least 15 problems,
   or the term cannot be a preference over attractors.
2. A pilot on one seed of the r12 recipe, identical but for
   `--pairs t/out/loop/pairs-negatives-2026-09-25.jsonl --pref-loss dpop`
   (the recipe's `--dropout 0.1` included; the pairs rebuilt from the
   corpus's own pool file, or the trainer refuses them), judged the way
   section C chooses the stopping step: tests passed on the dev split
   (`t/r12-dev-ids.json`) at every kept step, decoded greedily, and the dev
   proven-but-wrong count beside it. In `metrics.jsonl`, all of:
   `pairs_rejected_logp` below `pairs_rejected_ref_logp` (the rejected side
   falls; before the dropout fix it rose while every other number read
   well), `pairs_chosen_logp` at or above `pairs_chosen_ref_logp`,
   `pairs_chosen_deficit` under `pairs_margin / (beta * lambda)` (the
   hinge's slack), and `pairs_reward_accuracy` above the 0.5 a
   reference-equal model starts at. `pairs_chosen_below_reference` is
   watched, not a criterion on its own: one pair a tenth of a nat under its
   reference at a 28-nat margin is the hinge's slack.
3. The prediction, registered before the pilot in the r12 predictions file:
   dev tests passed not below the no-pairs arm, and dev proven-but-wrong
   lower. Either number going the other way ends it, as round 2 ended plain DPO.

Until then the flag exists, is tested, and is off: `--pref-loss none` is the
default and a run without `--pairs` is unchanged to the bit.
