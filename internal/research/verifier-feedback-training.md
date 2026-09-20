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
