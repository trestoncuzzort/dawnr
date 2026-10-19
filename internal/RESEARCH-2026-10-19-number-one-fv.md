# The number-one formal-verification assistant on minimal resources: the sweep of 2026-10-19

Registered 2026-10-19 20:20Z. Own record first (`internal/RESEARCH-2026-10-14-landscape.md`,
`internal/RESEARCH-2026-10-07-landscape-survey.md`, `internal/RESEARCH-2026-10-05-what-to-steal.md`,
`t/PREDICT-2026-10-18-v6.md`), then the paper library, then the web (every page named in section 7 was fetched
on this date). Nothing below is measured yet; section 5 is the queue, each row with the number that would show it
did nothing.

## 0. The claim, written so it can be false

"The number-one formal-verification AI that runs on minimal resources" is not one number. It is four, each on a
public set, each at a stated budget:

| claim | public yardstick | budget that counts as minimal | where dawnr is today |
|---|---|---|---|
| verified answers from a natural-language task | the 95-problem development panel; then AlgoVeri's 21 statable contracts and the 488 Dafny Vericoding tasks lifted into t | one 4B model at 8 bits, at most 17 calls a problem, the seven kernels on one laptop | 6 clean / 3 all-seven of 95 (v5); 17 of 182 held out |
| a wrong program never gets a proof | kernel-checked mutant survival on the lifted public sets | the same | 94.8% of 15,148 mutants killed on Vericoding-Dafny, 54 of 488 specs admit a survivor; false-accept floor 23% on the twin pairs (E1) |
| the proof is worth more than a test | the matched-budget verified-vs-raw ablation (E3) | one card, three seeds | not run |
| anyone can run it | install, answer, replay a certificate offline | a CPU with 8 GiB; training on an 8 GB card | works: Q8 at ~15 tokens a second, 4B QLoRA at 38 s a step on the 5050 |

The first row is the one the field scores. The second and fourth are where nothing in the literature competes.

## 1. Who leads today, lane by lane (fetched 2026-10-19)

**Verified code from a specification, three languages.** The Vericoding benchmark (arXiv:2509.22908, MIT; 12,504
specifications: 3,029 Dafny, 2,334 Verus, 7,141 Lean) reports off-the-shelf frontier models at 82% Dafny, 44% Verus,
27% Lean, and that 9% of the successful specs were too weak. AlgoVeri (arXiv:2602.09464, Apache-2.0; 77 algorithms
with identical contracts in all three) reports 40.3% Dafny (Gemini-3 Flash), 24.7% Verus, 7.8% Lean, with iterative
repair tripling the Dafny rate. Both leaderboards are CSVs of frontier-model runs, not small models.

**Dafny.** AxDafny (arXiv:2606.32007): verifier-guided repair with Gemini-3.1-Pro, 92.7% on DafnyBench's proof-hint
task, 56.4% on 250 competition problems where direct GPT-5.5 gets 11.6%. DafnyPro (arXiv:2601.05385, POPL 2026):
diff-checker + invariant pruner + hint augmentation lifts Claude 3.5 Sonnet 70% to 86%; **a fine-tuned Qwen 7B
reaches 68%, 14B 70%**, trained on larger models' DafnyPro-enhanced attempts (weights not released). ATLAS
(arXiv:2512.10173): 2,751 verified Dafny programs synthesised from TACO Python solutions, decomposed into 19,385
training examples of six kinds (NL to code 2,751; NL to spec 5,225; spec to code 2,751; spec repair 2,353;
implementation repair 4,562; proof infilling 1,743); **Qwen2.5-Coder-7B goes 32.4% to 56.9% on DafnyBench
(pass@10) and 15.8% to 65.8% on DafnySynthesis (pass@5)**; nothing released. Re:Form (arXiv:2507.16331, code at
github.com/ReFormDafny/ReForm, models on Hugging Face, no licence file): Qwen2.5 0.5B to 14B, SFT on 20k
Claude-annotated functions then GRPO with a subset reward the verifier checks as two implications (generated
precondition no stronger, generated postcondition no weaker); 14B RL 14.0% on DafnyComp where Claude gets 2.7%;
16 to 64 A800s. **Verifier-grounded agentic RL (arXiv:2610.19298, this month)**: Qwen3 1.7B to 14B and a 35B MoE,
GRPO against a live verifier, reward = weighted fraction of obligations discharged (postconditions 1.0,
preconditions and safety 0.5, invariants and termination 0.25) minus 1.0 for a changed specification, minus 3.0 for
assume/axiom/admit, plus 2.0 for verified with the proof intact; **binary pass/fail reward 71.0% against the dense
reward's 93.5%** at 35B on DafnyBench; at 4B, annotation repair 26.6% to 51.6% and code generation 43.4% to 52.5%;
nothing released. The MIT thesis (arXiv:2605.30914): RLVR on APPS-derived Dafny went 2.2% to 58.1% by
specification hacking, 9.7% to 31.1% after the weak tasks were removed.

**Verus.** KVerus (arXiv:2605.03822, ASE 2026): knowledge base + error-driven refinement, 80.2% on three single-file
benchmarks against AutoVerus 56.9%, 23 functions accepted upstream into Asterinas; no code named. ExVerus
(arXiv:2603.25810): counterexamples generated on proof failure and fed back as repair guidance; beats the best
LLM-based generator on success, cost and robustness. Seed-set scaling (arXiv:2602.04910): 6.9M Rust programs with
spec and proof, a fine-tuned Qwen2.5-Coder-32B with a better cost-proof trade-off than Claude Sonnet 4.5.
microsoft/verus-proof-synthesis (MIT) holds AutoVerus, Verus-Bench (150) and VeruSAGE-Bench (849), OpenAI keys only.

**Lean.** Pythagoras-Prover-4B (arXiv:2606.12594, Apache-2.0, Qwen3-4B-Base, SFT data released, a GGUF exists):
86.1% pass@32 on MiniF2F against DeepSeek-Prover-V2-671B's 82.4%, from Augmented Lean Formalisation (2M mutated
statements, self-distilled, curriculum SFT within 8k tokens). OProver-32B (arXiv:2605.17283): iterative post-training
where repair trajectories become SFT data and unresolved cases become RL; 93.3% MiniF2F pass@32. Leanstral 1.5
(Mistral, July 2026): 119B total, 6.5B active, 587 of 672 Putnam at 4M tokens a problem. VERINA (ICLR 2026, 189
tasks): o3 72.6% code, 52.3% spec, 4.9% proof; Goedel-Prover-V2-32B 11.2% proof. The thesis's verifier-guided
scaffold (decomposed subgoals + reviser) lifts a fixed model 46.2% to 69.2% on a Vericoding pilot.

**Rocq.** AutoRocq (FSE 2026): an agent in a feedback loop with the kernel on SV-COMP and Linux modules. Quarry
(OOPSLA 2026): decomposition ranked by a CoqHammer-solvability model, +7 to 13 points. Strat2Rocq: +13.4% for
CoqHammer. **Frama-C.** AutoACSL (arXiv:2606.20969): LLM + code property graph, 96% full proof with Gemini-3 on 604
programs; the ECOOP FTfJP paper (arXiv:2602.13851) finds rule-based ACSL still more reliable than LLMs. **SPARK.**
Marmaragan (2025, GPT-4o 50.7%) and an AdaCore blog; nothing in 2026. **F\*.** Nothing new since PoPAI (2024).

## 2. What the small-model lane says, in one table

| system | model | task | before → after | the lever |
|---|---|---|---|---|
| verifier-grounded RL | Qwen3-4B | DafnyBench annotation repair | 26.6 → 51.6 | dense per-obligation reward, 20-turn episodes |
| verifier-grounded RL | Qwen3-4B | DafnyBench code generation | 43.4 → 52.5 | the same |
| ATLAS | Qwen2.5-Coder-7B | DafnyBench / DafnySynthesis | 32.4 → 56.9 / 15.8 → 65.8 | 2,751 verified programs decomposed into 19,385 sub-task rows, failed attempts kept |
| DafnyPro | Qwen 7B | DafnyBench | base not given → 68 | distilled from a larger model's hint-augmented attempts |
| Re:Form | Qwen2.5-14B | DafnyComp (out of domain) | 8.3 (SFT) → 14.0 (RL) | subset reward checked by the verifier as implications |
| Pythagoras | Qwen3-4B-Base | MiniF2F pass@32 | — → 86.1 | 2M mutated statements, self-distillation, curriculum |
| dawnr v5 | Qwen3.5-4B | 95 dev problems, NL → t → seven kernels | 6 clean / 3 all-seven | 4,189 gate-admitted rows, one SFT pass |

Three levers recur at this size and none of them is in dawnr's recipe: decomposing each verified program into
several sub-task rows, a dense verifier reward instead of a tier, and repair turns driven by the verifier's own
counterexample. dawnr's frozen route (`t/spec_first.py`, `t/recipes/v6_server_route.py`) samples and never repairs;
its RL reward (`t/rl_reward.py`) is a tier (0, 0.05, 0.10, 0.50, 0.75, 1), and the 2026-10-03 run moved the training
reward 0.240 to 0.255 and nothing unseen.

## 3. What nobody else does, still (unchanged from 2026-10-14, re-checked)

Seven kernels that must all agree, a one-edit twin refuted at a measured witness in every leg, a published
false-accept rate, refusal scored as its own outcome, and the whole thing on one laptop. The nearest are SWE-Proof's
twins on three backends and AlgoVeri's three kernels. Every system in section 1 that beats 80% does it with a
frontier model or a 32B-plus model and a closed harness; every small-model result is single-kernel Dafny. The
defensible claim is therefore not "highest Dafny number" but "the best verified-answer rate per parameter and per
watt, with an audited false-accept rate, that anyone can reproduce on a laptop" — and the public sets in section 0
are how it gets measured instead of asserted.

## 4. What is not taken, and why

Leanstral, OProver, KVerus, AutoVerus, AxDafny as systems: frontier or 32B-plus, or OpenAI-keyed, or unreleased.
Re:Form's 20k Claude-annotated functions, Vericoding's `vericoded` solutions and any GPT output: not rows, by the
rules (`t/RUN-NEXT.md`, Apache/MIT sources only, no GPT text in rows); their *tasks* are fair game. A prover model
inside the gate (Pythagoras-4B filling Lean goals): not before the mvcgen+grind probe (survey item 1), because an
agent in the loop is what "The Prover Is the Judge" shows bypassing weak checks. Retrieval of proved rows into the
prompt: measured 2026-10-01, did not help the 4B.

## 5. The queue, decided

Each row is its own PREDICT file before it runs. Costs are for this laptop (16 cores, 15 GB, one 8 GB card).

| | what | from (licence) | where it goes | judged by (the falsifier) | cost |
|---|---|---|---|---|---|
| 1 | **decomposed rows**: every gate-admitted training program also becomes a spec-to-body row, an invariant-infilling row (annotations stripped, the verified original as the target) and, where a survivor was found and repaired, a spec-repair row; failed attempts with the kernel's own message kept as repair rows | ATLAS's six-way decomposition (arXiv:2512.10173; method only, nothing released); the 4B's +25 on annotation repair (arXiv:2610.19298) | `t/recipes/v7_decomposed_rows.py` → a v7 row file at the exact v5 recipe | the frozen development protocol: clean ≥ 7 and all-seven ≥ 3 of 95, else the rows did nothing | a script; 13 to 16 h of training |
| 2 | **a repair turn in the route**: when the gate refutes, the witness input and the failing clause go back to the model for at most two more calls inside the 17 | ExVerus (arXiv:2603.25810), AxDafny (arXiv:2606.32007); AlgoVeri's tripled Dafny rate under repair | a `v7_server_route.py` beside the frozen one; both arms (v5, candidate) run it | paired development run under the new route: candidate clean > v5 clean, all-seven not lower | GPU-served Q8 on the 5050, hours |
| 3 | **dense verifier reward**: fraction of obligations discharged per kernel, weighted; a changed specification −1, an assume or a dropped invariant −3, verified with the twin refuted +2; Re:Form's two implications for spec rows | arXiv:2610.19298 (formula in its section 3; nothing released), arXiv:2507.16331 | `t/rl_reward.py` and `t/rl_grpo.py`, Dafny + interpreter twin as the rollout reward, seven kernels only at evaluation | the 2026-10-03 registration re-run: an unseen development number must move (clean ≥ 7), not only the band reward | rollouts dominate; days |
| 4 | **mutated tasks**: Augmented-Lean-Formalisation applied to t: mutate admitted spec-program pairs into new verified tasks through the twin machinery, self-distil | Pythagoras (arXiv:2606.12594, Apache-2.0, data released) | `t/twins/` tooling → rows | rows admitted by the gate; then row 1's falsifier | a script; training |
| 5 | **the public yardstick**: the t-writing model on AlgoVeri's 21 contracts at 15 rounds against the per-language baselines (40.3 / 24.7 / 7.8), and on the 488 lifted Vericoding-Dafny tasks; budget-efficiency curves (verified against tokens) | AlgoVeri harness (Apache-2.0), own lifts (`t/algoveri`, `t/vericoding`) | `t/e3_vericoding_aggregate.py`, a new AlgoVeri runner | the Dafny leg matches direct Dafny; the Verus and Lean legs beat direct Verus and Lean | inference, hours |
| 6 | E2 common-mode audit (cvc5 beside Z3), the Lean mvcgen+grind probe, then E3 | own plan (2026-10-14) | kernels | agreement under solver change; integer_exponential and bubble_sort in Lean | days |

Row 1 first: it is the user's rule for v6 (same recipe, better data), it needs no teacher, no key, no new dependency,
and it is judged by the instrument already frozen. Row 2 second because it is cheap and the field's most consistent
inference-time gain. Row 3 only after a data step moved an unseen number, since RL on this student has not yet.

## 6. What the corrective candidate decides (running now)

The interrupted C2 grade of the corrective candidate and a paired local re-grade of v5's development answers are
ran on this laptop's seven kernels (`t/out/v6-20261018/local-grade-2026-10-19/`). **Measured 21:05Z: 6 clean, 2 all-seven against v5's 6 and 3; C2 fails; the two lost problems were never answered in t** (the dated section at the end of `t/PREDICT-2026-10-18-v6.md`). If the candidate had cleared C2
(clean ≥ 7, all-seven ≥ 3), the contract repairs were the lever and row 1 builds on the corrected rows; if not, row
1 starts from the corrected 4,089 rows anyway, because the decomposition is a different lever.

## 7. Receipts

arxiv.org/abs/2509.22908, github.com/Beneficial-AI-Foundation/vericoding (MIT), arxiv.org/abs/2602.09464 and
github.com/haoyuzhao123/algoveri (Apache-2.0; Dafny 4.11, Verus 0.2025.01.13, Lean 4.25.0-rc2),
arxiv.org/abs/2606.32007, arxiv.org/abs/2601.05385, arxiv.org/html/2512.10173, arxiv.org/html/2507.16331 and
github.com/ReFormDafny/ReForm (no licence file), arxiv.org/html/2610.19298, arxiv.org/abs/2605.30914 (library copy),
arxiv.org/abs/2605.03822, arxiv.org/abs/2603.25810 (library copy), arxiv.org/abs/2602.04910,
github.com/microsoft/verus-proof-synthesis (MIT), arxiv.org/abs/2606.12594 and
huggingface.co/Pythagoras-LM/Pythagoras-Prover-4B (Apache-2.0), arxiv.org/abs/2605.17283 (library copy),
arxiv.org/abs/2608.29841, arxiv.org/abs/2501.06283, arxiv.org/abs/2606.20969, arxiv.org/abs/2602.13851; Leanstral
1.5 and the Rocq items from search results only (not fetched).
