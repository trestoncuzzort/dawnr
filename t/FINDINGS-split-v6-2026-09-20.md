# The 1,032 stdin problems were invisible to the dataset builder, 2026-09-20

Pool v6 was wired in earlier today: 4,035 problems, 1,032 more than v5, a 34.4%
increase, and by tonight the 235B has answered **1,030 of the 1,032**. None of
them could have entered a training set, and the reason is one line.

`t/loop_dataset.py:817` reads the pool from the split file:

    pool_name = split.get("pool", "v1")

and then keeps only ids that fall in the split's train or eval half. There was no
`split-v6.json`. Every stdin id is outside `split-v5.json`'s 3,003, so all 1,030
answers were skipped in silence — no warning, no rejection reason, because an id
in neither half is not rejected, it is never considered.

## What was written

`t/out/loop/split-v6.json`, on `split-v5.json`'s schema exactly, no new fields:

| field | value |
|---|---|
| `pool` | `v6` |
| `pool_size` | 4035 |
| `eval_ids` | **the same 232**, byte-identical to v5, v4 and v3 |
| `train_ids` | 3,803 = v5's 2,771 + the 1,032 v6 adds |

232 + 3,803 = 4,035 = `len(pool("v6"))`. The held-out set is unchanged on purpose:
every number this project has published on 232 problems stays comparable, and a
split that moved the eval half would silently invalidate all of them.

Six invariants were asserted before the file was written, not after: 232 eval
ids; no overlap between eval and train; no new id colliding with the held-out
set; every v5 train id still in pool v6; every eval id in pool v6; and the two
halves summing to the pool exactly. The new ids are 474 stdin-shaped APPS
problems and 558 CodeContests problems from `nl_stdin_pool.stdin_pool()`.

## What it does not do yet, measured

    python3 t/loop_dataset.py --split t/out/loop/split-v6.json \
        --from-samples qwen235-heldout locallm-r7b-headed2 --out-suffix v6probe

    train: 3803 problems, 0 with a positive
    eval:  232 problems, 0 with a positive
    sample gate rejections: {"eval": {"kernels-not-clean-seven": 42,
      "not-wellformed": 306, "spec-not-agrees": 3, "spec-pool-mismatch": 11,
      "tests-not-passing": 102}, "train": {}}

Two things to read there. The split loads and the builder walks all 4,035
problems, so the plumbing is right. And `spec-pool-mismatch: 11` is the gate
doing its job: those are `qwen235-heldout`'s eleven specification-check results,
run under `--pool v3`, correctly refused when offered as v6 evidence.

So two steps remain before pool v6 yields a single training example, and neither
is this file:

1. **The 1,030 answers are not graded.** `qwen235-v6new` holds `raw` and `tasks`
   and no kernel table. Until the seven run over them there are no positives to
   gate.
2. **Every contributing tag needs `spec_check --pool v6`.** `positive_rejection`
   compares the result's recorded pool against the split's, by design. Note the
   consequence, because it is a real constraint and not a bug: `spec-disagree.json`
   is keyed by `tag/name` and carries **one pool per answer**, so re-running a tag
   under v6 replaces its v3 evidence rather than adding to it, and a v3-split
   build would then reject the same answers for the mirror-image reason. Move a
   tag's pool when that tag's data is wanted under v6, not before.

The gate is left exactly as it is. It is the reason 26 of 26 repaired answers did
not cheat once, and a pool label it declines to take on trust is the same
mechanism.
