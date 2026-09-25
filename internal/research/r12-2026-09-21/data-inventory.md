# Training data for the next locallm run: inventory and contamination, 2026-09-21

Read-only. Nothing in the repository or on the lab was written, and no job was started. The gate counts come from running `loop_dataset.positive_rejection` itself in memory over every tag on the lab (lab repo 3f57ec8b; the gate code is byte-identical to the desktop's). The evidence files are in `r12/`: `inventory.json`, `pending.json`, `cachepeek.json`, `contam.json`, `behave.json`, `decontamination.json`, `decontaminate.py`.

## 1. Sources

"Positives" means distinct train problems under the strict gate. The union over every tag today is **94** (79 on reference draws, 15 on the examples tier). The r8 corpus used 79 because it was built before the examples tier existed. r6ex had 90 because it left out prover-train's 4.

| source | status | now | if finished | missing |
|---|---|---:|---:|---|
| 21 contributing tags from r8's 37-tag list (14B v3/he/apps seeds and fix1, 30B, 27B, DeepSeek-16B, prover-train) | graded 7/7, spec-checked v5 | 94 (86 after decontamination) | same | nothing. Their ungraded rows are copies of graded programs |
| 1.5B r0hf, r0hf-v3, r1-samp-s1; 27B np1024 | graded, clean rows, never spec-checked | 0 | ≤7 (58, 225, 637, 762, 820, 855, 964) | `spec_check --pool v5` |
| qwen235-v6new-p4 | 86 pass, 45 clean | 0 | ≤45 | `spec_check --pool v6`, a split-v6 build |
| qwen235-v6new | 15 of 1,030 raw files corrupt (a shorter write over a longer one), so extract crashed and there is no extract or tests file. Its 121-row table comes from an older extraction | 0 | +2 (47 in the union with p4) | repair or drop the 15, extract/tests `--pool v6`, spec v6 |
| prover-train2 | 37 pass. Its only table is from the reversed session (/dev/shm, 09-20 05:53) and reads 30 of 37 clean | 0 | ≤29 | regrade `--no-cache`, spec v5 |
| qwen235-train | 401 pass. The queue's grade hit its 20 h `timeout` and wrote no table. The /dev/shm grade still running covers 206 of them; the verdict cache shows **5 clean (3 new), 52 undecided (16 new), 149 dead**. 195 were never queued | 0 | ~10–25 | finish the grade. Before merging its table, drop 2 stale rows (rows join by name, not content: https://bazel.build/remote/caching, 849498e1939e). Grade the 195, then spec |
| qwen235-train-p4 | **never extracted**. In memory: 483 pass, 413 new problems | 0 | ~10–20 (the 235B converts 2–3% on train vs 22% held out) | extract, tests, grade, spec |
| repair -fix2/-fix3 (10 arms) | about 290 passing, ungraded | 0 | ~0–3 (fix1 arms converted 1 of 199) | grade, spec |
| held-out repair arms | eval split | 0 | 0 | none |
| multiplier bank | 2,652 banked replies, no extractor or filter | 0 | 0 new problems. 2 of its sources are eval problems | a filter |
| hint bank | 27 × 8 banked; `hint_filter.py` does not exist | 0 | ≤25 lifted documents. Rows 86 and 472 are eval problems | filter, grade |
| lifted / committed | 192 / 30 clean | 167 / 26 after decontamination | | **HEAD's `t/AGREEMENT.md` lists 1 task**: a3c6f955 overwrote 0bbc05cb's 43-row matrix, so a corpus built today silently loses 29 committed documents |

If everything finishes, the result is about 190–210 problems, with no GPU needed.

## 2. Contamination

Method: every hit was read by hand, and each detector is backed by fetched prior art.
- The reference solution with names erased (Python AST alpha-renamed): https://arxiv.org/html/2403.04811, e0cb51c91628.
- Token and statement edit similarity above 0.8: https://ar5iv.labs.arxiv.org/html/2107.06499, a8f6e12ca0ef.
- Every corpus document executed on the eval problem's own assertions, to catch type-4 clones: https://arxiv.org/html/2508.01357v1, 26305f382689; https://ar5iv.labs.arxiv.org/html/1812.06469, 7071a16c1347.
- `loop_filter.key` answer overlap.

The thresholds flag 93 eval problems, and 66 of those turn out on reading to be template siblings such as largest/smallest or odd/even.

**32 eval problems have a same-task training source:**
- Reference identical once names are erased: 366, 527, 699, 719, 775, 800, 842 (and 161, whose partner is outside the pool).
- Near-identical statement or reference: 10, 208, 347, 402, 411, 604, 813, 928, 970.
- A train or corpus program implementing the same function: 138, 358, 443, 492, 502, 518, 566, 682, 687, 729, 887, 931.
- **The eval problem itself is in the corpus**: 269 and 626, as lifted `dafny_synthesis_task_id_N__*` tasks. Both `loop_locallm.mbpp_id` and preflight match only `mbpp_N`, so they have been in every corpus since r7.
- 565 is the identity function in t.

corpus-r8-headed holds **36 same-task documents covering 16 of these**. Of locallm's 23 clean answers from r4 to r10, **22 are on these 32**. The 23rd, r9-seed42's 541, disagrees with its specification. On the other 200 problems locallm has **0 spec-agreeing clean answers in every arm**. The comparison models score, on tests plus seven kernels: Phi-4-mini 2, Prover-7B 3, the untrained 1.5B 4, the 235B 9.

Rule: apply both.
1. **Drop** the 37 same-task documents: 8 SFT (242, 404, 451, 498, 504, 728, apps_124, apps_2465), 25 lifted, and 4 committed (contains, digit_sum, gcd, remainder). Exclude 21 train ids from every future build; 427 and 790 already have passing qwen235 answers waiting to be graded. This follows Lee et al.'s rule of keeping the eval copy and dropping the train copy, and StarCoder's decontamination: https://raw.githubusercontent.com/bigcode-project/bigcode-dataset/main/decontamination/README.md, a240a8bc7a10.
2. **Report every score on all 232 and on the clean 200.** The 32 overlap ids stay frozen so old arms remain comparable. The execution check has only 3 assertions per problem, so some contamination may remain (Riddell and Allamanis, receipts above). Separately, 18 eval problems have tests weak enough that unrelated documents pass them.

## 3. Best valid corpus today

**86 SFT + 167 lifted + 26 committed = 279 documents.** That is 254 without restoring AGREEMENT.md; corpus-r8-headed decontaminated would be 265. As an optional arm, training on every distinct verified program gives 220 programs for the 86 problems, 413 documents (RFT: https://arxiv.org/html/2308.01825v2, 86f784e5f2be).

Run on the lab from `~/tup`:
```
git show 0bbc05cb:t/AGREEMENT.md > t/AGREEMENT.md   # the operator's call: restore, or regrade t/tasks
python3 t/loop_dataset.py --from-samples deepseek-coder-v2-16b-v4-s{1,2} qwen2.5-coder-14b-apps-s{1,2} \
  qwen2.5-coder-14b-he-s{1..8} qwen2.5-coder-14b-v3-s{1..8} qwen2.5-coder-14b-v3-s{1,2,3,4,5,6,8}-fix1 \
  qwen3.8-27b-fp8 qwen3.8-27b-fp8-v3 qwen3.8-27b-fp8-v3-s2 qwen3-coder-30b-apps-{g1,g1-probe,s1,s2} \
  student-r4-train locallm-r4-train prover-train --split t/out/loop/split-v5.json --min-kernels 7 --out-suffix r12
python3 t/loop_locallm.py corpus --pool v5 --lifted --split t/out/loop/split-v5.json \
  --sft t/out/loop/sft-r12.jsonl --out t/out/loop/corpus-r12-raw.txt   # 316; without --pool v5 APPS/HE rows vanish
python3 decontaminate.py t/out/loop/corpus-r12-raw.txt t/out/loop/corpus-r12.txt decontamination.json  # -> 279
python3 t/head_align_corpus.py --corpus t/out/loop/corpus-r12.txt --out t/out/loop/corpus-r12-headed.txt
```
sft-r12 should have 94 rows. To add the v6 positives later: run `spec_check --pool v6` on the v6 tags and build them against split-v6. Then pass both `--sft` files with `--pool v6 --split t/out/loop/split-v6.json`. Do not re-check the v5 tags under v6: there is one spec result per answer, and it would be overwritten.

**What was learned:** locallm's clean count so far is explained by same-task documents in its own corpus; its clean-200 score is 0. Three silent regressions were found: the held-out regex misses lifted names, AGREEMENT.md shrank to one row, and a grade timed out without writing a table. CPU work alone could roughly double the valid positives, from 86 to about 190–210.
