# Section 3's curve on the clean 200: prompted models of every size against the fine-tuned student; registered before any answer is drawn

AMBITION.md section 3, as re-read on 2026-10-01: the curve is fine-tuned small models against prompted large ones.
Only one prompted model has been measured on the clean 200 by the corrected instrument, Phi-4-mini (3.8B): 3 at one
kernel and 3 by all seven prompted, 9 and 7 under `t`'s grammar (`t/PREDICT-2026-10-01-replication.md`). The
fine-tuned 4B student reads 16 to 27 at one kernel and 8 to 13 by all seven over the rounds since
(`DISCLAIMERS.md`). This measures where it sits among prompted models from 0.8B to 671B parameters.

## The measurement

Every model is asked exactly as Phi-4-mini prompted was: prompt v5, pool v5, the clean 200
(`~/scratch/clean-200-ids.txt`), 17 answers a problem (one at temperature 0, sixteen at temperature 0.7 with seeds 1
to 16), a 3,072-token reply budget. Graded by the instrument of section 1's judgement: `extract --promote-header`,
the problems' tests, the seven kernels on the lab, the 1,000-draw specification check with each task's own generator
and MBPP+'s references, `t/score_levels.py --min-completeness 0.6`, pooled over the 17 sets. If the case split
(`t/PREDICT-2026-10-04-case-split.md`) is merged before a set is graded, the set is graded with it, and any cell it
changes is reported beside the old reading as for every other set.

**On our own hardware** (the lab's GPU 2, vLLM 0.29, weights from Hugging Face, all Apache-2.0): Qwen3.5-0.8B, 2B,
4B (the weights the student is fine-tuned from), 9B in bf16, and Qwen3.5-27B with vLLM's fp8 weight quantization (bf16
does not fit one 48 GB card). The server applies Phi's sampling (`--generation-config vllm --override-generation-config
'{"top_p": 0.95, "top_k": -1, "repetition_penalty": 1.0, "min_p": 0.0}'`) and turns thinking off
(`--default-chat-template-kwargs '{"enable_thinking": false}'`), as the base-model selection asked the Qwen3.5 models
with thinking off (`t/PREDICT-2026-10-01-base-model-selection.md`).

**On Bedrock** (the capped proxy, flex tier, openly licensed models only): gpt-oss-120b (117B, 5.1B active), Qwen3-
235B-A22B-Instruct-2507, DeepSeek-V3.2 (671B, 37B active). The pilot's cost per sample projects about $10 for the three
at 3,400 answers each, inside the proxy's $60 cap ($42.26 spent). They run when the AWS session is renewed (it lapsed
at 11:00Z). Through Bedrock's endpoint the client sets only the temperature, so top-p is the provider's default.

## Predictions

- **Z1.** The prompted Qwen3.5-4B, the student's own starting weights, proves at most 8 at one kernel (under half of
  the shipped recipe's three-seed mean, 16.7).
- **Z2.** No prompted Qwen3.5, 0.8B to 27B, proves as many at one kernel as the lowest shipped-recipe seed (16).
- **Z3.** DeepSeek-V3.2 proves at least 28 at one kernel, more than the best student seed measured (27).

The table that results (parameters, total and active; at least one kernel; all seven) is section 3's curve, with
Phi's two readings and the student's seeds beside it, and is reported whichever way the predictions fall.

## What it cannot show

MBPP and HumanEval are public, so every prompted model may have read their Python solutions; none has read `t`, and
the proofs and specifications are what the gate counts. The clean 200 answers drawn here are measurements only: no
training row may come from them (the pool builds refuse every clean-200 id, `t/student_rows.py`).
