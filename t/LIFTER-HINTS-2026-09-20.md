# The 782 Dafny programs no lifter run had ever seen, 2026-09-20

`t-corpora/DafnyBench/DafnyBench/dataset/hints_removed/` holds 782 `.dfy` files
with the source's own annotations stripped. `t/corpora.py:38` hardwires
`CORPUS_DIR` to the sibling `ground_truth/`, so no lifter run had ever opened
them. This is that run, and its control.

    cd t && python3 lifter.py \
      --dir  ../t-corpora/DafnyBench/DafnyBench/dataset/hints_removed \
      --corpus-dir ../t-corpora/DafnyBench/DafnyBench/dataset/hints_removed \
      --out out/lift.hints --jobs 4 --timeout 200

782 files, 1,040 s, `--jobs 4` (the lifter's own `HARD_JOBS_CAP`, because each
job may run dafny). Peak one-minute load 7.0 on this desktop.

## The number, and why the obvious comparison is wrong

| run | rows | lifted | fully lifted |
|---|---:|---:|---:|
| `t/LIFTER-785.md`, recorded 2026-09-06, ground_truth | 968 | 159 (16.43%) | 99 of 785 (12.61%) |
| ground_truth, **current** lifter, run today as a control | 968 | 346 (35.74%) | 253 of 785 (32.23%) |
| **hints_removed, current lifter** | 948 | **314 (33.12%)** | **218 of 782 (27.88%)** |

Read against the recorded figure alone, hints_removed looks like it doubles the
yield, 33.12% against 16.43%. That reading is wrong and the control is what
shows it. The recorded run used the 2026-09-06 lifter; the tree now carries the
2026-09-12 residuals fix and a renamed refusal taxonomy, and thirteen recorded
reasons no longer exist at all (`div-mod` 62, `multi-return` 57, `seq-return`
23, `string-char` 22 and more).

Splitting the two effects:

- **the lifter's own improvement**, same corpus, same flags: 16.43% to 35.74%,
  **+19.31 points**. That is where the whole apparent gain lives.
- **the corpus**, like for like: 35.74% to 33.12%, **−2.62 points** on methods
  and −4.35 on fully-lifted programs.

So hints_removed is **slightly worse, not better**, which is the direction to
expect: it is ground_truth with the loop invariants deleted.

The control reproduced 968 rows exactly, which is what makes the row definition
trustworthy across the two runs.

**`t/LIFTER-785.md` is stale by 19 points** and should be read as a record of
what the 2026-09-06 lifter did, not of what this one does.

**The "154 counted" column cannot be reproduced on this desktop.** Of the 314
lifted rows, 0 are Decision-17 counted: 308 are excluded with
`arm-unavailable: Failed to compile C# source code using 'dotnet build'`, and
`dotnet` is not installed here. Only the *lifted* column is comparable between
the two runs.

## Where the loss goes, and it goes to one obligation

`lift-check-failed` is 73 in hints_removed against 55 in ground_truth on the
same lifter, and that difference is most of the −2.62 points. Inside those 73:

- **57 of 73 (78.1%)** carry a `for-desugared` rewrite.
- **47 of 73 (64.4%)** show one signature: `L_req` and `L_ens` verified, only
  `L_inv_0` not. Every one of the 47 is for-desugared. In ground_truth the same
  signature appears 23 times, so it **doubles** here.

`L_inv_0` is the loop-invariant equivalence obligation. hints_removed deletes
loop invariants from the source. The corpus's entire effect lands on the one
obligation it was built to remove, which makes this corpus a targeted stress
test rather than a general one.

**It is not the bug `t/LIFTER-785-RESIDUALS.md:100-131` describes.** That one,
`_build_checker_parts` typing each for-desugared bound local as a bare `int`, is
fixed: `_task_var_inits` exists at `t/lift_check.py:787` and is used at `:1619`.
These 47 are the *second* bug the same document names immediately afterwards,
`_task_loop_scopes`'s end-alignment heuristic
(`extra_names = rest_local_names[:extra]`), which misassigns the for-desugared
fact when a real local is declared before the loop.

That bug now has a 47-row regression set with a single failing obligation each,
which is a better test than the two examples the residuals document had.

Failing-obligation groups over the 73: `L_inv_0` alone 47, `L_ens` + `L_inv_0`
6, `L_req` 6, three `L_fun_*` pairs, `L_ens` alone 2, `L_inv_0` + `L_inv_1` 2,
and 2 with no verdicts at all (dafny `tool_error`).

## What this is worth

218 fully-lifted programs from hints_removed and 253 from ground_truth, 471
together, against a pipeline whose recent datasets contain **none** of them:
`sft-r3-27b`, `sft-r4`, `sft-r6` and `pairs-r6` are 100% `source: "samples"`.
The lifting path has contributed nothing to any recent training set, and this
run says the material is there.

Outputs are `t/out/lift.hints` (80 MB) and `t/out/lift.gt-current` (88 MB),
both gitignored. The second is the control and is worth keeping until the
`_task_loop_scopes` fix is measured against it.
