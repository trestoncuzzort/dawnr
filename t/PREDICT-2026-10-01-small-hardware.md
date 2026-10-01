# The student at 4 bits on a CPU: registered 2026-10-01 08:52Z

## What this is

"Usable by everyone" (rung R7, `internal/LADDER-PLAN-2026-10-01.md`) and the small-hardware row
of `AMBITION.md` ask that the student run as a 4-bit file on a machine with no large card. No
student has been exported or run that way. This does it for the 4B on v4 (the student whose
results are on record; a later student goes through the same steps) and measures whether its
answers survive, with the gate's own counts and not perplexity.

## What it stands on

llama.cpp's own two phases (github.com/ggml-org/llama.cpp, `tools/quantize/README.md`, fetched
2026-10-01): `convert_hf_to_gguf.py DIR --outtype bf16`, then `llama-quantize ... Q4_K_M`. It
says accuracy loss "is usually measured in perplexity and/or KL divergence" and "can be
minimized by using a suitable imatrix file"; its table gives 4.89 bits a weight at Q4_K_M. No
importance matrix on this first pass; if proofs are lost, that is the published remedy.

## The measurement

- **Export.** The merged 4B on v4 (bf16 safetensors) to a bf16 GGUF, then Q4_K_M. On the lab's
  CPU, with llama.cpp built without GPU support.
- **Serving.** `llama-server`, 12 threads, thinking off. Before any question is asked, the
  prompt the server renders for one conversation is compared with the prompt the training code
  renders (`t/student_sft.py`: the tokenizer's chat template with thinking disabled); a
  difference stops the measurement.
- **The 33 specification-given questions** (`t/PREDICT-2026-10-01-spec-given.md`), one greedy
  answer each, 1,024 new tokens, through the same four gates and the seven kernels. The bf16
  student on record: 33 keep the specification, 28 proved by at least one kernel, 26 by all
  seven.
- **The 100 dev problems**, one greedy answer under the student prompt, through the gate. The
  bf16 student on record: 38 valid tasks, 9 pass the tests.
- **Speed**: tokens a second while answering, as the server reports it.

## Predictions

45. The 4-bit student is proved by at least one kernel on at least 24 of the 33 (bf16: 28).
    Falsified below 24.
46. By all seven on at least 22 (bf16: 26). Falsified below 22.
47. On dev its one greedy answer passes the tests on at least 7 problems (bf16: 9). Falsified
    below 7.
48. It writes at least 10 tokens a second on 12 threads of the lab's CPU. Falsified below 10.

Not measured here: an 8 GB card (the only small card this project can reach is not on tonight),
and the gate itself on a fresh machine, which is the other half of R7.
