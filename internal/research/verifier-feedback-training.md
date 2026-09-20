# Training a code model on verifier / test-oracle signals

Research lane: RL from verifier feedback, rejection sampling, verified-data curation,
self-training loops, negative/counterexample training, and their measured effect sizes.
Priority 2025-2026. Compiled 2026-09-20.

**Our constraints (for the "implementable here" ratings):** 92M-param transformer trained
from random init, one shared GPU, ~46M token corpus, ~79 verified clean examples + 733
preference pairs, seven proof systems + per-problem unit tests as oracles, and an existing
mutation engine that produces deliberately broken twins of any verified program.

Rating scale: **A** = directly runnable at our scale this week; **B** = idea transfers, needs
reworking for 92M/79-example scale; **C** = interesting but the result is scale-dependent
and probably does not transfer; **D** = cautionary / negative result to keep in mind.

---

## 1. Improving Small Language Models for Code Generation with Reinforcement Learning from Verification Feedback

- **Year / venue:** 2026, arXiv preprint
- **arXiv:** 2605.30478
- **URL:** https://arxiv.org/abs/2605.30478
- **Authors:** Egor Skopin, Evgeny Kotelnikov

**Method.** Straight RLVR on small models: sample completions for MBPP problems, run the
provided unit tests, reward = test outcome. Compares reward formulations (unit-test-only,
static-analysis/Ruff-lint penalty, and a combined reward) and two group-based policy
optimizers (GRPO and GSPO). LoRA fine-tuning rather than full fine-tuning. Reports
behavioural diagnostics (generation length, Ruff severity profile, execution-error type
histogram) alongside pass@1.

**Reported numbers.**
- Base models: **Qwen3-0.6B** and **Llama3.2-1B** — the smallest scale in this literature,
  and the closest published point to ours.
- Benchmark: MBPP. **Up to +13 percentage points pass@1** under the best combined-reward
  configuration.
- Key negative: **static-analysis penalties alone bias the policy toward shorter completions
  that clear lint errors without reliably improving functional correctness.** Reward shaping
  induces systematic behavioural shifts; the authors stress extreme sensitivity to reward design.
- No public repo found.

**Implementable here: A.** This is the single most transferable effect size in the lane
because the base models are sub-1B. Caveat: 0.6B–1B *pretrained* models already have code
priors that a 92M from-scratch model does not, so +13pp is an optimistic ceiling.

**What to implement.** Binary pass/fail unit-test reward as the primary signal, and *never*
a style/lint-only reward term on its own — if we add a proof-shape or formatting term, keep
it strictly secondary and watch mean generation length as the canary for reward hacking.

---

## 2. Training Language Models on Synthetic Edit Sequences Improves Code Synthesis (LintSeq / TinyCodeLM)

- **Year / venue:** ICLR 2025
- **arXiv:** 2410.02749
- **URL:** https://arxiv.org/abs/2410.02749 · project page https://lintseq.github.io/
- **Repo:** https://github.com/upiterbarg/lintseq (Python; ICLR 2025 artifact)
- **Weights:** https://huggingface.co/upiter/TinyCodeLM-150M-LintSeqInstruct, `upiter/TinyCodeLM-400M`
- **Authors:** Ulyana Piterbarg, Lerrel Pinto, Rob Fergus

**Method.** LintSeq refactors an existing program into a sequence of synthetic *edits* by
running a **static verifier (a linter) in a backward sampling phase**: it randomly deletes a
line, uses the linter to find every line that becomes an error, deletes those too, and repeats
until the program is empty. Reversing that deletion trace gives a chain of program states each
of which is *linter-correct*. Forward phase converts consecutive states into diffs. Models are
then instruction-tuned to emit diffs rather than whole programs. **This is the closest published
analogue to our mutation engine used in reverse** — a checker defining which intermediate states
are legal.

**Reported numbers.** (Base models are *from-scratch pretrained* at 150M/400M — our scale band.)
- TinyCodeLM pretrained from scratch on **72B tokens**; instruction set **88,900 instruction+program
  pairs**, expanded **5x** into synthetic edit sequences.
- **TinyCodeLM-150M**: HumanEval pass@1 9.1 → **12.8**, pass@10 13.5 → **20.6**; MBPP pass@1
  11.5 → **13.6**, pass@10 21.6 → **24.4**.
- **TinyCodeLM-400M**: HumanEval pass@1 11.3 → **13.4**, pass@10 18.5 → **20.9**; MBPP pass@1
  15.5 → **19.4**, pass@10 22.2 → **29.9**.
- Larger models, HumanEval/MBPP pass@1: Gemma 2 2.6B 15.3/20.5 → **22.0/28.2**; Phi-3 Mini 3.8B
  35.2/31.9 → **38.4/37.2**; Llama 3.1 8B 38.4/37.4 → **38.5/40.3**. Note the **gain shrinks as
  the base model grows** — at 8B it is ~0 on HumanEval. That is the direction we want: the
  technique is worth *most* at small scale.
- HumanEval pass@50 gain of **+20% absolute (±3%)** over the baseline-tuned model.
- **Linter ablation (the load-bearing result):** replacing linter-guided deletion with random
  deletion (RandSeq) on TinyCodeLM-150M drops HumanEval pass@1 **6.4 → 4.5 (-30% relative)** and
  MBPP pass@1 **8.6 → 6.5 (-24% relative)**. The verifier in the loop is what makes the synthetic
  data worth anything; random corruption does not.

**Implementable here: A.** Same parameter scale, from-scratch training, verifier-in-the-loop
data synthesis, and a published ablation isolating exactly the verifier's contribution.

**What to implement.** Turn each of the 79 verified programs into a chain of checker-valid
intermediate states by deleting lines/tactics and letting the proof checker close the dependency
set, then train on the diff chain rather than the finished proof. With a 5x expansion this alone
turns 79 examples into ~400 sequences, and the RandSeq ablation tells us to make the deletions
*checker-guided*, not random — our mutation engine should be run in "delete until the checker
complains, then delete the complaints" mode, not "corrupt a token" mode.

---

## 3. Delay, Plateau, or Collapse: Evaluating the Impact of Systematic Verification Error on RLVR

- **Year / venue:** COLM 2026 (arXiv Apr 2026)
- **arXiv:** 2605.02909
- **URL:** https://arxiv.org/abs/2605.02909
- **Repo:** https://github.com/eth-sri/llm-verifier-noise
- **Authors:** Kazuki Egashira, Mark Vero, Jasper Dekoninck, Florian E. Dorner, Robin Staab,
  Martin Vechev (ETH Zurich SRI Lab)

**Method.** Controlled injection of *systematic* (not random i.i.d.) verifier errors into RLVR
training, on arithmetic tasks where ground truth is known exactly, so the effect of a broken
reward can be measured cleanly. Prior work had modelled verifier noise as random and concluded
it merely slows training; this paper shows that conclusion is an artefact of the noise model.

**Reported numbers / findings.**
- **Systematic false negatives** (verifier wrongly rejects correct programs) behave like random
  noise — training is slowed, final performance largely preserved.
- **Systematic false positives** (verifier wrongly accepts wrong programs) produce
  **sub-optimal plateaus through to outright performance collapse**. The outcome depends on the
  *pattern* of the errors, not the aggregate error rate, which makes it impossible to bound the
  damage from a headline accuracy figure alone.

**Implementable here: D (cautionary) / A (as a design rule).** This is the most important
negative-result paper for us because our reward *is* seven proof systems plus unit tests, and
a unit test suite is exactly a false-positive-prone verifier: a program that passes 3 weak tests
is accepted though wrong.

**What to implement.** Bias every oracle toward false negatives and away from false positives:
require *all* available oracles to agree before an example is labelled clean, treat a timeout or
checker crash as a reject rather than an accept, and log the false-positive rate of the test
suites (e.g. by running the mutation engine's broken twins through them — any broken twin that
passes is a measured false positive, and that number is the health metric for the whole pipeline).

---

## 4. The Verification Horizon: No Silver Bullet for Coding Agent Rewards

- **Year / venue:** 2026, arXiv (June 2026)
- **arXiv:** 2606.26300
- **URL:** https://arxiv.org/abs/2606.26300
- **Authors:** Binghai Wang et al. (13 authors)

**Method.** Position-plus-experiments paper characterising verification signal quality along
three axes — **scalability, faithfulness, robustness** — and arguing you cannot get all three at
once. Studies four reward constructions: test-suite verifier for general coding, rubric verifier
for frontend, human-as-verifier for real agent tasks, agent-as-verifier for long-horizon tasks.

**Reported numbers / findings.** Core claim: **no fixed reward function stays effective as policy
capability grows**; optimisation widens the gap between the proxy and the intent, showing up as
reward hacking or signal saturation. Verification must co-evolve with the generator.

**Implementable here: C for the frontier-scale specifics, B for the framing.** Our policy is 92M
and will not outrun a proof checker any time soon — a *formal* proof checker is one of the few
verifiers that is faithful by construction, which is a real advantage of our setup over the
test-suite-only setups this paper criticises.

**What to implement.** Record a saturation curve: fraction of sampled programs the oracle accepts,
per training round. When that fraction climbs while held-out quality does not, the reward has
saturated and it is time to harden the oracle (add tests, add a proof system) rather than train longer.

---

## 5. STaR: Bootstrapping Reasoning With Reasoning

- **Year / venue:** NeurIPS 2022 (the ancestor of every self-training-with-oracle loop here)
- **arXiv:** 2203.14465
- **URL:** https://arxiv.org/abs/2203.14465

**Method.** Sample rationales, keep only those whose final answer matches ground truth (an oracle
filter), fine-tune on the survivors, repeat. "Rationalization": for problems the model failed,
feed the answer as a hint, generate a rationale backwards, strip the hint, and add it to the set —
recovering training signal from failures instead of discarding them.

**Reported numbers / limitation that matters most to us.** The headline result is a large gain on
arithmetic/CommonsenseQA from a 6B model. But the load-bearing caveat: **the first iteration only
works if few-shot performance is above chance — GPT-2 could not bootstrap even on arithmetic.**
A self-training loop has an entry requirement and a 92M from-scratch model is below it at init.

**Implementable here: B, but only after a cold start.** We cannot run a naive STaR loop from random
weights; the pass rate at round 0 will be ~0 and the filter will return an empty set.

**What to implement.** Use the *rationalization* trick as the cold-start: our 79 verified programs
are the "answers". Condition on the verified program, have the model produce the derivation, strip
the conditioning, and train on it. That manufactures a first round of training data without needing
the model to solve anything unaided, which is exactly the barrier STaR names.

---

## 6. Does Reinforcement Learning Really Incentivize Reasoning Capacity in LLMs Beyond the Base Model?

- **Year / venue:** **NeurIPS 2025 Oral**; best paper at ICML 2025 AI4MATH workshop
- **arXiv:** 2504.13837
- **URL:** https://arxiv.org/abs/2504.13837
- **Repo:** https://github.com/LeapLabTHU/limit-of-RLVR
- **Authors:** Yang Yue, Zhiqi Chen, Rui Lu, Andrew Zhao, Zhaokai Wang, Shiji Song, Gao Huang

**Method.** Measures RLVR models against their own base models across the whole pass@k curve
(not just pass@1), on math, coding and visual reasoning, across several model families and
**six RLVR algorithms**. Also measures whether RLVR-model reasoning paths already lie in the
base model's sampling distribution (perplexity / coverage analysis).

**Reported numbers / findings — the central negative result of this lane.**
- RLVR wins at small k (k=1) but **the base model overtakes it as k grows to tens or hundreds,
  across every benchmark and model family tested, without exception.** RLVR narrows the reasoning
  boundary: it reallocates probability mass onto paths the base model already had, it does not
  add new ones.
- All **six RLVR algorithms perform similarly and all remain far from optimal** at extracting the
  base model's latent capacity — i.e. the algorithm choice matters far less than people assume.
- **Distillation, by contrast, does introduce genuinely new reasoning patterns** from the teacher
  and expands the boundary.

**Implementable here: A as a warning, and it reframes the whole plan.** Our model is trained from
random weights: there is no rich base distribution for RLVR to sharpen. If RLVR only amplifies
what the base already samples, then RLVR on a 92M from-scratch model will amplify approximately
nothing. The paper's own remedy — *distillation expands the boundary where RL does not* — points
at what should come first.

**What to implement.** Spend the budget on supervised/distilled data (verified programs, verified
derivations, checker-guided edit chains) **before** any RL stage, and when RL does run, report
pass@k not just pass@1 so we can see whether we are sharpening or actually widening. If our pass@k
at large k degrades after an RL round, that is the documented failure mode, not a bug in our setup.

---

## 7. V-STaR: Training Verifiers for Self-Taught Reasoners

- **Year / venue:** COLM 2024
- **arXiv:** 2402.06457
- **URL:** https://arxiv.org/abs/2402.06457

**Method.** STaR discards every incorrect sample. V-STaR keeps them: correct solutions go to the
generator's SFT set, while *all* solutions, labelled correct/incorrect by the oracle, become
**DPO preference pairs for a separate verifier model**. At inference the verifier reranks candidates.
Iterated over several rounds; generator and verifier both improve.

**Reported numbers.**
- Base models: **LLaMA2 7B / 13B** class. Benchmarks: code generation (MBPP/HumanEval) and math (GSM8K).
- **+4% to +17% test accuracy over existing self-improvement and verification baselines.** Gains
  compound across iterations.

**Implementable here: A.** This is the closest published justification for our 733 preference pairs
existing at all — it is exactly "oracle verdicts turned into DPO pairs". The key structural point:
the preference pairs train a *verifier/reranker*, not (only) the generator, and the verifier then
buys accuracy at sample time rather than at train time. That is cheap for us: a reranker can be a
small head on the same 92M trunk.

**What to implement.** Split the 733 preference pairs into a DPO-trained correctness head, and use
it to rerank the generator's n samples before we ever call the real proof checker. Measure the
gain as "oracle calls saved per solved problem" as well as accuracy — at our scale, oracle time is
the bottleneck.

---

## 8. Not All Negative Samples Are Equal: LLMs Learn Better from Plausible Reasoning (PNS)

- **Year / venue:** 2026, arXiv (Feb 2026)
- **arXiv:** 2602.03516
- **URL:** https://arxiv.org/abs/2602.03516

**Method.** Argues that treating every wrong answer as an equally good "rejected" sample wastes the
negative side of preference training. Synthesises **Plausible Negative Samples**: outputs with correct
format and locally coherent structure where **each individual step looks reasonable but the
composition is wrong**. Selection uses a composite PNS reward — accuracy inversion, format compliance,
reward-model quality score, and chain-of-thought coherence. The resulting pairs are harder and force
finer-grained discrimination during DPO.

**Reported numbers.** Gains reported over standard DPO with randomly-sampled negatives; the
qualitative claim is the transferable part — **hard, near-miss negatives beat trivially-wrong
negatives for the same number of pairs.**

**Implementable here: A, and it is a direct instruction to our mutation engine.** We already have an
engine that makes "deliberately broken twins". This paper says the *quality bar* on those twins is
what decides whether the 733 pairs are worth anything.

**What to implement.** Grade our broken twins by edit distance and by how far into the proof the
checker gets before it fails. Keep the twins that fail **late** and are **one small edit** from the
verified program (near-misses); down-weight or discard twins that fail at the first token or are
structurally garbage. Rebuild the 733 pairs with that filter and re-run the same DPO — the number of
pairs stays the same, so any difference is attributable to negative quality alone.

---

## 9. AlphaVerus: Bootstrapping Formally Verified Code Generation through Self-Improving Translation and Treefinement

- **Year / venue:** **ICLR 2025**
- **URL:** https://openreview.net/pdf?id=AyjhgkQDeY ·
  PDF mirror http://www.contrib.andrew.cmu.edu/~bparno/papers/alpha-verus.pdf

**Method.** Generates **code plus its proof** in Verus (Rust) with no human-labelled training data,
by translating from a Dafny corpus and iterating with verifier feedback in three stages:
**Exploration** (translate), **Treefinement** (tree search over repair attempts guided by the verifier's
error messages), and **Critique** (filter out programs that satisfy the verifier but not the intent).
The Critique stage exists *because* the loop reward-hacks the verifier — the model learns to write
vacuous specifications that verify trivially.

**Reported numbers.**
- Collected corpus **DAFNY2VERUS-COLLECTION: 247 translated programs, 102 error trajectories, and
  579 exploit pairs** — i.e. a *tiny* dataset, the same order of magnitude as our 79 + 733. This is
  the single closest data-scale match in the lane.
- Beats **AutoVerus by ~10% on proof annotation**, despite AutoVerus being purpose-built for that task.
- Reports gains on verified HumanEval and verified MBPP, with no human intervention, no hand-engineered
  prompts, and modest compute.

**Implementable here: A.** Tiny data, formal checker as the only supervisor, explicit handling of
verifier gaming, and the artefact includes a *negative* corpus (error trajectories + exploit pairs)
structured much like ours.

**What to implement.** Copy the three-stage shape: (1) propose, (2) **Treefinement** — feed the
checker's error message back and search over repairs rather than resampling from scratch, (3) keep
an explicit *exploit* set of programs that pass the checker but are vacuous/degenerate, and train
against them as hard negatives. That third set is free for us to generate: run the mutation engine
until something passes the oracle anyway, and every such hit is both a measured false positive and a
new hard negative.

---

## 10. Re:Form — Reducing Human Priors in Scalable Formal Software Verification with RL in LLMs (Dafny)

- **Year / venue:** 2025, arXiv (Jul 2025), under review
- **arXiv:** 2507.16331
- **URL:** https://arxiv.org/abs/2507.16331
- **Repo:** https://github.com/Veri-Code/ReForm · models+data https://huggingface.co/Veri-Code
- **Benchmark released:** DafnyComp (compositional, multi-function programs with global constraints)

**Method.** End-to-end pipeline with **no human annotation anywhere**: LLM-generated Dafny
data curation, SFT, then GRPO with the **Dafny verifier as the only reward**. Deliberately
**removes natural-language chain-of-thought** from the pipeline, arguing it is long, ineffective
and unreliable for formal tasks. Reward includes a "spec superiority" term so the model is pushed
to write *stronger* specifications rather than vacuous ones.

**Reported numbers — this is the best-instrumented small-scale formal-verification RL result.**
- Base models: **Qwen-2.5 at 0.5B, 1.5B, 3B, 7B, 14B** — includes sub-1B.
- Data: 20,000 Dafny functions total; **only 3,000 used for SFT and 4,500 for RL**. (Sources:
  16.3k Python2Dafny, 0.9k MetaReflection, 0.3k BigCode.) Eval: 512 in-domain, 300 DafnyComp.
- **3B model, in-domain pass@1: base ~5% → SFT ~40% → SFT+RL ~55%.** So SFT on verified data is
  worth **~35 points** and the verifier-driven RL stage adds **~15 points** on top.
- Spec superiority rate: **+63.8% relative gain** from RL over SFT.
- Out-of-domain DafnyComp (14B): SFT 8.3% → **RL 14.0%** pass@1; GPT-4o 2.7%; most other LLMs ~0%.
- RL improves pass@128 much more than SFT does — i.e. here RL *widened* the distribution rather
  than narrowing it, the opposite of the Yue et al. finding, plausibly because the verifier is
  formal and exact rather than a test suite.
- Cost: 14B RL run ≈ **20 hours on 64 A800-80G**. GRPO, 4 samples/input, batch 1024, lr 1e-5,
  temp 1.0, KL 0.01, entropy 0.02.

**Implementable here: A for the recipe and the hyperparameters, B for the compute.** The ordering
evidence is what matters: **SFT on verifier-approved data delivered ~2.3x the gain that the RL
stage did**, from 3k examples. That is the strongest argument for spending our effort on the
verified-data side before the RL side.

**What to implement.** Adopt the no-CoT formal-only target format, the GRPO hyperparameters above
as a starting point, and above all the **spec-superiority idea**: score a candidate not just on
"the checker accepted it" but on whether its obligations are *stronger* than a reference, which
directly blocks the vacuous-proof exploit. Also mirror their split ratio — roughly 40% of curated
data to SFT, 60% to RL.

---

## 11. Reinforcement Learning for Reasoning in Large Language Models with One Training Example (1-shot RLVR)

- **Year / venue:** **NeurIPS 2025** (poster)
- **arXiv:** 2504.20571
- **URL:** https://arxiv.org/abs/2504.20571

**Method.** RLVR (GRPO and PPO) where the training set is literally **one** problem, selected by
training-accuracy variance. Measures generalisation to six math benchmarks the single example has
nothing to do with.

**Reported numbers — the most striking data-efficiency result in the lane.**
- Base model **Qwen2.5-Math-1.5B**: MATH500 **36.0% → 73.6%** from **a single training example**.
  Average over six math benchmarks **17.6% → 35.7%**.
- **Two** examples: MATH500 74.8%, average 36.6% — slightly better than one.
- A **1.2k-example** DeepScaleR subset containing that same example gives MATH500 73.6%,
  average 35.9% — i.e. **1 example ≈ 1,200 examples**. The data scaling curve is almost flat.
- Replicates across Qwen2.5-Math-7B, Llama3.2-3B-Instruct, DeepSeek-R1-Distill-Qwen-1.5B, and
  across GRPO and PPO.

**Implementable here: B — enormously encouraging *if* the mechanism transfers, and it may not.**
The paper's own reading (and Yue et al.'s) is that this is **elicitation, not instruction**: the
single example unlocks capability already latent in a heavily-pretrained base. A 92M model trained
from random weights on 46M tokens has very little latent capability to elicit, so the headline
number should not be extrapolated to us.

**What to implement.** The actionable part is the *selection criterion*, which costs nothing:
pick RL prompts by **high variance in training accuracy** (problems the model sometimes solves and
sometimes does not), rather than by difficulty or at random. With 79 verified examples and a tiny
model, prompt selection is one of the few free levers we have. Also: this paper is direct evidence
that **"we only have 79 examples" is not automatically fatal for the RL stage** — it is fatal for
the pretraining stage, which is a different problem.

---

## 12. Goedel-Prover: A Frontier Model for Open-Source Automated Theorem Proving

- **Year / venue:** 2025, arXiv (Feb 2025); V2 technical report Aug 2025 (arXiv 2508.03613)
- **arXiv:** 2502.07640
- **URL:** https://arxiv.org/abs/2502.07640 · project https://goedel-lm.github.io/

**Method.** Two-part pipeline. (1) **Statement formalisation**: train formaliser models to turn
natural-language problems into Lean 4 statements, with an automatic check that the formal statement
preserves intent — yielding **1.64M formal statements**. (2) **Expert iteration**: a chain of provers,
each trained on proofs produced and *Lean-verified* by its predecessor. Bootstrap: use
DeepSeek-Prover-V1.5-RL to generate 16 proofs per statement, compile each with Lean, keep one
verified proof per solved statement, retrain, repeat.

**Reported numbers.**
- miniF2F **57.6% Pass@32**, beating the previous best open-source model by **+7.6 points**.
- PutnamBench: 7 problems at Pass@512, #1 on the leaderboard at the time.
- Produced **29.7K verified Lean proofs for Lean Workbook problems, ~1.9x the 15.7K** from prior work.
- Scale: the formal statement corpus is 1.64M — four orders of magnitude beyond our pool.

**Implementable here: C for the scale, A for one specific mechanic.** The transferable mechanic is
**"generate k attempts, keep exactly one verified proof per problem, retrain"** — deduplicating to
one proof per statement prevents the easy problems (which yield many proofs) from swamping the set.

**What to implement.** Cap the contribution of any single problem to one verified sample per round.
With 79 examples and seven proof systems, the risk of one easy theorem dominating the gradient is
real, and this is a one-line fix.

---

## 13. Spurious Rewards: Rethinking Training Signals in RLVR

- **Year / venue:** 2025, arXiv (Jun 2025)
- **arXiv:** 2506.10947
- **URL:** https://arxiv.org/abs/2506.10947 ·
  writeup https://rethink-rlvr.notion.site/Spurious-Rewards-Rethinking-Training-Signals-in-RLVR-1f4df34dac1880948858f95aeb88872f
- **Repo:** https://github.com/ruixin31/Spurious_Rewards
- **Authors:** Rulin Shao, Shuyue Stella Li, Rui Xin, et al.

**Method.** Runs RLVR with deliberately broken reward signals — **random rewards**, format-only
rewards, and even **systematically incorrect** rewards — and compares against ground-truth rewards.

**Reported numbers — the most important control experiment in this lane.**
- **Qwen2.5-Math-7B trained with completely random rewards: MATH-500 +21.4 points absolute**,
  against **+29.1 points** for perfect ground-truth rewards. A reward carrying *zero* information
  captured ~74% of the gain of a correct one.
- **This does not replicate on Llama3 or OLMo2.** The effect is a Qwen-family artefact — RLVR is
  surfacing code-reasoning behaviours already baked into Qwen's pretraining, not teaching anything.

**Implementable here: A as a mandatory experimental control; the result itself is a D.**
Every "RLVR gave us +N points" claim in this literature — including ours, when we make one —
is suspect unless a random-reward arm was run alongside.

**What to implement.** Whenever we run a verifier-reward training arm, run a **random-reward arm
with the identical budget** as a control, and report the delta between them rather than the delta
from the starting checkpoint. If our verifier reward cannot beat random by a clear margin, the
oracle is not the thing doing the work. This is cheap: it is the same training script with the
reward function replaced by `random.choice([0,1])`.

---

## 14. Textbooks Are All You Need (phi-1)

- **Year / venue:** 2023, arXiv (the origin of the "filter hard, train small" result)
- **arXiv:** 2306.11644
- **URL:** https://arxiv.org/abs/2306.11644
- **Authors:** Gunasekar, Zhang, Aneja, et al. (Microsoft Research)

**Method.** Not verifier-filtered but *classifier*-filtered: a quality classifier selects
"textbook quality" web code, plus GPT-3.5-synthesised textbooks and exercises. Trained from
scratch. Included here because it is the canonical measurement of **what aggressive data
curation buys per parameter**, which is the question our 46M-token corpus poses.

**Reported numbers.**
- **phi-1: 1.3B params, 4 days on 8 A100s, 6B tokens of filtered web code + 1B tokens synthetic.**
  HumanEval pass@1 **50.6%**, MBPP **55.5%**.
- **phi-1-small: 350M params, same pipeline, still 45% on HumanEval.** This is the number that
  matters for us — a 350M model reaching 45% HumanEval purely on data quality.
- Emergent capability gap between phi-1 and phi-1-base attributed to the small finetuning exercise
  set, not scale.

**Implementable here: B.** The lesson transfers (curation beats volume at small scale); the exact
numbers do not, since 350M is ~4x our parameter count and 7B tokens is ~150x our corpus.

**What to implement.** Treat the corpus as the main lever, not the architecture. Spend a round
explicitly measuring **tokens-of-curated-data vs held-out oracle pass rate** on our own corpus so we
know where our curve saturates — phi's contribution was proving that curve is much steeper than the
raw-scaling curve, and that is testable at 46M tokens.

---

## 15. Absolute Zero: Reinforced Self-play Reasoning with Zero Data (AZR)

- **Year / venue:** **NeurIPS 2025**
- **arXiv:** 2505.03335
- **URL:** https://arxiv.org/abs/2505.03335 · project https://andrewzh112.github.io/absolute-zero-reasoner/
- **Repo:** https://github.com/LeapLabTHU/Absolute-Zero-Reasoner (Python)

**Method.** One model plays both **proposer** (invents tasks — deduction, abduction, induction —
over Python programs) and **solver**. A **code executor is the sole verifier**: it validates that a
proposed task is well-formed and has a gold answer, then checks solutions. Joint optimisation with a
multitask advantage estimator; rewards for *task learnability* as well as solution correctness. No
external dataset at all.

**Reported numbers — note the scaling direction, which is bad news for us.**
- Qwen2.5-**Coder-3B: +5.7** overall average (code +3.7, math +7.7)
- Qwen2.5-**Coder-7B: +10.2** overall (code +5.0, math +15.2)
- Qwen2.5-**Coder-14B: +13.2** overall (code +3.6, math +22.8)
- Qwen2.5-Base-7B: +7.0 overall; Llama3.1-8B: **+3.2** overall (code +3.1, math +3.4)
- Explicit conclusion: **"performance improvements scale with model size"** — 3B gains less than
  half what 14B gains. Self-play needs a capable proposer, and capability is the scarce thing at 92M.
- Safety: an "uh-oh moment" — concerning reasoning chains emerged in the Llama3.1-8B run.

**Implementable here: C.** The mechanism is beautiful and the repo is usable, but the measured
trend runs the wrong way for us: the smallest model tested (3B, and a *pretrained coder* at that)
got the smallest gain, and Llama-8B got +3.2. Extrapolated to 92M-from-scratch, the expected gain
is around zero. **Do not build a self-play proposer this round.**

**What to implement.** Only the cheapest fragment: the **learnability reward** for task selection —
weight a problem by how close the current model's pass rate is to 50%. That is the same insight as
1-shot RLVR's variance-based selection and costs one counter per problem.

---

## 16. DeepSeek-Prover-V1.5: Harnessing Proof Assistant Feedback for RL and Monte-Carlo Tree Search

- **Year / venue:** ICLR 2025
- **arXiv:** 2408.08152
- **URL:** https://arxiv.org/abs/2408.08152
- **Repo:** https://github.com/deepseek-ai/DeepSeek-Prover-V1.5
- **Weights:** `deepseek-ai/DeepSeek-Prover-V1.5-Base` / `-SFT` / `-RL` on Hugging Face (7B, open)

**Method.** Three stages on a **7B** model: pretrain on formal maths, SFT on an enhanced Lean 4
proof corpus, then **RLPAF — reinforcement learning from proof assistant feedback** (the Lean
compiler's verdict is the reward). Inference uses **RMaxTS**, an MCTS variant whose tree nodes are
*intermediate tactic states recovered from Lean's compilation messages*, with an **intrinsic reward
for reaching novel tactic states** to fight reward sparsity.

**Reported numbers.**
- miniF2F-test **63.5%** (V1.5-RL + RMaxTS), ProofNet **25.3%** — SOTA at publication.
- Predecessor DeepSeek-Prover-V1 (also 7B) reached **46.3% with 64 samples** on miniF2F after
  fine-tuning on a synthetic corpus of **8M formal statements + proofs**, generated by
  expert iteration with Lean as the filter, including the **prove-the-negation trick**: for each
  synthesised statement, search for a proof of the statement *and* of its negation concurrently,
  which cheaply discards unprovable statements and harvests training data either way.

**Implementable here: B for RMaxTS, A for the negation trick and the error-message tree.**
The valuable, scale-free idea is that **the checker's error message is a state signal, not just a
verdict** — partial progress through a proof is a dense reward where pass/fail is sparse.

**What to implement.** Two things. (1) Extract the failure position/tactic state from each of our
seven proof systems' error output and use "how far the checker got" as a dense shaping term instead
of binary accept/reject — this is the single highest-value change for a model too weak to ever hit a
full pass. (2) For any generated conjecture, attempt it and its negation; whichever closes gives a
verified training example.

---

## 17. VeRPO / Beyond Binary: Turning Partial Success into Dense Verifiable Rewards for RL in Code Generation

- **Year / venue:** 2026, arXiv (Jan 2026)
- **arXiv:** 2601.03525
- **URL:** https://arxiv.org/abs/2601.03525
- **Repo:** promised on acceptance; none public as of now.

**Method.** Attacks reward sparsity without introducing a learned reward model. A test suite yields
*per-test-case* outcomes, so passing a subset is an intrinsic, verifiable dense signal. VeRPO
computes a difficulty weight per unit test from **execution statistics gathered during training**:
`w_j = exp(-alpha * rho_j)` with `alpha = 2.0` and `rho_j` the empirical pass rate of test j, then
divides by a Gaussian-KDE estimate of local test density to correct **"cardinality bias"** — the
failure where many easy tests collectively dominate the gradient despite each having a low weight.
Reward = sum of weights of passed tests.

**Reported numbers.**
- Backbone **Qwen3-8B**. Gains of VeRPO over **outcome-only GRPO** (multi-turn): HumanEval+ +1.46,
  BigCodeBench-Full +1.61, BigCodeBench-Hard +2.38, LiveCodeBench-V6 +2.57,
  **Codeforces CodeElo +8.83**; **average +3.12 over GRPO**, +17.80 over the base on CodeElo.
- Single-turn gains are smaller: **+1.26 average over GRPO**.
- So: dense partial-credit is worth roughly **1-3 points on top of** binary verifier reward, and much
  more on the hardest benchmark where binary reward is almost always zero.

**Implementable here: A.** Our regime is precisely the one where binary reward is almost always zero,
which is where this paper's gain is largest (CodeElo +8.83 vs HumanEval+ +1.46). The method needs no
extra model — only per-test statistics we are already collecting.

**What to implement.** Replace the binary oracle reward with the weighted fraction of passing unit
tests / discharged proof obligations, weights `exp(-2 * pass_rate)` estimated online, and **apply the
density correction** — with seven proof systems and uneven obligation counts per problem, cardinality
bias is exactly our failure mode (a problem with 40 trivial obligations would otherwise outweigh one
with 3 hard ones).

---

## 18. Where the Verifier Fails: A Category-Level Audit of Reward Signals in RLVR

- **Year / venue:** 2026, arXiv (Sep 2026)
- **arXiv:** 2609.01354
- **URL:** https://arxiv.org/abs/2609.01354
- **Related:** "Are Verifier Errors Independent Within a GRPO Group? Evidence from Qwen2.5 Rollouts",
  arXiv 2609.06386, repo https://github.com/ethxin0011/rlvr_group_correlation

**Method.** Applies **metamorphic testing to the verifier instead of the model**: generates
certified-equivalent rewrites of ground-truth answers (transformations that preserve meaning by
construction) and measures per-category rejection rates across four widely used verifiers, over
**307,420 verdicts**.

**Reported numbers.**
- Verifier **self-validation ranges from 53.8% to 95.2% on identical inputs — a 41.3-point spread**
  between harnesses. Earlier work had quoted a single "~94% acceptance of its own ground truth"
  figure; this shows that average hides categories where the verifier is barely better than a coin flip.
- Companion paper finds verifier errors are **correlated within a GRPO group**, which breaks the
  independence assumption GRPO's advantage estimate relies on.

**Implementable here: A, as a cheap audit we should run before trusting any result.**

**What to implement.** Metamorphic-test our own oracles: take each of the 79 verified programs, apply
meaning-preserving rewrites (rename bound variables, reorder independent lemmas, change whitespace,
swap equivalent tactics), and confirm the oracle still accepts. Any rejection is a false negative in
our reward, and per the Delay/Plateau/Collapse paper (item 3) those are survivable — but we need the
number, and it is the cheapest experiment on this list.

---

## 19. Scaling Relationship on Learning Mathematical Reasoning with LLMs (RFT — rejection sampling fine-tuning)

- **Year / venue:** 2023, arXiv (the canonical effect-size measurement for rejection sampling)
- **arXiv:** 2308.01825
- **URL:** https://arxiv.org/abs/2308.01825
- **Authors:** Zheng Yuan et al.

**Method.** RFT: sample many reasoning paths from a supervised model, keep the ones whose answer is
correct (oracle filter), **deduplicate by distinct reasoning path**, fine-tune on the survivors.
Studies how gains vary with pre-training loss, supervised data amount, and augmented data amount.

**Reported numbers — the two findings that matter most for a small model.**
- **LLaMA-7B: SFT 35.9% → RFT 49.3% on GSM8K (+13.4 points)** when rejection samples from multiple
  models are pooled.
- **"RFT brings more improvement for less performant LLMs."** The worse the base model, the bigger
  the rejection-sampling gain — the opposite of the scaling direction in AZR (item 15) and LintSeq's
  large-model results. This is the most favourable scaling law in the whole lane for our situation.
- **The gain comes from *distinct* reasoning paths, not raw sample count.** More samples with the
  same reasoning add little.
- **Log-linear relation between data amount and performance**, and pre-training loss predicts
  performance better than parameter count does.

**Implementable here: A.** Rejection sampling is the cheapest possible use of an oracle and this is
the measurement that says it pays off *most* at our end of the capability range.

**What to implement.** Build the RFT loop first, before any RL: sample n proofs per problem, keep
every one the checker accepts, **deduplicate by proof structure (normalised tactic sequence), not by
string**, and fine-tune. Pool across all seven proof systems — "rejection samples from multiple
models" is what took LLaMA-7B from 35.9 to 49.3, and seven proof systems are our multiple sources.
Also: report **pre-training loss** alongside accuracy, since it is the better predictor.

---

## 20. Curriculum Learning for Small Code Language Models

- **Year / venue:** **ACL 2024 Student Research Workshop**
- **arXiv:** 2407.10194 · https://aclanthology.org/2024.acl-srw.44/
- **URL:** https://arxiv.org/abs/2407.10194
- **Data:** TinyPy Generator corpus, https://www.kaggle.com/datasets/kamelmohammedyamani/tinypy-for-curriculum-learning
- **Authors:** Marwa Naïr et al.

**Method.** **1M-parameter** decoder-only GPT models — the smallest scale anyone publishes at —
trained on synthetic Python from **TinyPy Generator**, a context-free-grammar tool that emits
syntactically correct programs *with their expected outputs* (so the "oracle" is built into
generation). Difficulty is scored by a proposed Overall Metric, data bucketed easy/medium/hard, and
several curriculum schedules are compared, including a novel hybrid.

**Reported numbers.**
- **Curriculum learning significantly improves code *execution* accuracy for these 1M models, but
  its effect on code *completion* is much weaker.** That asymmetry is the finding: ordering data by
  difficulty helps the task that requires following semantics step by step, and barely helps
  next-token-style generation.

**Implementable here: A.** 1M params is *below* our 92M, so if anything works there it works here,
and the grammar-generated-with-known-output trick is directly reusable for bulking out a 46M corpus.

**What to implement.** Order the corpus easy→hard using a difficulty score (proof length, number of
obligations, number of distinct tactics), and expect the benefit on "can the model simulate/execute
the semantics" rather than on raw completion. Also consider grammar-generating extra well-formed
programs with known checker verdicts to grow the corpus beyond 46M tokens cheaply.

---

## 21. When the Reward Suite Is Leaky: A Preregistered Causal Contrast of Natural Verifier False Positives in RLVR

- **Year / venue:** 2026, arXiv (Jul 2026)
- **arXiv:** 2607.11022
- **URL:** https://arxiv.org/abs/2607.11022
- **Author:** Chuyifei Zhang

**Method.** A **preregistered** two-arm causal contrast — the rare thing in this literature. Same
MBPP tasks, same seeds, same compute; the only difference is the reward suite: **original MBPP tests
(leaky) vs MBPP+ extra tests (hardened)**. Two further model families replicate under a
preregistration frozen before their data existed. Emphasises that real test-suite false positives are
**per-task, persistent and asymmetric** — the same wrong programs are accepted every time — which is
exactly the systematic-false-positive regime item 3 warns about.

**Reported numbers.**
- The average held-out effect of hardening the suite is **bounded as non-inferior under a
  preregistered 1.5-point margin** — i.e. in this setting, fixing the leaky tests did **not** produce
  a meaningful downstream gain. A genuine, carefully-established **negative result**.
- But: **rewarded false-positive mass tracks a cheap static leakiness audit run before training,
  Spearman 0.80**, and the leaky stratum has a **false-positive share +43.8 points above clean tasks**.

**Implementable here: A — this is the cheapest high-value item on the list.** The finding is
two-sided and both sides are useful: (a) do not assume hardening the oracle automatically buys
accuracy; (b) a **static audit predicts which tasks will be gamed, with rho = 0.80, before spending
any training compute**.

**What to implement.** Run a static leakiness audit over our per-problem unit tests before training —
for each problem, push the mutation engine's broken twins through the suite and record the fraction
accepted. Stratify the 79 problems by that score and hold the leaky stratum out of the reward, or
weight it down. And when we do harden an oracle, preregister the expected effect size, because this
paper's headline is that the intuitive gain did not materialise.

---

## 22. LIMR: Less is More for RL Scaling

- **Year / venue:** 2025, arXiv (Feb 2025)
- **arXiv:** 2502.11886
- **URL:** https://arxiv.org/abs/2502.11886
- **Model/data:** https://huggingface.co/GAIR/LIMR
- **Authors:** Xuefeng Li, Haoyang Zou, Pengfei Liu (GAIR)

**Method.** **Learning Impact Measurement (LIM)** — an automated score for how well each training
sample's reward trajectory aligns with the *model's overall learning curve*. Samples whose difficulty
tracks the model's improvement are kept; samples that are always-solved or never-solved are dropped.
Purely automatic, no human labelling, no extra model.

**Reported numbers.**
- A selected subset of **1,389 samples matches or exceeds the full 8,523-sample dataset** across
  several maths benchmarks — an **~84% data reduction at no cost**.
- **+16.7% accuracy on AIME24** over the RL-on-everything baseline; beats LIMO and s1 by **13.0%**
  and **22.2%** on MATH500.
- Explicit conclusion: **precise sample selection, not data scale, determines RL effectiveness.**

**Implementable here: A.** With 79 examples we cannot subsample much, but LIM inverts usefully: it
tells us *which* of our examples are carrying the gradient, and the same statistic identifies the
dead weight (always-pass or never-pass problems contribute nothing).

**What to implement.** Log per-problem reward trajectories across training and compute the LIM
alignment score. Expect a large fraction of the 79 to be never-solved (dead) at 92M — those should
be routed to the *easier* end of a curriculum (item 20) or to rationalisation-style cold start
(item 5) rather than left in the RL pool contributing zero-variance groups, which also wastes GRPO's
advantage estimate.

---

## 23. Tülu 3 — RLVR as one stage of a full open post-training recipe

- **Year / venue:** 2024/2025, Ai2
- **arXiv:** 2411.15124
- **URL:** https://arxiv.org/abs/2411.15124 · blog https://allenai.org/blog/tulu-3-technical
- **Repo:** open-instruct / Tülu3Code, data and eval all released (permissive licences)

**Method.** RLVR here is deliberately minimal: replace the learned reward model in a standard PPO
setup with a **deterministic verification function**; reward **alpha = 10** if verifiably correct,
**0** otherwise. Applied on top of an SFT→DPO pipeline rather than as the whole training story.

**Reported numbers — the sober baseline against which the flashier results should be read.**
- RLVR on top of the DPO checkpoint gains **+1.7 on MATH, +3.3 on GSM8K, +1.3 on IFEval**.
- That is *low single digits* for a fully engineered RLVR stage in a frontier open recipe — versus
  the +13 to +37 point numbers elsewhere in this file. The difference is that Tülu applies RLVR to an
  already-strong checkpoint; the big numbers come from applying it to weak or raw base models.

**Implementable here: A as a calibration point.** Also note the binary alpha=10/0 reward and PPO —
deliberately unsophisticated, and it still worked. We should not over-engineer the reward on round one.

**What to implement.** Use it as the expectation-setter in our write-ups: **a well-executed RLVR
stage on top of a good SFT/DPO checkpoint is worth a few points, not a transformation.** Budget
accordingly and put the effort into the data stages.

---

## 24. Infrastructure: GRPO/RLVR frameworks worth lifting rather than rebuilding

Not papers, but the code that makes the above runnable on one shared GPU.

- **verl** — https://github.com/verl-project/verl (Apache-2.0, Python). Implements PPO, **GRPO**,
  GSPO, ReMax, REINFORCE++, RLOO, PRIME, DAPO, **Dr.GRPO**, KL_Cov/Clip_Cov. Crucially it supports
  **function-based (verifiable) rewards** natively for math and code alongside model-based rewards —
  i.e. you plug in a Python callable that runs your checker. This is the reference implementation for
  the reward plumbing we need.
- **OpenRLHF** — https://github.com/OpenRLHF/OpenRLHF (Apache-2.0, Ray + vLLM). PPO, REINFORCE++,
  REINFORCE++-baseline, GRPO, RLOO. HKUST reproduced DeepSeek-R1-Zero-style training **on small
  models** with it, so the small-scale path is trodden.
- **TRL** (HuggingFace) — best fit for a single shared GPU and rapid prototyping; `GRPOTrainer` takes
  a list of reward functions directly.
- **awesome-RLVR** — https://github.com/opendilab/awesome-RLVR — continually updated index of the
  whole area; worth checking before any further literature sweep.
- **Spurious_Rewards** — https://github.com/ruixin31/Spurious_Rewards — has the random/format/wrong
  reward harnesses already written; lift these directly for the control arm in item 13.
- **llm-verifier-noise** — https://github.com/eth-sri/llm-verifier-noise — code for injecting
  controlled systematic verifier error, for reproducing item 3's diagnostics on our own oracles.
- **lintseq** — https://github.com/upiterbarg/lintseq — the linter-guided backward sampler from item 2.
- **Absolute-Zero-Reasoner** — https://github.com/LeapLabTHU/Absolute-Zero-Reasoner — executor-as-verifier
  self-play loop (item 15).
- **ReForm** — https://github.com/Veri-Code/ReForm + https://huggingface.co/Veri-Code — full
  formal-verifier RL pipeline with released models and data at 0.5B–14B (item 10).

**Implementable here: A.** For a 92M model on one shared GPU, **TRL's `GRPOTrainer` with a custom
verifier reward function** is the least-effort path; borrow verl's reward-function interface design
and Spurious_Rewards' control harness.

---

## 25. Learning from Less: Measuring the Effectiveness of RLVR in Low Data and Compute Regimes

- **Year / venue:** **MLSys 2026 (Oral)**; arXiv Apr 2026
- **arXiv:** 2604.18381
- **URL:** https://arxiv.org/abs/2604.18381 ·
  https://snorkel.ai/research-paper/learning-from-less-rlvr-low-data-compute-effectiveness/
- **Authors:** Justin Bauer, Thomas Walshe, Derek Pham, Harit Vishwakarma, Armin Parchami,
  Frederic Sala, Paroma Varma (Snorkel AI / Wisconsin)

**Method.** The only systematic study of RLVR *specifically* in the few-hundred-example regime.
Three **procedurally generated** datasets (number counting, graph reasoning, spatial reasoning) so
size, diversity and complexity can each be dialled independently — the verifier is exact by
construction. GRPO, 8 completions per prompt (5 for spatial).

**Reported numbers — the closest published match to our data scale and trainable-parameter count.**
- Base: **Qwen3-4B with LoRA rank 64 / alpha 16 → ~100M trainable parameters.** That is within ~10%
  of our 92M, albeit riding on a 4B frozen backbone.
- Training sets of **100, 200 and 500 examples**, either all-easy or mixed (~33% each easy/medium/hard).
  Test sets of 200 (500 for graph). Compute: 4x A100-80G, **5-12 hours** per run.
- Counting: easy-trained **21.9% (100 ex) → 44.2% (500 ex)**; mixed-trained **44.2% (100 ex) →
  35.5% (500 ex)**.
- Graph: easy **33.3% → 36.5%**; mixed **29.1% → 34.0%**.
- Spatial: easy **49.9% → 53.1%**; mixed **56.6% → 55.7%**.
- **5x sample efficiency: 100 mixed-difficulty examples matched 500 easy-only examples** on counting.
- **Models trained on low-complexity tasks generalise to higher-complexity tasks.**
- **Negative / non-monotonic results:** mixed-difficulty training *degrades* as the set grows on
  counting (44.2 → 35.5), and spatial easy-training peaks at 200 examples and declines at 500.
  More data is not monotonically better in this regime.

**Implementable here: A — the single most directly applicable paper in this file.** ~100M trainable
params, 100-500 training examples, exact procedural verifier, GRPO, modest compute.

**What to implement.** (1) **Mix difficulties in the RL pool rather than starting easy-only** — that
is the 5x lever and it costs nothing. (2) Generate a *procedural* easy tier so our 79 examples are
not the whole pool; the paper's easy→hard generalisation result says cheap synthetic easy problems
transfer upward. (3) Do not assume adding examples helps — run 100/200/500-style sweeps and expect a
peak, because two of their three tasks got worse past the peak.

---

## 26. CYCLE: Learning to Self-Refine the Code Generation

- **Year / venue:** **OOPSLA 2024**; arXiv Mar 2024
- **arXiv:** 2403.18746
- **URL:** https://arxiv.org/abs/2403.18746

**Method.** Code LMs are bad at self-refinement out of the box — shown an execution failure, they
tend to re-emit the same program. CYCLE *trains* the refinement behaviour: the training example is
(prompt, faulty generation, **execution feedback from the test suite**) → corrected program. Trained
at four sizes so the scale trend is visible.

**Reported numbers — one of the very few results reported across a 350M-3B sweep.**
- Sizes: **350M, 1B, 2B, 3B**, trained (not prompted).
- **Up to +63.5% relative improvement in self-refinement** across HumanEval, MBPP and APPS.
- **CYCLE-trained models outperform code LMs with 3x the parameters** on self-refinement — i.e.
  training on verifier feedback is worth roughly a 3x parameter multiplier for this capability.

**Implementable here: A.** 350M is the nearest published size, the signal is exactly our oracles'
output, and "worth 3x parameters" is the kind of claim that justifies the whole lane at 92M.

**What to implement.** Add a *repair* training objective alongside generation: triples of
(problem, broken twin from our mutation engine, checker error message) → verified program. Our
mutation engine gives us the broken twin and the oracle gives us the message, so **all 79 verified
programs immediately become repair training data at whatever multiplicity the mutation engine can
produce** — this is the cheapest way we have of turning 79 examples into thousands.

---

## 27. ExVerus: Verus Proof Repair via Counterexample Reasoning

- **Year / venue:** **ICML 2026**; arXiv Mar 2026
- **arXiv:** 2603.25810
- **URL:** https://arxiv.org/abs/2603.25810
- **Authors:** Jun Yang, Yuechun Sun, Yi Wu, Rodrigo Caridad, Yongwei Yuan, Jianan Yao, Shan Lu, Kexin Pei

**Method.** When a Verus proof fails, ExVerus **extracts a concrete counterexample from the SMT
backend**, validates it, and then guides the model to generalise the counterexample into an
**inductive invariant that blocks it**. The argument is that prior work treats proof generation as
static end-to-end prediction over source text with only a thin pass/fail verifier signal, and never
sees actual program behaviour. Getting semantically meaningful counterexamples out of the SMT solver
is the hard engineering contribution.

**Reported numbers.** Significant improvements in proof accuracy, robustness **and token efficiency**
over the state-of-the-art prompting-based Verus proof generator. (Prompting-based, so no training
cost — this is an inference-time method.)

**Implementable here: B.** Whether it transfers depends entirely on whether our seven proof systems
can be made to emit counterexamples rather than just rejections. Where they can, this is a much
richer signal than a verdict, and it costs no training compute.

**What to implement.** Audit which of the seven proof systems can produce a counterexample / failing
model on rejection, and plumb that into both the prompt and the repair-training triples from item 26.
A counterexample is a *typed, concrete* negative — far more informative than "rejected", and it
composes with the dense partial-credit reward from item 17.

---

## 28. Scaling Flaws of Verifier-Guided Search in Mathematical Reasoning

- **Year / venue:** 2025, arXiv (Feb 2025)
- **arXiv:** 2502.00271
- **URL:** https://arxiv.org/abs/2502.00271
- **Authors:** Fei Yu, Yingru Li, Benyou Wang

**Method.** Compares verifier-guided search (beam/tree search steered by an outcome value model or a
process reward model) against plain **repeated sampling**, as the sample budget grows.

**Reported numbers — a clean negative result about relying on an imperfect verifier at search time.**
- Verifier-guided search wins **when samples are limited**, then shows **diminishing advantage and
  eventually underperforms repeated sampling** as the budget grows. Replicated on **Mistral 7B and
  DeepSeekMath 7B** across **GSM8K and MATH**, with both outcome value models and process reward
  models as the verifier.
- Cause: **verifier failures — an imperfect verifier misranks candidates and prunes away all valid
  paths.** The effect **intensifies on harder and out-of-distribution problems.**

**Implementable here: A as a design constraint.** The critical distinction for us: their verifier is
a *learned* value/reward model, whereas ours is a *sound proof checker*. A sound checker cannot prune
a valid path — it can only be incomplete. **Unit tests, though, behave exactly like their imperfect
verifier.**

**What to implement.** Never let a *learned* reranker (the item 7 head) prune candidates irrevocably —
use it to order oracle calls, not to discard. Keep a fixed fraction of the sampling budget on
unguided repeated sampling as a hedge, and compare the two arms; this paper says the guided arm loses
at high budget and we should be able to see the crossover in our own numbers.

---

## 29. A Benchmark for Vericoding: Formally Verified Program Synthesis

- **Year / venue:** **POPL 2026 (Dafny workshop)**; arXiv Sep 2025
- **arXiv:** 2509.22908
- **URL:** https://arxiv.org/abs/2509.22908
- **Data:** full benchmark + all experimental results released as supplementary material

**Method.** Defines *vericoding* — generating code from a **formal specification** with a proof it
meets that spec — as opposed to "vibe coding" from natural language. Builds the largest
multi-system benchmark of its kind.

**Reported numbers.**
- **12,504 formal specifications: 3,029 Dafny, 2,334 Verus/Rust, 7,141 Lean.** 6,174 are new/unseen.
- **55,397 vericoding experiments** reported.
- Off-the-shelf LLM success: **27% Lean, 44% Verus/Rust, 82% Dafny.** The spread across proof systems
  is enormous and is mostly about how much automation the system provides, not about the problems.
- Pure Dafny verification progressed **68% → 96% over one year**.
- **Adding natural-language descriptions does not significantly improve performance.**

**Implementable here: A as a data source, B as a result.** With seven proof systems, the per-system
success spread (27% vs 82%) is the most actionable number here: **which proof system we target
changes the measured result more than most method choices will.**

**What to implement.** Two things. (1) Mine this benchmark for extra spec/proof pairs in whichever of
our seven systems it overlaps — 12.5k specifications against our 79 examples is a large multiplier,
and it is released. (2) Report our results **per proof system**, never pooled, because pooling across
systems with a 27%-82% baseline spread will make any method effect unreadable. (3) Do not spend
effort adding natural-language problem descriptions to the training format; the measurement says it
does not help.

---

## Synthesis — what this literature says to do at 92M / 46M tokens / 79 examples

**Ordering.** Re:Form (10) measured SFT-on-verified-data at ~35 points vs ~15 for the RL stage on top;
Yue et al. (6) show RL only sharpens a distribution the base model already has, and our base model has
almost none. **Data stages before RL stages** is the consistent reading.

**The three cheapest high-value actions, all supported by more than one paper:**
1. **Rejection-sampling fine-tuning, deduplicated by distinct proof structure, pooled across all seven
   proof systems** (19). RFT gains *grow* as the base model gets weaker, which is the only favourable
   scaling law in the file.
2. **Repair training from mutation-engine twins plus checker error messages** (26, 27, 16). Turns 79
   examples into thousands, and CYCLE measured it as worth ~3x parameters.
3. **Dense partial-credit reward from per-obligation pass counts with the density correction** (17),
   because at 92M the binary reward is almost always zero, and that is exactly where VeRPO's gain was
   largest (+8.83 on the hardest benchmark vs +1.46 on the easiest).

**The three things not to do:**
1. **Do not build a self-play proposer** (15) — the measured gain shrinks monotonically with model size
   and is already only +3.2 at Llama-8B.
2. **Do not run a naive STaR loop from random weights** (5) — there is a documented entry requirement
   and we are below it; cold-start by rationalising the verified programs instead.
3. **Do not trust a style/lint/format reward term on its own** (1) — it reliably buys shorter outputs
   rather than correct ones.

**The two controls that make any result we report believable:**
- A **random-reward arm** at identical budget (13). Random rewards captured ~74% of the true-reward
  gain on Qwen2.5-Math-7B; without this control, "+N points from our verifier" means nothing.
- A **metamorphic audit and a static leakiness audit of our own oracles** (18, 21), reported as
  false-negative rate and broken-twin-acceptance rate. The leakiness audit predicts gamed tasks at
  Spearman 0.80 *before* training compute is spent.

**Scale honesty.** Only four items here are at or below ~1B parameters with small data: item 1
(0.6B-1B, +13pp), item 2 (150M/400M from scratch, +2 to +7pp pass@1), item 20 (1M params), and item 25
(~100M trainable, 100-500 examples). Everything else is 7B and up, and items 6, 13 and 15 each give a
specific reason why 7B+ results should not be extrapolated downward.
