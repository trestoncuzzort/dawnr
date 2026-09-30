# The base rate by sampling on r12's core

Registered 2026-09-30 09:50Z, before any draw. `t/PREDICT-2026-09-30-dawnr-r12-core.md` prediction
4 read 0 (`spec_agrees` on the 100 dev problems, greedy), and its registered consequence is this
measurement: "the base rate is measured by sampling (64 draws per problem through the checker)
before any reward is built". A greedy 0 does not say whether the model never writes an agreeing
answer or only fails to rank one first. The difference decides three things on the shelf: RL
through the engine (`t/RL-DESIGN-2026-09-26.md`: start when about 10% of groups outside the corpus
hold a passing sample), sampling with a selector (`t/RUN-NEXT-locallm-r12.md` section D), and
mined negatives (`t/NEGATIVES-2026-09-25.md`: 3 usable pairs, 30 needed).

## The measurement

The model is the one the core's judgement scored: the pipeline's mid-trained checkpoint on r12's
core (`ckpt.pt` sha256 `d74ee05a7f9d9790…`, from the core whose `ckpt.pt` is `704f4824b69ed645…`).
The problems are the same 100 dev problems (`t/r12-dev-ids.json`: MBPP train-side problems no
training document names); no held-out evaluation problem is asked.

    ~/.venv-locallm/bin/python locallm/chat_eval.py --model <4-mid/model> --out <base-rate.json> \
        --dev 100 --max-tokens 800 --grammar --max-calls 2 --answer best-verdict \
        --samples 64 --temperature 0.8 --top-k 20 --sample-batch 32 --seed 1

64 draws per problem in two batches of 32, temperature 0.8 and top-k 20 (the sampler RL-DESIGN
section 3 measured with), the judgement's prompt, grammar, two-call budget and best-verdict answer
rule, each batch seeded by `t/pilot_sampling.derive_seed`. Every draw is graded like a greedy
answer: well formed, passes every shown example, the tests tier (the problem's assertions and 50
drawn inputs against its reference), and agreement with the specification check on 200 drawn
inputs for a draw that passes its examples. pass@k is human-eval's unbiased estimate
(arXiv:2107.03374; receipt 30e7f15a9ba5). A 2-problem, 4-draw smoke of the tool runs first and is
discarded.

## Predictions

1. **At least 3 of the 100 problems have a draw that passes every shown example** (greedy: 0; two
   examples are a loose gate). Falsified below 3.
2. **At least 1 problem has a draw that passes its examples and agrees with the specification
   check.** Held at about even odds. Falsified at 0.
3. **RL's bar stays unmet: pass@16 is below 0.10 both for the tests tier and for specification
   agreement** (the document-format policy of 2026-09-26 had a test-passing sample on 0.6% of
   problems outside its corpus at 16 draws). Falsified at or above 0.10 on either.

## What each outcome decides

- Prediction 2 falsified (no agreeing draw on any problem): on this core there is nothing for a
  reward to reinforce or a selector to select; RL through the engine and the sampling pilot stay
  off, and only a teacher can supply agreeing answers. The corpus queue
  (`internal/RESEARCH-2026-09-30-stage-sweep.md` section 7) is the whole plan.
- Some problems hold an agreeing draw and pass@16 stays below 0.10: selection has something to
  select on those problems, and the draws that pass their examples and disagree with the
  specification are the negatives lever 3 lacked (their count is reported); RL stays off.
- Prediction 3 falsified: RL through the engine may be registered, with the dense reward and the
  difficulty band (the problems whose rate lies in (0, 1/4] are reported).

## What it cannot show

One checkpoint, one seed of draws, 100 problems from one source (MBPP's train side). The dev set
is not the held-out set: a rate here bounds what training on these problems could use, and says
nothing about the clean 200, which stays unseen.
