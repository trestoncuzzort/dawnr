# Cached decoding on the round's own generation path, registered 2026-09-30 20:33Z

## Why now

Seed 1 of r12's round on the new core (arm `locallm-r12core`, `t/out/r12-run/run.log`) spent 45 s
fine-tuning and 52 minutes choosing its stopping step: seven kept checkpoints x 100 dev
problems, greedy, one row at a time, the key-value cache off (`t/pick_stopping_step.py` passes
`--use-cache` only when asked; `t/out/r12-run/run.sh` does not ask). The held-out generation that
follows is the same path, 232 problems, about 23 minutes. At step 200, 60 of the 100 dev replies
ran to the 1,200-token cap (`done_reason: length` in the answer set's raw records); at step 50,
all 100 did.

The cache is off on CUDA because it measured no faster (`locallm/FINDINGS-kv-cache-2026-09-19.md`:
0.92 to 1.21x on core-small at 128 new tokens). That measurement was at 128 new tokens. Uncached
decoding recomputes every position at every step, so its cost over a reply is quadratic in the
reply's length; cached decoding computes each position once (rasbt/LLMs-from-scratch
ch04/03_kv-cache README, "Computational efficiency increases ... the cumulative work scales
quadratically, O(n²). With a cache, each key and value is computed once"; that note measured 5x
at 200 tokens on a 124M model on a CPU, and "both ... implementations produce exactly the same
text"). At 1,200 new tokens the quadratic term is 9x larger than at 128 relative to the linear
one, so the 2026-09-19 numbers do not say what happens on this path. Nobody measured this shape.

The finding also checked identity: cached and uncached greedy output were identical in every
configuration, logits within 1e-5 relative. That is the property the round depends on: an answer
set decoded on the cache must be the same answer set.

## The measurement

On the Windows laptop's RTX 5050 (the desktop's card is under the round's lock), with the chosen
step-200 checkpoint of `locallm-r12core-s1` (sha256 715abd24...d402, the same bytes on both
machines) and the round's 100 dev ids (`t/out/locallm-r12core-s1/dev-ids.txt`), the pick's own
command twice, once each way, into two answer sets:

    python t/loop_locallm.py generate --model <ckpt> --tag cache-probe-off --split t/out/loop/split-v5.json
        --ids-file dev-ids.txt --temperature 0 --tokens 1200 --top-k 20 --seed 1
    ... --tag cache-probe-on ... --use-cache

Wall clock per run from the job's status file; the raw records compared task by task (reply text
and `done_reason`).

## Predictions, before the run

1. **Identity.** All 100 replies are byte-equal between the two runs. Falsified by one differing
   reply; then the cache does not go on this path until the difference is understood, whatever the
   speed.
2. **Speed.** The cached run takes at most half the uncached run's wall clock. Falsified by a ratio
   above 0.5.
3. **Length dependence.** Among the replies that hit the 1,200-token cap in both runs, the cached
   run is at least 3x faster per reply than the uncached one; among replies under 200 tokens the
   ratio is below 1.5x. Falsified by either half.

## What follows

If 1 and 2 hold: `t/out/r12-run/run.sh` passes `--use-cache` to the pick and to `gen_fleet.sh` for
the NEXT round (not this one, which runs from the working tree as registered), and
`cache_by_default` in `locallm/checkpoint.py` is re-registered for CUDA at long replies. If 1
fails: a finding, and nothing changes. The laptop's absolute times are not the desktop's; the
ratios are what is registered.
