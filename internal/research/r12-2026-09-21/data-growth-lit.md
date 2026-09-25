# Growing verified data and fixing spec-intent misalignment: ranked, with sources

Every source was fetched and read in this session. Receipts are on this machine (`mcp__research-first__receipt`). No repository file was edited.

## What the local numbers say first

Read-only measurements; the scripts are in `scratchpad/r12/*.py`.

- **Most proven-but-wrong answers are recited programs.** In r7b-headed2, r8, r9-seed42 and r10-regrade, 34-57% of them are corpus programs once names are erased (`loop_filter.key`). They cluster on attractors: r8 wrote `getSum` (`r := a + b`) for 15 different problems; r10 wrote `square_nums` 9 times.
  - Each appears at most twice in the corpus, so the cause is a signature prior, not duplication. The 87 SFT positives cover only 15 signatures, and 5 of those have a single program.
  - The corpus used was approximate (282 keys); rerun against the exact corpora on the lab.
- **It is not copying the nearest problem.** Only 1-7% pass the nearest training problem's tests, against 1-3% for a random same-signature problem.
- **The split is full of minimal pairs.** 43 of 232 eval problems have a training problem at 0.9 or higher English similarity (30/31 days, set/unset bits, min/max). Eval 347 is an exact duplicate of train 76.
- **Weak specs are not what limits the positives.** SAFE's 60% completeness bar would drop only 3 of 303 agreeing specs.

So the lever is more distinct programs per signature, each tied to English the model has to read.

## Ranked recommendations

**1. Grade the 235B's train answers and admit them through the existing gate.**
- **Source:** ReST-EM, https://ar5iv.labs.arxiv.org/html/2312.06585 (receipt `91a634035caf`): the large model's data beat the small model's own self-training because it covered more problems; iteration 2 regressed on APPS. SAFE, https://arxiv.org/html/2410.15756 (same receipt): unfiltered specs cut Acc@1 from 43.17 to 17.27.
- **Files:** `loop_dataset.py` (split-v6), `spec_check.py --pool v6`, plus the 60% completeness bar as a guard.
- **Cost:** 10-30 CPU-hours, already queued.
- **Expected:** about +80 positives (499 well-formed × 11 clean per 67 on held-out), doubling the current 90.
- **Risk:** the teacher's own attractors. Apply #2 first.

**2. Behavioural decontamination, applied to every new document.**
- **Sources:** Soft Contamination, https://arxiv.org/html/2602.12413v1 (receipt `b7f65efac1e1`): semantic duplicates raised seen and unseen items by about 20%; close neighbours had no effect. Riddell et al., https://arxiv.org/html/2403.04811: 72% vs 22% on most- vs least-similar MBPP items. Yang et al., https://arxiv.org/html/2311.04850v2: rephrased HumanEval took CodeLlama-13B from 36.0 to 81.1.
- **Rule:** drop a training problem whose reference agrees with an eval reference on both problems' inputs plus 100 draws. Keep minimal pairs, and report eval scores split by similarity.
- **Files:** `loop_locallm.py` (`held_out`), `score_heldout.py`.
- **Cost:** about 1 CPU-hour on the lab (it runs the references).
- **Expected:** an honest held-out score; blocks train 76 before #1 admits it.
- **Risk:** a reference that will not run needs an English check instead.

**3. Relabel verified-but-wrong programs with the problem they actually solve.**
- **Sources:** CodeIt, https://arxiv.org/html/2402.04858 (receipt `71ab665c8b6a`), 220M model: relabeling reached 49/400 against 24/400 for sample-and-filter, which "stagnates". MMA, https://ar5iv.labs.arxiv.org/html/2311.03755: writing English from formal code is 62.3% accurate vs 13.4% the other way.
- **Do:** (a) test each program against every same-signature training problem's tests plus `spec_check`; (b) otherwise a teacher writes English for it, kept only if a fresh teacher answer to that English matches the program on interpreter draws.
- **Files:** a `--relabel` mode in `loop_dataset.py`; an `informalize` variant in `multiplier.py`.
- **Cost:** (a) CPU minutes; (b) under 1 GPU-hour with a 27B-30B model. No new proving: the program and its spec are unchanged.
- **Expected:** 30-66 new programs per locallm round, adding programs per signature, the opposite of the attractor prior.
- **Risk:** noisy English (3 of MMA's 4 examples were right). Weight real positives higher: CodeIt without that fell to 38/400.

**4. A separate `Task: spec` document for each positive.**
- **Source:** Distilling Step-by-Step, https://ar5iv.labs.arxiv.org/html/2305.02301 (receipt `72cae873a864`), T5-220M: the extra target as its own task took ANLI from 43.58 to 49.58; folded into one target it gave 43.50.
- **Files:** `loop_locallm.py` (`cmd_corpus`), `head_align_corpus.py`.
- **Cost:** seconds, plus 30 s of training.
- **Expected:** trains the English-to-`ensures` step on its own.
- **Risk:** the answer splitter must learn the new head, as it did for `Example:`.

**5. Preference training against attractors, never plain DPO on twins.**
- **Sources:** Smaug, https://arxiv.org/html/2402.13228 (receipt `da8c8b3b5669`): DPO "catastrophically fail[s]" when the two answers differ by 6.5%; preferred-token log-probability −1.82 under DPO vs −0.26 under DPOP. Iterative RPO, https://arxiv.org/html/2404.19733: plain DPO 61.8, no better than supervised 63.5; DPO with a likelihood term went from 73.1 to 81.6.
- **Do:** preferred = the verified answer for problem P; rejected = the attractor recited for P. The two differ a lot, the safe case.
- **Files:** locallm's trainer (no preference loss yet); `loop_dataset.py`.
- **Cost:** about a day of engineering.
- **Expected:** a direct penalty on the recited 34-57%.
- **Risk:** round 2's DPO on twins already showed this failure: reward accuracy 1.0, tests-passing down from 5 to 3.

**6. Teacher paraphrases of the problem English, kept only if they survive a round trip.**
- **Source:** MetaMath, https://ar5iv.labs.arxiv.org/html/2309.12284 (receipt `72cae873a864`): rephrased questions took accuracy from 41.6 to 59.7; more answers to the same questions added only +0.1%.
- **Files:** `multiplier.py`. **Cost:** under 1 GPU-hour.
- **Risk:** it adds no new programs, and a paraphrase can land on an eval minimal pair, so #2 must gate it.

**7. Defer self-sampling from locallm.**
- **Sources** (receipt `91a634035caf` unless noted):
  - STaR, https://ar5iv.labs.arxiv.org/html/2203.14465: GPT-2 could not bootstrap even arithmetic.
  - B-STaR, https://arxiv.org/html/2412.17256: gains saturate after 3-5 iterations.
  - DeepSeek-Prover, https://ar5iv.labs.arxiv.org/html/2405.14333: +5.3, +2.1, +3.7, +1.2 per iteration.
  - AlphaVerus, https://arxiv.org/html/2412.06176: without critique, `assume(false)` snowballed.
  - Polu et al., https://ar5iv.labs.arxiv.org/html/2202.01344: global dedup was needed for stability.
  - nl2postcond, https://arxiv.org/html/2310.01831v2 (receipt `94d9718666d3`): 0.21-0.25 single-sample accuracy still covered 78-86% of problems in 10 samples.
- **k:** k=8 over about 2,680 unsolved training problems is 21,440 samples, about 63 GPU-hours unbatched. At 1-2% clean, a third to a half recited, that is roughly 30-80 new programs, fewer than #1 gives for CPU alone.
- **When it pays (estimate):** once locallm's held-out clean rate nears the teacher's, about 5%. Then use temperature 0.5, retrain from the base, dedup by `key`, and stop after 1-2 rounds.

**Not now:** renaming identifiers or reordering statements. For English-to-code it moved BLEU from 32.66 to 33.45 while exact match fell from 20.1 to 19.2 (https://ar5iv.labs.arxiv.org/html/2302.03499). The recitation key already erases names.

## What was learned

- "Proven but wrong" is largely a verified program recited for the wrong problem. Proof comes free with the memory, so stronger provers cannot fix it; more programs per signature and negatives aimed at attractors can.
- The supported data gain comes from more distinct problems, not more samples per problem.
- Self-training starts from a competent model; weak models were bootstrapped with teacher data or relabeling.
