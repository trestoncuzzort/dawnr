# More verified answers from a 92M model at inference time: sources and a protocol (r12)

**Bottom line.** Sample many answers per problem, filter them on the 2 visible examples, then choose among the survivors by behavioural agreement on random inputs. Keep the seven verifiers as the final gate, not as the chooser. Decode the samples as one batch with a stop rule, which should make them cheap. Grammar-constrained decoding comes later. Every claim below comes from a source fetched and read this session, with a receipt.

## What the code shows (checked)
- `locallm/model.py generate` has **no stop rule**. It always decodes `--tokens` (1200). r10's replies have a median of 318 characters (p90 640). With byte-level BPE (at least 1 char per token), **at least 73% of decode steps are thrown away** at the median.
- The KV-cache finding was timed only at **batch 1** on a 30M random-weight model. Batch >1 was never timed. `generate` already takes a batch of equal-length prompts, so k copies of one prompt need no padding.
- r10 funnel: 43 answers fail to parse and 77 fail well-formedness, leaving 112 tasks out of 232. 6 pass tests and 5 are clean. The parse failures are real syntax errors.
- **The visible-example filter is 72% precise here.** Across r8, r9, r9-seed42 and r10, 18 answers passed the 2 `discriminative()` points and 13 of those passed all 3.
- **Bug:** `t/example_holdout.py` treats `points[:2]` as the shown points. `loop_locallm.examples()` actually shows the `discriminative()` pair, and the two differ on **54 of 232** held-out problems.
- `t/pool_pick.py` filters on *all* tests. Fine for training data, but it must never run on held-out candidates.
- No grammar hook exists in locallm. `t.gbnf` only reaches vLLM, through `spec_experiment.py`.
- The headline arm r7b-headed2 was one draw at T=0.5, top-k 20. Rounds r8 to r10 were greedy. Phi-4-mini was greedy with 3,072 tokens.

## Ranked recommendations

| # | Change | Source (receipt) | Supporting number | Files | Cost | Expected effect | Risk |
|---|---|---|---|---|---|---|---|
| 1 | Keep samples that pass the 2 visible points, then take the largest behaviour cluster on inputs from `spec_check.draw` (no reference solution) | ar5iv.labs.arxiv.org/html/2203.07814, /2207.10397, /2204.11454 (c6c5684f31f5) | AlphaCode 300M: 82.05% of problems had an example-passing sample; clustering 21.5 to 24.1%. CodeT one-shot filter: APPS-intro pass@1 29.3 to 43.6. MBR-exec MBPP: 47.3 to 58.2 at 25 samples | new `t/select_candidates.py` using `spec_experiment.run_point`, `interp`, `spec_check.draw`, `loop_locallm.discriminative` | CPU minutes | The main lever for tests-pass, and therefore for clean answers | Only 1 held-out point per problem. Clustering fell below baseline for CodeGen on MBPP (41.0 vs 42.4) |
| 2 | Prefill once, decode k rows together with the KV cache, stop each row at the document boundary | raw.githubusercontent.com/karpathy/nanochat/master/nanochat/engine.py; arxiv.org/html/2609.19499v1; pytorch.org/blog/accelerating-generative-ai-2 (b4d0b366cf5f) | 8 serial calls keep only 16.7-17.9% of one batched call's throughput. N=1 to 8 raised latency only 5.26 to 7.64 s. torch.compile + static cache: 25.5 to 107.0 tok/s | `locallm/model.py`, `locallm/checkpoint.py sample(num_samples)`, `t/loop_locallm.py --samples`, `t/gen_fleet.sh` (passes flags through) | Code only | Makes k=64 affordable | Unmeasured at 92M. Use MPS only if nobody else is on the box (one MPS user at a time) |
| 3 | Tune T on problems outside the held-out set and report coverage with the unbiased estimator | ar5iv.labs.arxiv.org/html/2107.03374; arxiv.org/html/2407.21787v3; arxiv.org/abs/2606.28661 (eb33c5d4f9a5) | Codex-85M pass@1/10/100: 8.22/12.81/22.4. Best T 0.2 for pass@1, 0.8 for pass@100. Voting plateaus near 100 samples; Pythia got **zero** CodeContests coverage | `t/score_heldout.py` (coverage column) | Small | Tells whether k helps at all | The small model may have no coverage to find |
| 4 | Use proofs only as the final gate; the refuted twin is the exploit check | arxiv.org/html/2412.06176v1 (cba81bca0541) | Model-written specs "lack formal guarantees". Without critique, the model gamed the verifier with `assume(false)` | none | none | Avoids picking proven-but-wrong answers | none |
| 5 | Grammar mask in locallm through llguidance: `LLTokenizer(tok.backend.to_str())` plus `t/t.lark.gbnf` | arxiv.org/html/2403.01632v4; arxiv.org/abs/2405.21047; llguidance `hf.py`/`torch.py` (bdcc869cebfa) | 96.07% of syntax errors removed, but Llama-3.2-1B accuracy only 25.6 to 28.8 | `locallm/model.py` | About 50 µs per token of mask | Addresses only the 13-19% of answers that fail to parse; after filtering, about 0 more clean answers | The mask distorts the distribution (GAD). Type/scope errors (25-35%) are beyond a grammar |
| 6 | Learned verifier (LEVER), later | ar5iv.labs.arxiv.org/html/2302.08468 (c6c5684f31f5) | MBPP 62.0 to 68.9 | new | Needs a trained model | Unknown | Using the LLM itself as verifier did worse than pruning errors |

## The four questions
1. **Which signals are legitimate.**
   - (a) The visible examples: yes, if the baselines get the same selector and the score counts only the held-out point. CodeT shows that examples which are also graded "greatly empower" selection: HumanEval pass@1 went 44.5 to 58.6 when they were left in the context.
   - (b) The seven verifiers: a gate, not a chooser (AlphaVerus). Running them on every sample costs too much CPU.
   - (c) Agreement on random inputs: yes. Inputs only, no outputs, as in MBR-exec.
   - (d) Spec against the examples: a filter only. This project already found 6 of 12 disagreeing specs that hold at every example.
   - Checking each candidate's `ensures` against other candidates' outputs would be **our own extension**. No fetched source covers it, so it is untested.
2. **T and k.**
   - T: MBR-exec wants T below 0.5 for choosing by agreement. CodeT and Codex use 0.8 to widen coverage. AlphaCode saw little difference across a wide range. Sweep {0.4, 0.6, 0.8}.
   - k = 64: votes settle "within a few dozen draws" and voting plateaus near 100 samples.
   - Scoring: pass@1 after selection is the number that counts. Coverage@k is its ceiling.
3. **Grammar.** It is not wired into locallm's sampler (details in row 5).
4. **Cost.** Covered in row 2. The existing batch-1 null result does not predict batch-64 timing.

## Protocol for the next run
1. **Register predictions first** (a `t/PREDICT-...` file): coverage@64, clean answers after selection, selector precision.
2. **Tune** T on 200 train-split problems whose answers are not in the corpus. All tests may be used there. Pick T by pass@1 after selection.
3. **Generate** 64 samples per problem: `--samples 64 --tokens 512`, stop rule on, T as tuned. Keep the prompt the model was trained on (no `Example:` lines). Store every candidate with its mean log-probability in `candidates/<id>.jsonl`.
   - Pilot on 20 problems first, timing k=1, 16 and 64.
4. **Select** with `t/select_candidates.py`, which uses the visible pair only and never the 3rd point, the reference solution or the kernels:
   - extract and check well-formedness;
   - pass both visible points;
   - drop specs that contradict a visible point;
   - take the largest cluster by outputs on 24 drawn inputs; break ties by mean log-probability.
   - If nothing passes the visible points: largest cluster among well-formed candidates. If nothing is well-formed: the greedy answer.
   - Write one `raw/<id>.json` per problem.
5. **Grade** with `t/grade_lab.sh heldout <tag>` as usual.
6. **Baselines:** give Phi-4-mini the same k, T and selector (vLLM `n=64`). Report greedy and selected columns for every model.
7. **Report:**
   - clean and recited/novel counts;
   - held-out-point pass rate, after fixing the `example_holdout.py` pair;
   - coverage@k (for measurement only, never for selection);
   - an audit of selected answers against the reference solution on drawn inputs, because AlphaCode finds 30-60% false positives on datasets with few tests;
   - GPU and CPU time.

**Cost:**
- **GPU:** set by the pilot. If batching buys nothing, it is 64 times today's roughly 40 minutes, so the pilot decides whether to go ahead.
- **Selection CPU:** about 15k candidates through the pure-Python interpreter, a matter of minutes.
- **Kernels:** still one answer per problem, but about twice as many well-formed ones, so about twice today's 20+ minutes per 112 answers.

**Planning estimate, not a claim.** Assume pass@64 is 3-4 times pass@1 (the Codex small-model ratio), 72% filter precision, and 5 of 6 tests-pass answers turning clean. That gives roughly 6-12 clean, against 5 today.

## What was learned
- The largest fetched gains come from filtering on examples (+14 points) and agreeing on execution (+7 to +13). Proofs cannot choose between answers when the model writes its own spec.
- Decoding is wasting at least 73% of its steps, and batch>1 has never been timed.
- A grammar mask can only touch the 13-19% of answers that fail to parse.
- The existing gaming check measures the wrong pair of points on 54 problems.
- The open question is whether a 92M model gains coverage with k at all (Pythia got none). The 20-problem pilot answers it cheaply.
