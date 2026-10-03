# Reinforcement learning on the 4B student, the verifier as the reward: registered 2026-10-01 14:36Z, before any of its samples

`t/RL-DESIGN-2026-09-26.md` section 9: on the chosen weights the start rule is met for the first time (a
test-passing answer among ten samples on 27 of 100 dev problems the student never trained on). This is the
run section 7 step 3 describes, moved from the from-scratch model to the student.

**Method, as published, nothing invented in the update:** GRPO (DeepSeekMath, arXiv:2402.03300, 4.1.2,
outcome supervision) with the mean-only advantage of Dr. GRPO (arXiv:2503.20783; `loss_type="dr_grpo"`,
`scale_rewards=False`), through TRL's `GRPOTrainer` (huggingface.co/docs/trl, TRL 1.13) with a LoRA adapter on
the merged student; KL coefficient 0.04, learning rate 5e-6, eight answers a problem, at most 1,024 new tokens,
temperature 0.7 (the student's own sampling setting), thinking off, prompt s2. The prompts are the student's
own: `spec_experiment.build_prompt(entry, "s2")`.

**Reward:** `t/rl_reward.py`'s tiers (none 0, parses 0.05, typed 0.10, tests 0.50, proved-weak 0.75,
proved 1.00), rule-based as DeepSeek-R1 (arXiv:2501.12948), with two updates so it pays for what the gate
now counts: the answer is extracted as every student answer is (`extract --promote-header`), and "proved"
asks the specification check's `complete()` rule (both mutant families at least 60%, SAFE arXiv:2410.15756)
where it asked "not weak". Dafny is the kernel in the loop, on the desktop (section 1 of the design: a row
clean in Dafny is clean in all seven 97.8% of the time).

**Prompts:** `rl_reward.rl_prompt_ids` (training problems only; the split's eval ids, every dev id and the
decontamination exclusions refused), minus the 97 whose function name is that of one of the 33 held-out
specification-given questions, minus the 296 in the student's own rows. **Difficulty band** (STP and PSV, as
section 7 step 3): four samples on each of 800 of these drawn by a fixed seed, scored to the tests tier; the
problems with one or two of four passing make the training set. If fewer than 40 qualify, the band widens to
three of four; if still fewer than 40, the run stops and that count is the result.

**Run:** two passes over the band. **Start:** the latest student when the card is free (the 4B on v6 if it
trained and was measured, else the 4B on v5). **Measured after:** one greedy dev answer through the gate,
and the 33 specification-given questions, against the same measurements of the starting student.

## Predictions

91. One greedy answer passes the tests on at least 3 more dev problems than the starting student's.
92. It proves at least 1 more dev problem on a complete specification than the starting student's.
93. On the 33 specification-given questions it proves (all seven kernels) at most 1 fewer than the start.
94. Mean reward over the band's groups is higher in the second pass than in the first.

Reported beside them: the share of groups with spread in each pass; answers that reach the top tier in
Dafny and fail another kernel (counted, since the loop asks one kernel).

## Amendment, 2026-10-01 19:13Z, before any band sample: the start is the 4B on v5

The start rule this run stands on (27 of 100 unseen dev problems with a test-passing sample among ten,
`t/RL-DESIGN-2026-09-26.md` section 9) was measured on the 4B on v5's samples, and v5 is the measured-best
student for writing `t` (`t/PREDICT-2026-10-01-v6.md`, part 3: one greedy answer passes the tests on 13 dev
problems for v5, 6 for v6). The run starts from the 4B on v5 with its own rows for the band's exclusions.
Predictions 91 to 94 are unchanged, measured against the 4B on v5's own numbers.

## Amendment, 2026-10-02 02:14Z, after a band start that ran out of memory: prompts capped, smaller batches

The band's sampling stopped at 02:12Z when a batch of 16 padded to a 22,280-character prompt ran the card out of
memory (`t/rl_student.py band` had drawn 800 problems, 1 of them over 6,000 characters). Problems with prompts
over 6,000 characters are left out before the seeded draw (`--max-prompt-chars 6000`), and sampling runs at batch
8. The run now follows the specification round on the card. Predictions 91 to 94 are unchanged.

## Amendment, 2026-10-02 02:59Z, after a second out-of-memory stop: a batch that does not fit is halved

The round at batch 8 ran 42 minutes and stopped out of memory (02:57Z), losing what it had written; the RL band
was stopped by hand before it could. Decoding now does what accelerate's `find_executable_batch_size` does
(github.com/huggingface/accelerate, utils/memory.py): a batch that runs the card out of memory is split in half
and decoded again, and a single prompt that still does not fit gets an empty reply, counted as no answer
(`t/student_generate.decode`, tested). The caps and batch 8 of 02:14Z stay. Predictions unchanged.

## Amendment, 2026-10-03 20:41Z, before it runs: where

The desktop card is busy with the specification round, and the lab's GPUs 2 and 3 are free, with the operator's
word to use free GPUs. RL runs on the lab's GPU 2 (an RTX 6000 Ada): the same starting student (the 4B on v5, its
merged weights copied), the same rows, `t/rl_student.py band` and `train` with the same arguments, the reward's
Dafny run on the lab itself (`T_LAB=local`, which `rl_reward.prove` supports) instead of over SSH to it, then the
merge, the 33 specification-given questions and one greedy dev answer through `transformers serve` exactly as
before. The answers come back to the desktop and are graded and scored there as registered. The lab's PyTorch is
2.13 (desktop 2.11); TRL 1.13.0, transformers, peft and bitsandbytes are the same versions. Predictions stand.
