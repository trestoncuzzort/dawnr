# Pinning down intent with examples and tests, not prose

Research file backing the hypothesis: **putting the problem's own input/output examples
in the prompt stops the model specifying the wrong function.**

Failure being attacked: given an English sentence plus a handful of ground-truth I/O
assertions, the model writes a *confident specification of a different function* —
e.g. asked whether `x` is a sum of non-zero powers of two, it specified `r == x + 1`.
Seven proof systems then happily prove the wrong thing.

Rating scale for "implementable here":
- **A** — directly liftable into the current pipeline this week.
- **B** — needs adaptation (different language/harness) but the mechanism transfers.
- **C** — conceptual support / evidence only, nothing to lift.

---

## 1. Interactive Code Generation via Test-Driven User-Intent Formalization (TiCoder, original)

- **Year:** 2022
- **Venue/id:** arXiv:2208.05950 (Microsoft Research; Lahiri, Naik, Sakkas, Choudhury, von Veh, Musuvathi, Inala, Wang, Gao)
- **URL:** https://arxiv.org/abs/2208.05950

**Technique.** The user gives an informal NL intent. The LLM generates both candidate
*code* and candidate *tests*. Tests are chosen to maximally **discriminate between
divergent code candidates** (a test that all candidates agree on tells you nothing;
a test that splits the candidate set in half is the informative one). The user answers
pass/fail on the proposed test, and that answer prunes the candidate space and is fed
back into the prompt as a partial formalization of intent. Iterate.

**Numbers.** Reported ~45.97% relative improvement in pass@1 of generated code within 5
user interactions, and ~38.21% improvement in the pass rate of the *generated tests*,
over the base model, on MBPP/HumanEval-derived benchmarks.

**Implementable here: A.** This is the closest published relative of the hypothesis,
but note the *direction*: TiCoder uses tests to disambiguate because the prose alone
is ambiguous. Our setting already *has* ground-truth tests — so we are TiCoder with a
free, perfect oracle and zero interaction cost.

**What to implement.** Discriminative selection: when the model's spec and the ground
truth examples disagree, do not just paste all examples — paste the examples that
*separate* the specified function from the intended one. Concretely: evaluate the
model's candidate spec as a predicate on each ground-truth example, and put the
*failing* ones in the repair prompt with "your spec says P(x)=…, the problem says …".

---

## 2. LLM-Based Test-Driven Interactive Code Generation: User Study and Empirical Evaluation

- **Year:** 2024
- **Venue/id:** IEEE TSE 2024 (doi 10.1109/TSE.2024.3428972); arXiv:2404.10100. ICSE 2024 Companion version: doi 10.1145/3639478.3643525
- **URL:** https://arxiv.org/abs/2404.10100 · PDF: https://www.engineering.upenn.edu/~asnaik/assets/papers/tse24_ticoder.pdf

**Technique.** The full journal version of TiCoder: two interaction modes,
**TiCoder-PassFail** (user answers only PASS/FAIL on a proposed test) and
**TiCoder-Output** (on FAIL the user supplies the expected output — i.e. hands over a
ground-truth I/O example). Plus a mixed-methods user study with 15 programmers.

**Numbers.** Users of the workflow were significantly more likely to *correctly
evaluate* AI-generated code and reported significantly lower task-induced cognitive
load. The empirical arm reports pass@1 gains on HumanEval/MBPP across several models
with a small interaction budget (single-digit number of queries).

**Implementable here: A.** The `TiCoder-Output` mode is exactly our setting: the
expected output is already known. The paper's finding that *output-valued* feedback
beats boolean feedback is the direct argument for putting the full `f(in) == out`
assertion in the prompt rather than just "your spec is wrong".

**What to implement.** Two prompt arms to A/B: (a) boolean — "your specification
disagrees with the problem's tests"; (b) output-valued — the literal failing
assertions. Expect (b) to win; that is the paper's core result transplanted.

---

## 3. Programming by Examples: Applications, Algorithms, and Ambiguity Resolution

- **Year:** 2016
- **Venue/id:** IJCAR 2016 keynote paper, LNCS 9706 (Sumit Gulwani, Microsoft) — doi 10.1007/978-3-319-40229-1_2
- **URL:** https://link.springer.com/chapter/10.1007/978-3-319-40229-1_2

**Technique.** The canonical statement of the PBE problem. Examples are a *succinct but
under-specifying* form of intent: a huge set of programs is consistent with any small
example set. Two families of fixes are laid out — (i) ranking/syntactic bias over the
hypothesis space so the "natural" program wins, and (ii) user interaction to resolve
the residual ambiguity (asking about distinguishing inputs).

**Numbers.** No single headline number; this is the framing paper (FlashFill lineage).
The operative claim is that users supply **one or two** examples in practice, and that
ambiguity resolution, not search, is the bottleneck.

**Implementable here: C (framing), B (ranking idea).**

**What to implement.** The honest caveat for our experiment write-up: examples
*under-specify*. Our examples cannot uniquely pin the function — they can only *rule
out* the wildly wrong one the model currently writes. Frame the hypothesis as
"examples as a **falsifier** of a wrong spec", not "examples as a specification".

---

## 4. When Many-Shot Prompting Fails: An Empirical Study of LLM Code Translation

- **Year:** 2025
- **Venue/id:** arXiv:2510.16809; Proc. 1st Workshop on Code Translation, Transformation, and Modernization (doi 10.1145/3786180.3788314)
- **URL:** https://arxiv.org/abs/2510.16809

**Technique.** Sweeps the number of in-context examples from zero-shot up into the
many-shot regime for LLM code translation, measuring functional correctness (Pass@1)
rather than similarity metrics.

**Numbers.** Finds a **non-monotonic** curve: an optimal band around **5–25 examples**
maximises Pass@1 and cost-effectiveness; beyond that, Pass@1 *consistently declines*.
The authors attribute the decline to noise / conflicting signal crowding out the task.

**Implementable here: B — and this is a counter-example paper, deliberately included.**

**What to implement.** Cap the number of pasted examples. Our problems come with "a
handful" of assertions, which lands inside the good band — but if we ever start
auto-generating extra examples, this paper says more is not better. Log the example
count as a covariate so a null result can be checked against dosage.

---

## 5. Can Large Language Models Transform Natural Language Intent into Formal Method Postconditions? (nl2postcond)

- **Year:** 2024
- **Venue/id:** PACMSE / FSE 2024 (doi 10.1145/3660791); arXiv:2310.01831 (Endres, Fakhoury, Chakraborty, Lahiri — Michigan + Microsoft Research)
- **URL:** https://arxiv.org/abs/2310.01831 · https://dl.acm.org/doi/10.1145/3660791

**Technique.** Defines `nl2postcond`: take an informal NL description plus a reference
implementation plus a set of **test inputs**, and have the LLM emit a formal
postcondition as a program assertion. Crucially it introduces two *separate* metrics —
**correctness** (the postcondition holds on the reference implementation, checked by
running the tests) and **discriminative power** (the postcondition actually *rejects*
buggy implementations). A postcondition that is true but vacuous scores zero on the
second metric. The tests are hidden from the generating LLM and used only to score.

**Numbers.** Generated postconditions were generally correct and discriminative;
the headline applied result is **64 real-world historical bugs caught from Defects4J**
by postconditions inferred from natural language alone.

**Implementable here: A.** This is our exact problem — NL intent → formal spec — and
it hands us the *metric* we are missing. Our `r == x + 1` failure is a spec with high
apparent confidence and **zero discriminative power against the wrong function**; the
paper's two-axis metric is precisely what would have caught it.

**What to implement.** Score every generated specification on two axes, not one:
(1) does the spec hold on all ground-truth examples (correctness), and (2) does the
spec *reject* a deliberately mutated/wrong program (discriminative power). Gate the
proof systems behind axis (1): never send a spec to the seven provers if it does not
already agree with the problem's own assertions. This alone kills the `r == x + 1`
class of failure before any prover time is spent.

---

## 6. Beyond Postconditions: Can LLMs infer Formal Contracts for Automatic Software Verification? (NL2Contract)

- **Year:** 2025
- **Venue/id:** arXiv:2510.12702 (under submission)
- **URL:** https://arxiv.org/abs/2510.12702

**Technique.** Direct successor to nl2postcond, and the one that matters for a
*verification* pipeline. Observes that when you feed an LLM-inferred **postcondition
alone** to an automatic verifier, the verifier proposes invalid inputs and produces
**false alarms** — because the missing *precondition* lets it explore inputs the
programmer never meant. So it has the LLM infer a full functional contract
(precondition **and** postcondition) and measures soundness, bug-discriminative power,
and usability-in-verification.

**Numbers.** (1) LLMs are generally effective at generating contracts sound for all
possible inputs; (2) contracts are expressive enough to discriminate buggy from correct
behaviour; (3) **verifiers supplied with full contracts produce fewer false alarms than
with postconditions alone**; inferred preconditions align well with developer intent.

**Implementable here: A.** We have seven provers, so we are squarely in the regime this
paper is about. If our specs are postcondition-only, we are paying the false-alarm tax
it describes.

**What to implement.** Make the model emit a precondition alongside the postcondition,
and derive/validate the precondition against the *domain of the ground-truth examples*
(e.g. if every example has `x >= 1`, the precondition should not be `true`). Report
prover false-alarm rate before/after as a second outcome measure alongside conversion.

---

## 7. HumanEvalComm: Benchmarking the Communication Competence of Code Generation for LLMs and LLM Agents

- **Year:** 2024/2025
- **Venue/id:** ACM TOSEM (doi 10.1145/3715109), Jan 2025; arXiv:2406.00215
- **URL:** https://arxiv.org/abs/2406.00215
- **Repo:** https://github.com/jie-jw-wu/human-eval-comm — Python, HumanEval-derived benchmark + the `Okanagan` agent

**Technique.** Takes HumanEval problems and *deliberately damages the prose* along three
axes — **inconsistency, ambiguity, incompleteness** — then measures whether the model
asks a clarifying question or just barrels ahead and writes code. New metrics:
**Communication Rate** and **Good Question Rate**. Also ships `Okanagan`, an agent that
identifies ambiguous parts of code+description and asks about them.

**Numbers.** **More than 60% of Code-LLM responses still generate code rather than ask
a question** when the description has been manually damaged. That is the empirical core
of our failure mode: the model does not notice the prose is underdetermined, it commits.

**Implementable here: B (benchmark), A (the diagnosis).**

**What to implement.** A cheap ablation that makes the hypothesis falsifiable: run the
same problems with the prose *degraded* (drop a clause) and with examples present vs
absent. If examples are doing the work we think, the examples-present arm should be
insensitive to prose damage. This is the strongest single experiment in this file.

---

## 8. The Impact of Prompt Programming on Function-Level Code Generation (CodePromptEval)

- **Year:** 2024/2025
- **Venue/id:** arXiv:2412.20545 (Khojah et al., Chalmers/ICETLAB)
- **URL:** https://arxiv.org/abs/2412.20545
- **Repo:** https://github.com/icetlab/CodePromptEval — dataset of 7,072 prompts + replication package

**Technique.** Full-factorial experiment over five prompt techniques — **few-shot,
persona, chain-of-thought, function signature, list of packages** — all 32 combinations,
three models (GPT-4o, Llama3, Mistral), scored on correctness, similarity and quality.
This is the cleanest published measurement of "what does adding examples actually buy".

**Numbers.** Best combination is **few-shot + function signature at 57.5% pass@1 on
GPT-4o**, up from a 47.1% baseline — roughly **+10 percentage points**. Key negative
finding: **combining more techniques does not monotonically help**; e.g. stacking
chain-of-thought and few-shot onto the signature gained only **+0.1 pp**.

**Implementable here: A.** Gives a defensible prior for the effect size we should expect
(order of +10 pp, not +40) and a warning that piling on techniques washes the effect out.

**What to implement.** Copy the full-factorial design at small scale: {examples in
prompt: y/n} × {signature/type given: y/n}. Do *not* simultaneously add chain-of-thought,
or the paper says we will not be able to attribute the delta. Pre-register +10 pp as the
expected effect so a +2 pp result reads as a miss, not a win.

---

## 9. Does Few-Shot Learning Help LLM Performance in Code Synthesis? (CodeExemplar)

- **Year:** 2024
- **Venue/id:** arXiv:2412.02906 (Derek Xu et al., UCLA + Meta)
- **URL:** https://arxiv.org/abs/2412.02906

**Technique.** Asks the three questions we need answered in order: *do* few-shot
examples help code synthesis, *which* examples have the largest impact, and *how* to
select them. Produces two selectors — **CODEEXEMPLAR-FREE** (model-free, interpretable,
no training data) and **CODEEXEMPLAR-BASED** (model-based, stronger, needs training
data). Evaluated on HumanEval+.

**Numbers.** Both selectors significantly improve CodeLlama on HumanEval+; the widely
quoted figure from this line of work is that **relevance-based selection beats random
selection by ~5.7 pp pass@1** — i.e. *which* examples you pick is worth about half of
what picking examples at all is worth.

**Implementable here: B.** We do not choose our examples (the problem ships them), so the
selector itself is not liftable. But the *ordering* result is.

**What to implement.** If a problem ships more assertions than we want to paste, order
them by discriminative power (the nl2postcond metric) rather than by file order, and
keep the top-k. Cheap, and it is the only knob we have on example choice.

---

## 10. Test-Driven Development for Code Generation  ***(the single most on-point number in this file)***

- **Year:** 2024
- **Venue/id:** arXiv:2402.13521 (Noble Saji Mathews, Meiyappan Nagappan — Waterloo); the related ASE 2024 paper is "Test-Driven Development and LLM-based Code Generation" (IEEE/ACM ASE 2024)
- **URL:** https://arxiv.org/abs/2402.13521 · ASE version: https://www.computer.org/csdl/proceedings-article/ase/2024/124800b583/22gEBI6t8Uo

**Technique.** The direct A/B of our hypothesis. Take MBPP and HumanEval problems and
give the model **the problem statement alone** vs **the problem statement plus the
problem's own public test cases**. Models: GPT-4 and Llama 3. Then optionally add a
**remediation loop** (run the tests, feed failures back, retry).

**Numbers.**
- Adding the **public tests to the prompt**: **+12.78% on MBPP**, **+9.15% on HumanEval**.
- Adding a **remediation loop** on top: a further **+5.26% on MBPP**, **+5.49% on HumanEval**.
- Conclusion as stated: including test cases *consistently* leads to higher success.

**Implementable here: A. This is the prior for our experiment.** It is the same
manipulation (the problem's own examples pasted into the prompt), on the same kind of
benchmark, and it moved the needle roughly **+9 to +13%** — and the *repair loop was
worth about half as much again*. Note the caution: their outcome was code correctness;
ours is spec correctness, which nobody in this list has measured directly.

**What to implement.** Run exactly this two-arm design first (examples in prompt: y/n),
then add the remediation arm (feed the failing ground-truth assertion back and let the
model revise the spec). Budget for the second arm — it is the cheaper half of the win.

---

## 11. Automated Repair of Ambiguous Problem Descriptions for LLM-Based Code Generation (SpecFix)

- **Year:** 2025
- **Venue/id:** arXiv:2505.07270; IEEE (doi via IEEE Xplore 11334557). Jia, Morris, Ye, Sarro, Mechtaev — Peking University + UCL
- **URL:** https://arxiv.org/abs/2505.07270

**Technique.** Instead of asking the user, **repair the prose automatically by aligning
it to the input/output examples.** Key insight: LLMs are bad at directly clarifying
ambiguity because it needs metacognition ("how would my reading change if the text
changed"). So decompose: (1) measure the LLM's *interpretation* as the **distribution
of programs it induces**, and repair that distribution with ordinary testing +
program-repair machinery; (2) rewrite the description from the distribution change, a
step they call **contrastive specification inference**. Tool: **SpecFix**.

**Numbers.** Four models (GPT-4o, GPT-4o-mini, DeepSeek-V3, Qwen2.5-Coder-32B-Instruct)
on HumanEval+, MBPP+, LiveCodeBench, **with no human intervention**:
- Modified **43.58%** of descriptions (i.e. almost half of "clear" benchmark prose is ambiguous enough to be worth repairing).
- **+30.9% Pass@1 on the modified subset**; **+4.09% absolute across the whole benchmark**.
- Repairs **transfer across models**: prose repaired for one model lifts others by **10.48%**.

**Implementable here: A (high value).** Explicitly frames the fix as *aligning NL with
input/output examples* — our hypothesis, automated, with numbers.

**What to implement.** A pre-pass: before spec generation, have the model rewrite the
English sentence so it is consistent with the ground-truth assertions, then generate the
spec from the *repaired* sentence. The transfer result means one repaired problem set is
reusable across all our models — do the repair once, cache it, reuse across rounds.

---

## 12. Clover: Closed-Loop Verifiable Code Generation

- **Year:** 2023/2024
- **Venue/id:** arXiv:2310.17807; AI Verification (SAIV) 2024, LNCS (doi 10.1007/978-3-031-65112-0_7); Dafny Workshop @ POPL 2024. Sun, Sheng, Padon, Barrett (Stanford)
- **URL:** https://arxiv.org/abs/2310.17807 · PDF: https://theory.stanford.edu/~barrett/pubs/SSP+24.pdf
- **Repo:** https://github.com/ChuyueSun/Clover — Dafny + Python, includes the CloverBench dataset

**Technique.** A **consistency checker** over the triangle {code, docstring, formal
annotation}, using Dafny plus GPT-4. The part that matters for us: Clover explicitly
defends against **trivial/vacuous annotations**. It tests whether the annotation is
*strong enough* by trying to **reconstruct functionally equivalent code from the
annotation alone** and then checking equivalence with the original. If you can't
rebuild the program from the spec, the spec is too weak and is rejected.

**Numbers.** Up to **87% acceptance rate on correct instances** with **zero false
positives** on adversarial incorrect ones.

**Implementable here: A — this is the guard our pipeline is missing.**
`r == x + 1` would sail through any "is it provable" check; it would **not** survive a
reconstruction check, because no one regenerating from `r == x + 1` produces a
powers-of-two predicate.

**What to implement.** A reconstruct-and-compare gate: from the generated spec alone
(no prose, no examples), ask the model to regenerate a program; run **that** program
against the problem's ground-truth examples. If it fails them, the spec is of the wrong
function — reject before spending seven provers on it. This is a *test* for the exact
failure we observed, and it needs no prover.

---

## 13. Active Task Disambiguation with LLMs

- **Year:** 2025
- **Venue/id:** ICLR 2025; arXiv:2502.04485 (Kobalczyk, Astorga, Liu, van der Schaar — Cambridge/vdS lab)
- **URL:** https://arxiv.org/abs/2502.04485

**Technique.** Formalises task ambiguity and casts disambiguation as **Bayesian
Experimental Design**: choose the clarifying question that **maximises expected
information gain** over the space of viable solutions. Directly estimates information
gain rather than asking the LLM to introspect, because — same finding as SpecFix —
the metacognitive route fails.

**Numbers.** Information-gain-directed questioning beats prompting-the-model-to-ask
across their ambiguous-task suite (code generation among the domains); the qualitative
headline is that *question-space* reasoning alone is insufficient — you must reason in
*solution space*.

**Implementable here: B.** We are not interactive, so we do not ask questions. But the
mechanism converts cleanly: our "questions" are which ground-truth example to show.

**What to implement.** Rank the problem's examples by expected information gain — the
example on which a sample of candidate specs *disagrees most* — and put that one first
in the prompt. Concretely: sample k specs, evaluate each on each example, pick the
example with the highest entropy of outcomes.

---

## 14. Counterexample-Guided Inductive Synthesis (CEGIS) and distinguishing-input queries

- **Year:** 2015–2018 (framework: Solar-Lezama's sketching, 2006–08; theory: Jha & Seshia)
- **Venue/id:** "A Theory of Formal Synthesis via Inductive Learning", Acta Informatica / arXiv:1505.03953; "Counterexample Guided Inductive Synthesis Modulo Theories", CAV 2018 (doi 10.1007/978-3-319-96145-3_15)
- **URL:** https://arxiv.org/abs/1505.03953 · https://people.eecs.berkeley.edu/~sseshia/pubdir/togis17.pdf

**Technique.** The classical loop: synthesise a candidate consistent with the current
example set, verify it, and on failure extract a **counterexample** which becomes a new
example. The Jha–Seshia theory adds the oracle taxonomy we want: **membership queries**,
**witness queries**, **correctness queries**, and crucially **distinguishing-input
queries** — find an input on which two candidate programs disagree. Distinguishing
inputs "rule out incorrect programs" cheaply; the expensive correctness query is made
**only once a single candidate survives**.

**Numbers.** Theoretical (convergence and query-complexity results), not benchmark
percentages.

**Implementable here: A (the scheduling discipline), C (the theory).**

**What to implement.** Reorder the pipeline the way CEGIS does: cheap checks first,
expensive oracle last. Today we appear to hand specs straight to seven provers. Instead:
spec → check against ground-truth examples (cheap) → reconstruct-and-compare (cheap,
item 12) → **only then** the provers. And when a prover produces a counterexample, feed
it back as a *new example*, which is the CEGIS loop applied to spec repair.

---

## 15. The Daikon system for dynamic detection of likely invariants

- **Year:** 2007 (system dates to 1999)
- **Venue/id:** Science of Computer Programming 69(1–3), doi 10.1016/j.scico.2007.01.015 (Ernst, Perkins, Guo, McCamant, Pacheco, Tschantz, Xiao)
- **URL:** https://dl.acm.org/doi/abs/10.1016/j.scico.2007.01.015 · PDF: https://people.csail.mit.edu/cpacheco/publications/daikon-tool-scp2006.pdf
- **Repo:** https://github.com/codespecs/daikon — Java, **MIT licence**, still maintained

**Technique.** The canonical "specification from examples" system, and the *non-LLM*
baseline our hypothesis deserves. Instantiate a library of invariant templates with the
program's variables, run the test suite, keep every instantiated template that held in
**every** observed execution. Output is a set of likely pre/postconditions and object
invariants, derived purely from executions — no prose at all.

**Numbers.** No single accuracy figure; the operative reported behaviour is the
**dependence on suite quality**: on a binary-search program an initial test suite yielded
**62 loop-invariant candidates, most of them invalid**, purely because the suite was
incomplete. Daikon reports *likely* invariants precisely because a finite set of runs
cannot certify a universal.

**Implementable here: B.** We are not in Java, but the template-instantiation trick is
language-agnostic and tiny to reimplement for a small language.

**What to implement.** A **zero-LLM control arm**: mechanically enumerate simple
candidate relations over `(x, r)` from a template library (`r == x`, `r == x+c`,
`r < x`, `r % k == 0`, parity, boolean constants…) and keep the ones consistent with all
ground-truth examples. If the LLM-with-examples arm cannot beat a template enumerator on
these problems, the hypothesis is about the LLM, not about the examples. Also: Daikon's
62-invalid-candidates result is the honest warning that *"consistent with the examples"
is not "correct"* — expect residual wrong specs even in the treatment arm.
