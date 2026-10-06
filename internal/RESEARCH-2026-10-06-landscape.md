# The landscape, and what it decides (2026-10-06)

Written 2026-10-06 21:20Z, after G8 (higher-order calls) landed, on the operator's direction to finish, zoom out
over the whole project, and decide from the landscape of competing work. Every competitor number below was read on a
fetched page on 2026-10-06; the pages are linked. Our own numbers were measured the same evening from `t/AGREEMENT.md`
(84 tasks, the clean-clone matrix at eb0e8102) and `t/COVERAGE-nl.md`. This builds on
`internal/RESEARCH-2026-10-05-what-to-steal.md`, which ranked what to borrow. This note ranks who competes and what that
changes in our order of work.

## 1. Who does what we do

| System | What it does | Best published number | Openness | Against t |
|---|---|---|---|---|
| [AxDafny](https://arxiv.org/abs/2606.32007) | verifier-guided repair writing Dafny code, invariants, assertions | 92.7% DafnyBench | paper only | one prover, frontier model, no refuted mutant |
| [DafnyPro](https://arxiv.org/abs/2601.05385) | diff checker, invariant pruner and hint library for Dafny | 86% DafnyBench (Claude 3.5 Sonnet); fine-tuned Qwen 7B 68%, 14B 70% | code not found | small models reach 68-70% on one prover |
| [AlphaVerus](https://arxiv.org/abs/2412.06176) | self-improving Dafny-to-Verus translation; a learned critique model against `assume(false)` | 33% Verified-HumanEval (LLaMA-3.1-70B) | paper CC BY 4.0 | nearest to t's translation idea, one direction; its critique model is what t's twin does deterministically |
| [AutoVerus](https://arxiv.org/abs/2409.13082) | multi-agent Verus proof generation | over 90% of 150 Verus-Bench tasks | MIT (per the sweep) | Verus only |
| [Clover](https://arxiv.org/abs/2310.17807v4) | consistency among code, docstring and Dafny annotations | 87% of correct instances accepted, 0 false positives on adversarial ones | not stated | the same spirit as the twin, checked by consistency, not refutation |
| [Vericoding](https://github.com/Beneficial-AI-Foundation/vericoding) | 12,504 specs: Dafny 3,029, Verus 2,334, Lean 7,141 | off-the-shelf LLMs: Dafny 82%, Verus 44%, Lean 27% | MIT | the largest multi-verifier benchmark; three provers, not a lowering system |
| [AlgoVeri](https://github.com/haoyuzhao123/algoveri) | 77 classical algorithms, identical contracts in Dafny, Verus, Lean | Gemini-3 Flash: Dafny 40.3%, Verus 24.7%, Lean 7.8% | Apache-2.0 | "one spec, several verifiers", but the spec is hand-ported per language |
| [Why3](https://www.why3.org/) | WhyML dispatched to SMT solvers and Rocq/PVS/Isabelle; extracts OCaml, C | (a platform) | free software | the incumbent multi-prover platform; several solvers over one verification condition, no LLM writer, no refutation |
| [Dafny's compilers](https://github.com/dafny-lang/dafny) | verified Dafny to C#, Go, Python, Java, JavaScript | (a toolchain) | MIT | t's Dafny leg could ship programs in five languages |
| [KaRaMeL](https://github.com/FStarLang/karamel) | Low* (F*) to readable C; HACL*, Everest | (a toolchain) | Apache-2.0 / MIT | the route from t's F* leg to shipped C |
| Codex CLI, Gemini CLI, Goose, OpenHands, Open Interpreter, Khoj, AnythingLLM | terminal and desktop assistants | Terminal-Bench 2.0: 82.2% and 80.2% for the two cloud CLIs; none published for a small local model | mostly Apache-2.0 / MIT | none verifies what it writes; dawnr's 141 of 161 is on its own set, not comparable |

What the table says, read plainly:

1. **No system targets more than three verifiers, and none pairs each proof with a refuted mutant.** Lean is the weak
   leg on every multi-verifier benchmark. No LLM system was found that lowers one spec to SPARK, Frama-C, Rocq or F*.
2. **The multi-prover incumbent (Why3) shares one verification condition across solvers.** t's legs are independent
   kernels with their own logics (Dafny/Boogie, Verus/Z3 through Rust's type system, SPARK/GNATprove, Frama-C/WP,
   Lean's kernel, Rocq's kernel, F*), so agreement among them is evidence that a single VC cannot give.
3. **Every strong verified-code number comes from a frontier model on one prover.** The best small-model numbers
   (DafnyPro's 7B-14B at 68-70%) are on Dafny alone.

## 2. Where we stand (measured 2026-10-06)

| Measure | Value |
|---|---|
| committed tasks | 84 (88 with G8; its matrix is running) |
| verified with the twin refuted in all seven kernels | 36 of 84 (43%) |
| twin refuted, as a share of the cells whose real is verified | 100% in every kernel (Dafny 84 of 84, Verus 76, F* 53, SPARK 50, Rocq 43, Lean 40, Frama-C 36) |
| tasks a kernel abstains on, by name | Dafny 0, Verus 7, F* 29, SPARK 31, Rocq 41, Lean 42, Frama-C 47 |
| natural-language problems in t's fragment | 2,959 of 4,239 function-shaped (69.8%); 10,618 of 20,509 stdin-shaped |

Why the abstentions are where they are: the 10/06 landings (compositional types through higher-order calls) went
into Dafny and Verus first, and the other five kernels refuse them by name. Counted by the SPEC section each refusal
names, over the 84 tasks:

| kernel | The library (v1) | Compositional types | Comprehensions | Strings (v2) | Early exits | Finite sets | other |
|---|---|---|---|---|---|---|---|
| Lean | 18 | 14 | 7 | 3 | 2 | 2 | 0 |
| Rocq | 18 | 14 | 7 | 3 | 2 | 0 | 1 |
| Frama-C | 18 | 14 | 7 | 3 | 2 | 2 | 5 |
| SPARK | 7 | 10 | 7 | 4 | 2 | 2 | 3 |
| F* | 7 | 10 | 7 | 4 | 2 | 0 | 3 |

So the language grew from 39 to 88 tasks in a day, and the claim that sets t apart, seven independent kernels, now
covers fewer than half of them. Breadth has outrun depth.

## 3. Decisions

**D1. Depth before more breadth: the five kernels carry what the language already has.** Order, by tasks unlocked:
the library (v1) in Lean, Rocq and Frama-C (18 tasks each; SPARK and F* already carry 11 of the 18), then
compositional types (14 in Lean, Rocq, Frama-C; 10 in SPARK, F*), then comprehensions (7 in all five), then the
string library's second wave, early exits and sets. Each landing is registered in a PREDICT file with its bar,
measured by the clean-clone matrix, and keeps rule 2 (an honest refusal beats a false verdict). Why first: decision
D2's table is worth publishing only if the SPARK, Frama-C, Lean, Rocq and F* columns hold verdicts rather than
refusals, and those columns are the ones no competitor can fill. Bar for the programme: all-seven agreement from 36
of 84 to at least 70 of the committed tasks, with no verified cell whose twin is not refuted.

**D2. An external, aligned benchmark in seven kernels: AlgoVeri first.** AlgoVeri (Apache-2.0) states 77 classical
algorithms with identical contracts in Dafny, Verus and Lean, and its best published model reaches 40.3% / 24.7% /
7.8% there. We transcribe its contracts into t (the data stays outside this repository, fetched by a script, with
credit), record which ones t can state today and why the rest cannot, write a reference t program for each one it
can state, and publish `t/ALGOVERI.md`: per algorithm, the verdict in each of the seven kernels with the twin. This is
a measurement of the language and its kernels, not of a model. A model's pass rate on it comes later and is audited
for contamination first (`heldout_audit.py`, the 10/05 sweep's condition). The contracts t cannot state become the
language queue, replacing guesses from the census alone. Vericoding's 3,029 Dafny specs follow as a spec-lift census
(how many t can state), since 12,504 reference programs are not ours to write.

**D3. Twin refutation as a headline metric.** The share of verified cells whose twin is refuted (100% in all seven
today) and the all-seven count go into `t/AGREEMENT.md`'s summary and the README, beside the proof counts. This
answers Clover's and AlphaVerus's approach (consistency checks or a learned critic) with a deterministic,
kernel-checked number.

**D4. A proved program ships: `t build`.** The verified Dafny leg is compiled with Dafny's own back ends (Python, Go,
JavaScript, C#, Java) and checked against the interpreter on the task's witnesses and tests; F* to C through
KaRaMeL is the second route. Today the hand-back writes Python that is "checked against t, not itself proved"; this
gives the stronger path where the toolchain exists. The trusted base is stated plainly: the Dafny compiler is not
verified.

**D5. dawnr's agent benchmarks wait.** Terminal-Bench 2.0 and OSWorld would give the first small-model, fully
offline numbers (none is published), but the operator paused assistant work for t at 10/06 08:10Z, and D1 and D2 are
the work only this project can do. This is revisited when D2's table is published.

**Rejected for now, with reasons.** Why3 as an eighth kernel: its back ends are SMT solvers over one verification
condition, so they would not add an independent kernel; the comparison is argued in the README instead. Carcara
(Alethe proof checking, from the 10/05 sweep) would put "proved" on a small checker. It fits the trust goal, but it
needs cvc5 proof output wired through three kernels first, and comes after D1.

## 4. Order of work

1. D3 (an hour): the metric in the matrix summary and the README.
2. D1, the library (v1) in Lean, Rocq and Frama-C, each registered and measured.
3. D2's first step, the contracts transcribed and the reach recorded, run beside D1. It shows which constructs the
   classical algorithms need, and that feeds D1's order and the language queue (G9 records and options next).
4. D4 once D1's first landing is in.
