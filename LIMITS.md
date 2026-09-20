# Limits, stated plainly

Every caveat this project knows about, in one place, so none of them depends on
a reader reaching a particular paragraph. The headline is in
[`README.md`](README.md); this is what it does not claim.

## On the headline claim

- No model trained here has beaten Phi-4-mini. Three rounds have tied it at 3
  of 232, on a baseline regraded the same day by the same evaluator. Three
  answers is a thin result.
- Phi's 3 of 232 is a low bar and it is low for a reason: Phi has never seen t,
  so most of its answers do not parse. Beating it at writing t is a weaker
  claim than beating it at Python.
- Three models *run through* this pipeline beat Phi, and none was built here,
  so none is a result of this project's method: Qwen3.8-27B at 12 clean,
  Qwen3-235B-A22B at 11, DeepSeek-Prover-V2-7B at 6, against our best of 3.
  A larger model is simply better at this, and saying otherwise would be false.
- **Scale stops paying somewhere below 235B.** The 27B scores 12 and the 235B,
  about nine times its size, scores 11. Between them the clean count did not
  move. What did move is the opposite of a flattering number for us: the 235B
  gets 53 of 232 answers to compute the right values where locallm gets 3. It
  is far better at solving the problems and no better at proving them, and that
  gap, not the headline, is what this project is actually about.
- The 232 held-out problems are MBPP, which every base model here was almost
  certainly pretrained on. The split protects against *this project's* training
  leaking into its own evaluation; it cannot protect against a base model
  having seen MBPP before we met it. That applies to every row equally, ours
  and Phi's, so the comparison stands while the absolute numbers are softer
  than they look.
- The models are not the same size. DeepSeek-Prover-V2-7B is 7B against
  Phi-4-mini's 3.8B, so its 6 against 3 is not a per-parameter claim; what
  makes it interesting is the conversion rate, which is a property of what the
  model was trained on rather than how big it is.

## On what a proof here is worth

- Nothing here is hallucination-free or 100 percent correct. A proof shows a
  program meets its specification, not that the specification says what the
  problem asked. That is why every table carries a **proven but wrong** column,
  why the tests are a separate gate, and why an accepted answer's specification
  is checked against the problem's own solution
  ([`t/spec_check.py`](t/spec_check.py)).
- **"Clean" means the tests pass and seven proof systems verified it with the
  twin refuted. It has never meant the specification is strong, and now that
  gap is measured.** Enumerating ten trivial programs against each accepted
  specification (AlphaVerus's exploit model,
  [arXiv:2412.06176](https://arxiv.org/abs/2412.06176)) finds **1 of 11 clean
  answers exploitable**: asked to remove all whitespace from a string, one
  specification said only that every output character is alphanumeric and the
  output is no longer than the input, which returning nothing satisfies. Its
  program is correct; its proof establishes almost nothing. 7-29% of the
  proven-but-wrong population is exploitable the same way
  ([`locallm/FINDINGS-exploit-2026-09-20.md`](locallm/FINDINGS-exploit-2026-09-20.md)).
- **The specifications are usually wrong rather than weak**, and that took a
  correction to establish. Across 1,295 wrong answers tested against 14 scored
  specifications, 1 was weak. The first version of that measurement reported
  "not one weak specification"; widening the search found one, a
  maximum-of-three problem missing `r >= c` that still rejected 345 of 350
  wrong answers. A zero found by a search is a property of the search
  ([`locallm/FINDINGS-completeness-2026-09-20.md`](locallm/FINDINGS-completeness-2026-09-20.md)).
- **The seven checkers do less of the work than the name suggests.** A
  preregistered ablation
  ([`t/ABLATION-2026-09-17.md`](t/ABLATION-2026-09-17.md)) measured one prover
  admitting wrong answers 17.4 percent of the time against 12.9 percent for all
  seven with the twin refuted, at half the problem coverage. On held-out
  answers, where the model writes its own specification, every proof gate
  admits about 97 percent wrong and the tests catch what the proofs cannot. The
  honest claim is tests **and** proofs together, not seven provers rather than
  one.
- A proof covers the specification, not the intent. Hence the tests, the
  proven-but-wrong column and the specification check.
- t covers integers, booleans, sequences, pairs, strings as character
  sequences, loops with invariants and recursive specification functions. No
  heap, no floats, no concurrency.

## On the training side

- Pretraining the core did not help this pipeline. A 92M core pretrained on 46M
  tokens of real source and specialized on the filtered t data scored 1 clean
  of 232, wrote fewer well-formed answers than the 3.2M models, and produced 91
  proven-but-wrong answers out of 136 well formed. The comparison moves size,
  tokenizer, corpus and recipe together, so it says the number did not improve
  and not which change is responsible.
- The owned core's architecture choice is not settled in its favour: at 4000
  updates the older GPT core beats the modern one at every seed, on loss, time
  and memory.
- No auxiliary training objective tried here has improved program synthesis.
  Execution-state supervision improves execution-state prediction and does not
  transfer; latent prediction does neither at three seeds.
- Token loss on a validation window predicts nothing about behaviour at this
  scale. The 45% loss cut that bought no usable completion is the second time
  in two days that a loss result and a behaviour result disagreed here.
- The clean pool is small (87 examples). The corpus that feeds it was called
  exhausted here until 2026-09-20, when 1,032 stdin-shaped problems that
  `t/nl_stdin.py` had already measured and nothing had ever imported were wired
  in as pool v6 (4,035 problems, +34.4%). That is more problems, not more clean
  examples: none of them has been answered by any model yet, so the 87 stands
  until they are.
