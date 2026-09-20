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

**Numbers.** (Verified from the abstract.) Using OpenAI Codex, with **1 to 5 simulated
user queries**: pass@1 improvements of **22.49%–37.71% absolute on MBPP** and
**24.79%–53.98% absolute on HumanEval**. These are *absolute* percentage-point gains and
they are large because the feedback is an idealised oracle — which is exactly the regime
we are in, since our ground-truth assertions *are* an idealised oracle.

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

**Numbers.** (Verified from the abstract.) User study: **15 programmers**; participants
using the workflow were significantly more likely to *correctly evaluate* AI-generated
code and reported significantly lower task-induced cognitive load. At-scale arm:
**4 state-of-the-art LLMs, 2 Python datasets**, with an idealised proxy for user
feedback — **average absolute improvement of 45.97% in pass@1 within 5 user
interactions**, plus the unit tests come out as a by-product.

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
- **URL:** https://arxiv.org/abs/2505.07270 · v2: https://arxiv.org/html/2505.07270v2
- **Repo:** https://github.com/msv-lab/SpecFix — **Python**, official ASE 2025 artifact.
  Does ambiguity detection by **clustering LLM-generated candidate programs by behaviour
  on differential tests**, then requirement refinement, then evaluation via pass@k,
  majority voting and behavioural metrics. **This is the single best repo to lift from.**

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

---

## 16. Rethinking the Role of Demonstrations: What Makes In-Context Learning Work?  ***(the strongest evidence AGAINST our hypothesis)***

- **Year:** 2022
- **Venue/id:** EMNLP 2022 (ACL Anthology 2022.emnlp-main.759); arXiv:2202.12837. Min, Lyu, Holtzman, Artetxe, Lewis, Hajishirzi, Zettlemoyer
- **URL:** https://aclanthology.org/2022.emnlp-main.759/ · https://arxiv.org/abs/2202.12837

**Technique.** Ablates what in-context demonstrations actually contribute by **replacing
the labels in the demonstrations with random ones** and re-measuring.

**Numbers.** **Randomly replacing the labels barely hurts performance**, consistently
across **12 models including GPT-3**, on a range of classification and multi-choice
tasks. What the demonstrations actually supply is (1) the **label space**, (2) the
**input distribution**, (3) the **format** of the sequence — not the input→output
mapping.

**Implementable here: A — as the control that could kill the hypothesis.** If examples
help us only by conveying *format* and *the shape of the output*, then a fake example
with a wrong output would help just as much as the real one, and "examples pin down
intent" is the wrong explanation for any gain we see.

**What to implement.** **A corrupted-example arm.** Three arms: no examples / real
examples / examples with *scrambled outputs*. If the scrambled arm matches the real
arm, the effect is formatting, not intent, and we must report that. Caveat in our
favour: Min et al. studied classification and multi-choice, where the label space is
tiny; on open-ended function specification the mapping carries much more information,
which is why item 10 still found +9–13%. Say so explicitly rather than ignoring the
paper.

---

## 17. Assessing the Impact of Requirement Ambiguity on LLM-based Function-Level Code Generation (Orchid)

- **Year:** 2026
- **Venue/id:** arXiv:2604.21505 (also circulated as "Clarity Is Not Assumed: Understanding LLM-Based Code Generation under Ambiguous Requirements")
- **URL:** https://arxiv.org/abs/2604.21505

**Technique.** Introduces **Orchid**: **1,304 function-level tasks** with **5,216
ambiguous requirement variants** across four linguistic ambiguity types — **lexical,
syntactic, semantic, vagueness**. Measures both correctness and **functional consistency
across repeated generations** under ambiguity, and separately tests whether models can
*detect* and *localise* the ambiguity.

**Numbers.** Ambiguity consistently degrades performance; **even GPT-4 drops >30%** under
ambiguous specifications. Models identify ambiguity with **relatively high recall but
low precision**, and struggle to *localise* and *resolve* the source.

**Implementable here: B (benchmark), A (the measurement idea).**

**What to implement.** **Functional consistency as a cheap ambiguity detector, requiring
no ground truth**: sample the spec k times at temperature; if the k specs are not
semantically equivalent, the prose is ambiguous for this model and this problem is a
prime candidate for the examples treatment. Use it to *stratify* our results — the
hypothesis should show its biggest effect on the high-variance problems.

---

## 18. Do LLMs generate test oracles that capture the actual or the expected program behaviour?

- **Year:** 2024
- **Venue/id:** arXiv:2410.21136 (Konstantinou, Degiovanni, Papadakis — Univ. of Luxembourg)
- **URL:** https://arxiv.org/abs/2410.21136

**Technique.** Controlled experiment on **24 open-source Java repositories**, over both
oracle *classification* and oracle *generation*, with developer-written and
automatically generated tests, across several carefully tested prompts. The question is
whether the oracle encodes what the code **does** or what it **should do**.

**Numbers.** LLMs are **more likely to generate oracles capturing the actual (implemented)
behaviour than the expected (intended) behaviour**. They are better at *generating*
oracles than at *classifying* correct ones. Oracle quality improves markedly when the
code carries **meaningful variable and test names**. LLM oracles have higher fault-
detection potential than EvoSuite's.

**Implementable here: A (as a threat to validity).** This is the *mechanism* of our
failure, named: the model describes whatever artefact is nearest to hand rather than the
intent. If our prompt shows the model a draft program, the spec will describe that
program, not the problem.

**What to implement.** Generate the specification **before and independently of** any
candidate program, from prose + examples only. If the pipeline currently shows the model
its own code while asking for a spec, that ordering is itself a cause of `r == x + 1`.
Also: keep meaningful names in the problem statement — the paper says naming measurably
moves oracle quality.

---

## 19. SpecGen: Automated Generation of Formal Program Specifications via Large Language Models

- **Year:** 2024/2025
- **Venue/id:** arXiv:2401.08807 (Nanjing University, NTU, SMU)
- **URL:** https://arxiv.org/abs/2401.08807

**Technique.** Two phases. (1) **Conversational**: few-shot examples plus **iterative
feedback from the verifier itself** (OpenJML) steering the LLM towards a JML spec that
verifies. (2) **Mutation-based**: when the LLM output will not verify, apply four
mutation operator families — **predicative, logical, comparative, arithmetic** — with a
heuristic selection strategy, and search the neighbourhood of the failed spec.

**Numbers.** On a benchmark of **385 Java programs, SpecGen verifies 72.5%**,
outperforming both LLM and non-LLM baselines.

**Implementable here: A (mutation repair), B (the JML specifics).**

**What to implement.** When a generated spec disagrees with the ground-truth examples,
do not resample from scratch — **mutate** it. The four operator families are directly
applicable to a small spec language, and arithmetic/comparative mutation is exactly the
neighbourhood that contains the fix for an `r == x + 1`-shaped error. Cheap, and it
reuses whatever the model got right.

---

## 20. AutoSpec: automated specification synthesis with an iterative verifier loop

- **Year:** 2023/2024
- **Venue/id:** ASE 2023 — "Towards Automated Verification of LLM-Synthesized C Programs" / AutoSpec line of work
- **URL:** (discussed in the survey at https://arxiv.org/abs/2601.12845)

**Technique.** Decompose the program, synthesise candidate loop invariants and
pre/postconditions per fragment, and run an **iterative feedback loop against the
verifier**, keeping only annotations the verifier accepts and retrying the rest.

**Numbers.** **Verifies 79% of 251 C programs within five attempts.** The reported
weakness is the one that matters to us: it **depends on users providing correct and
complete properties and is vulnerable to under-specification** — i.e. it will cheerfully
verify a weak spec.

**Implementable here: B.**

**What to implement.** Bound the retry loop at **five attempts** (their empirical knee)
rather than an open-ended loop, and — because of the stated under-specification
weakness — pair every accepted spec with the strength check from item 12. "It verified"
must never be the acceptance criterion on its own.

---

## 21. VERINA: Benchmarking Verifiable Code Generation

- **Year:** 2025
- **Venue/id:** arXiv:2505.23135; OpenReview 0A4Uf88pog (Sunblaze lab, UC Berkeley)
- **URL:** https://arxiv.org/abs/2505.23135
- **Repo:** https://github.com/sunblaze-ucb/verina — Lean 4 + Python, dataset also on HuggingFace

**Technique.** **189 manually curated Lean tasks**, each with problem description,
reference implementation, formal specification **and an extensive test suite** — so code,
spec and proof can be scored *separately and modularly*. The spec-scoring pipeline is the
part to steal: it combines **theorem proving with comprehensive testing** to score a
generated specification on **soundness** (does it accept the reference implementation)
and **completeness** (does it reject wrong implementations).

**Numbers.** Best model **OpenAI o3**: **72.6% code correctness**, **52.3% specification
soundness+completeness**, and **4.9% proof success** (one trial/task). The gap between
72.6% code and 52.3% spec is the quantified version of our problem: *models write the
program better than they write the spec of the program.*

**Implementable here: A.** Closest published architecture to ours (code + spec + proof,
tests on the side), and it supplies the exact scoring rubric we need.

**What to implement.** Adopt soundness/completeness as our spec metric and report it
alongside conversion. Soundness = spec accepts the ground-truth behaviour on all
examples. Completeness = spec rejects mutants. Under this rubric `r == x + 1` scores
**unsound**, and that is a number we can move.

---

## 22. Verus-SpecGym / Verus-SpecBench: An Agentic Environment for Evaluating Specification Autoformalization  ***(our failure mode, named and measured)***

- **Year:** 2026
- **Venue/id:** arXiv:2605.26457
- **URL:** https://arxiv.org/abs/2605.26457 · https://arxiv.org/html/2605.26457v1

**Technique.** An agentic loop where the model develops a **specification** (not code)
for an informal problem by interacting with **Verus** (the Rust verifier), bash and the
filesystem, refining against verifier errors. Benchmark: **Verus-SpecBench, 581
spec-writing tasks derived from Codeforces problems**.

**Numbers.**
- gemini-3.1pro **77.8%**; other frontier models **51.1–57.8%**; open-source **21.5–25.5%**.
- Failure taxonomy, verbatim relevant: model-generated specs **omit important input
  assumptions**, **accept incorrect outputs**, and **reject valid ones**.
- **LLM-as-a-judge misses 26% of the failures** their executable evaluator catches.
- Conclusion: spec autoformalization is **brittle even on problems where the same models
  already generate correct code**.

**Implementable here: A.** The closest thing in the literature to a direct measurement of
the thing we are failing at, on a comparable problem source (competitive-programming
prose + examples).

**What to implement.** Two things. (1) **Do not use an LLM judge to decide whether a spec
is right** — it misses a quarter of the failures; execute the spec against the examples
instead. (2) Adopt their three-way failure taxonomy as our error labels (missing
precondition / accepts wrong output / rejects right output) so round-over-round we can
say *which* failure the examples fixed, not just that the count moved.

---

## 23. Testing LLMs on Code Generation with Varying Levels of Prompt Specificity

- **Year:** 2023
- **Venue/id:** arXiv:2311.07599 (Murr, Grainger, Gao)
- **URL:** https://arxiv.org/abs/2311.07599

**Technique.** **104 coding problems × four prompt types** varying degrees of *tests* and
*specificity*, across Bard, ChatGPT-3.5, ChatGPT-4 and Claude-2, scored on accuracy plus
time and space efficiency. The framing sentence is the one to quote: when tests are in
the prompt they act as **"a definitive specification of what the code should accomplish"**.

**Numbers.** Reports per-model accuracy across the four specificity levels; the
consistent direction is that adding tests to the prompt raises accuracy, with the effect
largest for the weaker models.

**Implementable here: B.** Older models, but the four-level design is a good template:
prose only / prose+signature / prose+tests / prose+tests+detail.

**What to implement.** Use their four-level ladder rather than a binary on/off, so we can
see whether the examples are substituting for prose detail or adding to it. Also predict
in advance that the effect will be **largest on our weakest model** — a cheap,
pre-registered directional check.

---

## 24. Hypothesis Search: Inductive Reasoning with Language Models

- **Year:** 2023/2024
- **Venue/id:** ICLR 2024; arXiv:2309.05660; OpenReview G7UtIGQmjm (Wang, Zelikman, Poesia, Pu, Haber, Goodman — Stanford)
- **URL:** https://arxiv.org/abs/2309.05660 · https://openreview.net/forum?id=G7UtIGQmjm

**Technique.** Pure example-driven intent inference. Given only input/output pairs:
(1) prompt the LLM for **multiple abstract hypotheses in natural language** about the
rule; (2) **implement each hypothesis as a Python program**; (3) **filter by executing
against the observed examples**. The NL hypothesis is the intermediate representation —
a spec — and the program is its realisation, which is our pipeline shape exactly.

**Numbers.** On a 40-problem ARC subset: **12.5% direct prompting → 27.5%** with the
automated hypothesis-search pipeline (**>2x**), and **37.5%** when a human picks among
LLM-generated hypotheses.

**Implementable here: A.** The single most transferable *procedure* in this file for a
spec-generation pipeline.

**What to implement.** Replace one-shot spec generation with **generate-k-then-filter**:
sample k candidate specs, discard every one that contradicts a ground-truth example, and
only then send survivors to the provers. Note the human-in-the-loop delta (27.5→37.5):
if we ever want an operator-assisted arm, choosing among candidate specs is where the
leverage is — not writing them.

---

## 25. When Prompt Under-Specification *Improves* Code Correctness  ***(second counter-evidence paper)***

- **Year:** 2026
- **Venue/id:** arXiv:2604.24712
- **URL:** https://arxiv.org/abs/2604.24712 · https://arxiv.org/html/2604.24712v1

**Technique.** Mutates prompts to *remove* specification detail and measures robustness
across **10 models** on **HumanEval** and the structurally richer **LiveCodeBench**.

**Numbers.** Robustness depends on prompt structure: the same under-specification
mutations that **degrade HumanEval have near-zero net effect on LiveCodeBench** because
of redundancy in the richer descriptions. More pointed: under-specification sometimes
**improves** correctness, by breaking misleading lexical/structural cues that trigger
**retrieval-based** (memorised-lookalike) solution strategies. Named mechanisms:
disruption of over-fitted terminology, removal of misleading constraints, elimination of
spurious identifier triggers.

**Implementable here: A (as a threat), C (the finding).**

**What to implement.** The uncomfortable reading for us: our `r == x + 1` may be a
*retrieval* failure — "sum of non-zero powers of two" pattern-matched onto a memorised
neighbour. If so, adding examples helps only if they *override retrieval*, and adding
more prose may make it worse. Test it: record whether the wrong specs cluster on
problems whose phrasing resembles a well-known different problem. Also note the
redundancy finding — richer descriptions absorb damage, which argues for
prose **plus** examples rather than examples replacing prose.

---

## 26. ClarifyCodeBench: Evaluating LLMs on Clarifying Ambiguous Requirements for Code Generation

- **Year:** 2026
- **Venue/id:** arXiv:2607.00711
- **URL:** https://arxiv.org/abs/2607.00711

**Technique.** An **interactive** benchmark from real-world programming tasks with manual
annotations of ambiguity types, the clarification questions that resolve them, and
ground-truth answers. Two novel metrics: **Turn-discounted Key Question Rate (TKQR)** —
rewards asking the key question *early*, penalises delay and redundancy — and **Optimal
Round Adherence (ORA)** — penalises both premature code generation *and* unnecessary
questioning.

**Numbers.** Across six SOTA LLMs: **strong code-generation performance does not translate
into effective requirement clarification**, and **more inference-time thinking improves
code correctness but yields only marginal gains in identifying ambiguity**.

**Implementable here: B (benchmark), A (the reasoning-budget finding).**

**What to implement.** Do **not** try to fix this with more reasoning tokens — the paper
says that buys code correctness, not ambiguity detection. Spend the budget on the
examples-in-prompt and the check-against-examples gate instead. That is a direct
experiment-design decision and it saves money.

---

## 27. Can Large Language Models Write Good Property-Based Tests?

- **Year:** 2023
- **Venue/id:** arXiv:2307.04346
- **URL:** https://arxiv.org/abs/2307.04346

**Technique.** Evaluates LLMs at writing **property-based tests** (PBT) from API
documentation — i.e. producing a *universally quantified* property rather than a finite
set of examples. Related systems in this line: **PBT-GPT** (properties + random inputs
from API docs), **ChekProp** (arXiv:2505.23549, CPS guardrails, iteratively repairs its
own PBTs), and **Property-Generated Solver (PGS)** — a Generator/Tester agent pair where
the Tester defines properties, generates inputs and feeds property-violation feedback
back to the Generator.

**Numbers.** Per-library pass rates vary widely; the durable finding is that models write
*syntactically valid* properties far more often than *semantically meaningful* ones —
the same correct-but-vacuous hazard as item 5.

**Implementable here: B.**

**What to implement.** A property is what our specification *is*. The PGS loop is the
liftable bit: a Tester role that takes the generated spec, **generates fresh inputs
beyond the given examples**, and reports violations to the spec-writer. That extends the
finite example set into something closer to a real oracle — which is the only way to
catch a spec that happens to agree with all four shipped examples by accident.

---

## 28. Selecting Representative Examples for Program Synthesis

- **Year:** 2018
- **Venue/id:** ICML 2018, PMLR v80 (Pu, Miranda, Solar-Lezama, Kaelbling — MIT)
- **URL:** https://proceedings.mlr.press/v80/pu18b/pu18b.pdf

**Technique.** Directly answers the "*how many* examples" angle. Given a large example
set, pick a **small representative subset** that determines the same program, framed as a
set-cover / maximum-coverage problem over the hypothesis space and solved with a learned
selector. The point is that most examples are redundant and a **handful of
well-chosen ones is equivalent to the whole set**.

**Numbers.** Reports large reductions in the number of examples needed for synthesis to
converge to the right program versus random subsets, at equal or better accuracy.

**Implementable here: B.**

**What to implement.** Formalises the intuition behind item 13 with a cheaper algorithm:
greedy max-coverage over candidate specs. Sample k specs; greedily pick the example that
eliminates the most surviving specs; repeat until one survives or examples run out. The
number of examples that greedy needs **is** our empirical answer to "how many examples
pin this problem down" — log it per problem; it is a publishable number in its own right
and costs nothing extra to collect.

---

## 29. ClarifyGPT: Enhancing LLM-Based Code Generation via Requirements Clarification

- **Year:** 2023/2024
- **Venue/id:** PACMSE / **FSE 2024** (doi 10.1145/3660810); arXiv:2310.10996 (Mu, Shi et al.)
- **URL:** https://arxiv.org/abs/2310.10996 · https://dl.acm.org/doi/10.1145/3660810

**Technique.** Detects ambiguity **without any ground truth** via a **code consistency
check**: generate several candidate programs from the same requirement, run them on
generated test **inputs**, and compare *outputs*. Identical outputs ⇒ the model
interprets the requirement one way ⇒ unambiguous. Divergent outputs ⇒ ambiguous. Then
**cluster the solutions by their test outputs**, pick one representative per cluster, and
synthesise a targeted clarifying question from the contrast between clusters.

**Numbers.**
- GPT-4 on MBPP-sanitized: **70.96% → 80.80% pass@1** (+9.84 pp).
- Averaged over **five benchmarks**: GPT-4 **62.43% → 69.60%**; ChatGPT **54.32% → 62.37%**.

**Implementable here: A (highest ratio of value to effort in this file).**

**What to implement.** The output-divergence detector, applied to *specs* instead of
programs: sample k specs, evaluate each on the problem's example inputs, and cluster by
the resulting truth-vector. A problem where all k specs agree and all agree with the
ground truth needs no intervention; a problem where they split is where the examples
treatment should be spent. This gives us a **per-problem ambiguity score for free**, with
which to stratify the round-7 results instead of reporting one aggregate count.

---

## 30. On the risk of coding before testing: error propagation in LLM test-generation workflows

- **Year:** 2026
- **Venue/id:** arXiv:2607.05139 (Konstantinou, Tambon, Papadakis — Univ. of Luxembourg)
- **URL:** https://arxiv.org/abs/2607.05139
- **Artifact:** https://zenodo.org/records/21089934 — benchmarks, prompts, faulty implementations, generated test suites

**Technique.** Isolates **error propagation**: when an LLM generates code first and then
tests, do faults in the code get replicated in the tests? Tested across prompting
strategies including chain-of-thought and across multi-step workflows where intermediate
outputs become context.

**Numbers.** **Generating tests after faulty code cuts fault-detection effectiveness to
14%, versus 25% when tests are generated independently** — roughly **half**. Chain-of-
thought does not rescue it.

**Implementable here: A (pipeline ordering).** Companion to item 18 and the same group.

**What to implement.** Hard rule for the pipeline: **the specification must never see a
candidate program.** If any stage currently generates code first and then asks for a spec
"for this code", that ordering alone can account for a large share of wrong specs, and it
is free to fix. Independent generation, then cross-check.

---

## 31. Choose, Don't Label: Multiple-Choice Query Synthesis for Program Disambiguation

- **Year:** 2026
- **Venue/id:** **OOPSLA/PACMPL** (doi 10.1145/3808279); arXiv:2604.08792. Barnaby, Ding, Bastani, Dillig (UT Austin / Penn)
- **URL:** https://arxiv.org/abs/2604.08792 · https://doi.org/10.1145/3808279

**Technique.** Argues that eliciting supervision as **labelled examples is error-prone and
often fails to capture intent**, and replaces it with **multiple-choice queries**: the
system synthesises a small set of **high-level behaviour descriptions** covering the
candidate programs, and the user just picks the intended one. Active learning over the
hypothesis space, but with the query in the *behaviour* space rather than the
input/output space.

**Numbers.** Reports fewer queries to convergence and higher user accuracy than
example-labelling baselines (PL venue; the comparison is queries-to-disambiguate).

**Implementable here: B.**

**What to implement.** The prompt reformulation is free and worth an arm: instead of
"here are the examples, write a spec", give the model **k candidate behaviour
descriptions** (generated from k sampled specs) and ask it to *choose* which matches the
prose+examples. Discrimination is an easier task than generation — that is the paper's
whole thesis, and it matches the Hypothesis-Search human-selection delta in item 24.

---

## 32. Towards Automated Verification of LLM-Synthesized C Programs / survey of spec-generation with test oracles

- **Year:** 2026
- **Venue/id:** arXiv:2601.12845 — "Automatic Generation of Formal Specification and Verification Annotations Using LLMs and Test Oracles" (preprint, intended for Science of Computer Programming)
- **URL:** https://arxiv.org/abs/2601.12845 · https://arxiv.org/html/2601.12845

**Technique.** Survey-plus-method over the whole area we are in: LLM generation of formal
specs and verification annotations across **Verus, Dafny, Alloy, Lean, JML**, with the
central recommendation that **combining LLMs with verifiable test oracles is both more
effective and closer to normal developer workflow** than either alone. Carries the
comparative numbers for SpecGen (72.5% of 385 Java programs) and AutoSpec (79% of 251 C
programs in ≤5 attempts).

**Numbers.** Aggregates the above; useful mainly as the citation map for related work.

**Implementable here: C (orientation), A (the thesis).**

**What to implement.** Nothing new — but it is the sentence to put at the top of the
round-7 write-up: *the field's current best answer to "how do you know the spec is right"
is "check it against executable oracles", not "check it against a prover".* We have seven
provers and were missing the oracles. That is the hypothesis, stated as the literature
states it.

---

## 33. TOGA: A Neural Method for Test Oracle Generation — and TOGLL, its LLM successor

- **Year:** TOGA 2022; TOGLL 2024
- **Venue/id:** TOGA — **ICSE 2022** (doi 10.1145/3510003.3510141), arXiv:2109.09262 (Dinella, Ryan, Mytkowicz, Lahiri). TOGLL — arXiv:2405.03786 (Soneya Binta Hossain, Matthew Dwyer)
- **URL:** https://arxiv.org/abs/2109.09262 · https://arxiv.org/abs/2405.03786
- **Related:** "Neural-Based Test Oracle Generation: A Large-scale Evaluation and Lessons Learned", arXiv:2307.16023 — the independent re-evaluation that found TOGA's reported numbers did not hold up

**Technique.** TOGA reframes oracle generation as **ranking over a small set of likely
oracles** rather than free generation, on the empirical observation that developer-written
assertions follow **a small number of common patterns** expressible as a compact grammar;
CodeBERT is fine-tuned to rank candidates and to classify whether a prefix throws.
TOGLL replaces the ranker with fine-tuned LLMs (7 models, 6 prompt variants).

**Numbers.** TOGLL generates about **3.8x more correct assertion oracles** and **4.9x more
exception oracles** than TOGA. The cautionary half: independent evaluation found TOGA
produced **a high rate of false positives**, and that for many prefixes it emitted no
assertion at all — its headline numbers did not survive re-evaluation.

**Implementable here: B (the grammar), A (the cautionary tale).**

**What to implement.** The **constrained-grammar** idea is the cheapest structural defence
available to us: if candidate specifications must be drawn from a small grammar of
plausible predicate shapes rather than generated free-form, `r == x + 1` can still be
*expressed* — but generate-and-rank over the grammar (rather than one confident free-form
emission) surfaces the alternatives and lets the examples choose between them. Also, the
re-evaluation story is the reason to score round 7 with an executable check rather than a
reported metric: this subfield has already been burned once by numbers that did not
replicate.

---

# Synthesis: what the literature says about our bet

**The bet is well supported, and the expected size splits into two regimes.**

*One-shot (examples pasted into the prompt, no loop):* the direct A/B of "problem's own
tests in the prompt" (item 10) gave **+9.15% HumanEval / +12.78% MBPP**. Prompt-technique
factorial work (item 8) puts **few-shot + signature at +10.4 pp pass@1**. Ambiguity
detection by output-divergence (item 29, ClarifyGPT) gave **+9.84 pp** on GPT-4/MBPP.
Aligning prose to examples automatically (item 11, SpecFix) gave **+30.9% on the subset
it touched** but **+4.09% overall**, with **43.58% of benchmark descriptions ambiguous
enough to be worth repairing**. **One-shot, pre-register roughly +10 pp.**

*Looped against an oracle (examples used to reject and retry):* much larger.
TiCoder with an idealised feedback proxy (items 1–2) got **22.49–37.71 pp absolute on
MBPP**, **24.79–53.98 pp on HumanEval**, **45.97 pp average** across four LLMs — within
**five** interactions. Item 10's remediation loop added another **~+5%** on top of its
one-shot gain.

**This distinction is the most actionable thing in the file.** TiCoder's huge numbers
come from having a trusted oracle in the loop, and **we already have one** — the
problem's own assertions, free, perfect, and needing no user. Pasting the examples into
the prompt buys the ~10 pp; *rejecting and regenerating specs that contradict the
examples* is what buys the 20–45 pp. Round 6's conversion move of 27%→33% sits inside the
one-shot band, which suggests the proof-gate data bought roughly what a one-shot prompt
intervention buys — and that the loop, not more prompt content, is the unexploited half.

**Three papers say be careful.**
1. **Item 16 (Min et al.)** — randomising demonstration labels barely hurt across 12
   models. Run the **scrambled-output arm** or the result is not interpretable.
2. **Item 4 (many-shot)** — pass@1 *declines* past ~25 examples. Do not auto-inflate.
3. **Item 25** — under-specification sometimes *improves* correctness by breaking
   retrieval of a memorised lookalike. `r == x + 1` smells like exactly that failure.

**The cheapest wins, in order (all rated A, none needs a prover):**
1. **Gate on the examples before the provers** (items 5, 21). Never prove a spec that
   already disagrees with the problem's own assertions. This kills the observed failure
   class outright and *saves* prover time.
2. **Reconstruct-and-compare** (item 12, Clover): regenerate a program from the spec
   alone, run it on the examples. Catches strong-looking, wrong-function specs.
3. **Generate-k-and-filter** (items 24, 29): sample k specs, drop those contradicting an
   example, cluster the rest by truth-vector — a free per-problem ambiguity score.
4. **Never show the spec-writer a candidate program** (items 18, 30): tests written after
   faulty code detect 14% of faults versus 25% written independently.
5. **Emit a precondition too** (item 6): postcondition-only specs make verifiers raise
   false alarms; with seven provers we are paying that tax.

**Measure the spec, not just the conversion count.** Every serious paper here scores
specs on **two axes** — soundness (accepts the intended behaviour) and
completeness/discriminative power (rejects the wrong behaviour). Our observed failure is
a *soundness* failure that the provers cannot see. Report soundness and completeness per
round (items 5, 21, 22) and the number will say *which* thing improved.

**Do not buy more reasoning tokens for this.** Item 26: more thinking improves code
correctness but gives only marginal gains in identifying ambiguity.

---

## Repository shortlist

| Repo | Language / licence | What to lift |
|---|---|---|
| https://github.com/msv-lab/SpecFix | Python, ASE 2025 artifact | Behavioural clustering of candidate programs for ambiguity detection; requirement-repair prompt sequence; pass@k + majority-vote eval harness |
| https://github.com/ChuyueSun/Clover | Dafny + Python | The anti-vacuity **reconstruction** check; CloverBench |
| https://github.com/sunblaze-ucb/verina | Lean 4 + Python | Spec **soundness/completeness** scoring pipeline (proving + testing combined); 189 curated tasks |
| https://github.com/codespecs/daikon | Java, **MIT** | Invariant template library — the non-LLM control arm |
| https://github.com/icetlab/CodePromptEval | Python, 7,072 prompts | Full-factorial prompt-technique experiment design + scripts |
| https://github.com/jie-jw-wu/human-eval-comm | Python | Damaged-prose HumanEval variants; Communication Rate / Good Question Rate metrics |
| https://zenodo.org/records/21089934 | data artifact | Faulty implementations + generated suites for the error-propagation study |

