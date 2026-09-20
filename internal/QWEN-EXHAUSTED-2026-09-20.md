# What a large model can still do for this roadmap: the complete list

Written 2026-09-20 while Qwen3-235B-A22B was on loan across the lab's four cards,
to answer one question exactly: **when can the model be given back without leaving
roadmap work that only it could have done?**

The rule used below: an item is *model-shaped* only if a large language model does
something no amount of CPU, code or measurement here can. Writing a lowering,
fixing a lifter rule, running seven provers, grading a table and filtering a
candidate bank are all CPU. Generating an answer, a specification, an invariant, a
proof hint or a repair is the model.

## Model-shaped, and launched 2026-09-20

| item | what the model does | instrument |
|---|---|---|
| **WS-16.2** | a proof hint per row for the 30 rows six kernels verify and one does not | `t/hint_candidates.py` |
| **WS-18 / WS-22.2** | the sampler: answers over the 2,771 train ids at prompt v4, then three temperature draws | `~/qwen_locallm.sh` |
| **WS-19 move 2** | reads a verifier's verdicts and a concrete witness and rewrites the answer, over the 101 answers one kernel short of clean | `t/repair.py` |
| **WS-19 move 3** | the data multiplier: specification from body, body from specification, invariants from a stripped task, over the 221-task verified corpus | `t/multiplier.py` |
| **WS-21 move 1 / WS-22.4** | decodes against `t/t.gbnf` on the llguidance backend | `spec_experiment.py generate --grammar` |
| **WS-21 move 2** | the same 232 problems under prompt v5's grammar-guidance block | `--prompt v5` |

Every one banks to disk. None of them accepts anything: the verdict is the seven
provers' and that is CPU, deliberately, so the expensive resource drains first.

## Not model-shaped, and the reason

- **WS-7, WS-8, WS-9, WS-10, WS-14 (all five), 13.2, 13.3, 16.1, WS-19 moves 4 and
  6, WS-20 (all four moves), WS-22.1** are done.
- **13.1 constructs, 16.2's lifter half, 12.7's line** are lowering and lifter code.
  A model can draft a patch; it cannot measure whether seven provers still agree,
  and that measurement is the work.
- **13.4's eight remaining conformance cells** are the closest call and the answer
  is still no. Six of the eight are named designs, not gaps a hint fills: a second
  capacity dimension for nested returns, an executable `lower` with a length bound,
  a pair with a seq component through the buffer encoding. The other two, `biglen`
  and `seqlen`, are open by design until a symbolic witness exists.
- **WS-19 move 7**, the reward ablation, shares one set of generated answers between
  its two arms. The hurdle its own entry names is the one-kernel reward path, which
  is code.
- **WS-15 (15.3, 15.4, 15.5), 17.1, 17.2** need a second person, a Windows machine
  with Visual Studio, or both. No model substitutes for a witness.
- **WS-11** needs an arm64 or x86_64 build host.

## The one thing a card is still needed for, and it is not this model

**WS-22.3 and WS-22.5 train locallm.** 22.5 is the project's stated target, at least
4 clean of 232, and it is reached by training a small model on the data the jobs
above are generating. locallm is 875M at its measured ceiling and fits one card for
minutes (`locallm/measure_capacity.py`). So giving back the 235B costs nothing
there; giving back **every** card makes the target unreachable, and that is a
different decision from this one.

## What is left after the six jobs drain

CPU, and all of it outlives the loan:

1. Grade about 5,300 raw answers through the seven provers. This is the bottleneck
   on everything, `qwen235-train`, `qwen235-v6new` and `-p4` included.
2. Filter the hint bank. A candidate counts only when the real VERIFIES and the twin
   is STILL REFUTED, which is DAISY's 25-percent warning made measurable.
3. Filter the multiplier bank the same way, with the problem's own tests deciding a
   reconstruction that merely restated the body.
4. **The extraction half of the multiplier, which needs no model at all and is the
   better lever.** PACT (arXiv:2102.06203) got a 167x augmentation out of proof
   artifacts already on disk, zero model calls, and its 121M model beat an 837M one
   trained without them at a matched budget. The seven provers here already emit
   obligation lists, which premises closed a goal, and a refutation witness per
   twin, and this pipeline throws all of it away after reading the verdict.
5. `split-v6.json` is written; the 1,030 stdin answers still need grading and their
   contributing tags re-checked under pool v6.
6. The lifter and lowering rows for WS-16.2's other half.
