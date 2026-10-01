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

## Outcome, 2026-10-01 10:08Z

The 4B on v4, exported with llama.cpp's own two steps (`convert_hf_to_gguf.py --outtype bf16
--no-mtp`, then `llama-quantize Q4_K_M`: 2.71 GB, 5.13 bits a weight), served by `llama-server`
on 12 threads of the lab's CPU at the lowest priority. The prompt the server renders was
compared with the training template before anything was asked: identical. (`--no-mtp` is needed
because the merged student has no multi-token-prediction block and the converter otherwise
declares one; the first export did not load.)

**The 33 specification-given questions**, one greedy answer each, the same gates and kernels:

| | bf16 (on record) | 4-bit |
|---|---:|---:|
| answers that parse and keep the specification | 33 | 32 |
| a kernel refutes the program | 4 | 8 |
| proved by at least one kernel | 28 | **23** |
| proved by all seven | 26 | **22** |

21 of the 33 replies are word for word the bf16 student's. Of the 12 that differ, the 4-bit
student loses 5 questions the bf16 one proved (one reply does not parse, four are refuted by a
kernel) and gains none; one moves from six kernels to seven. Five losses and no gains is p = 0.06
by an exact two-sided sign test: a loss, of about one proof in six, not yet a certain one.

**The 100 dev problems**, one greedy answer under the student prompt:

| | bf16 (on record) | 4-bit |
|---|---:|---:|
| valid tasks | 38 | 44 |
| pass the tests | 9 | 10 |
| proved by at least one kernel, specification agrees | 4 | 3 |
| the same on a complete specification | 2 (113, 727) | 2 (113, 727) |

**Speed**: 221 requests, 15.5 tokens a second overall (median 16.2, slowest 8.6), on 12 threads
at the lowest priority beside another user's jobs.

45. **At least 24 of 33 proved by one kernel or more: falsified.** 23.
46. **At least 22 by all seven: holds, at exactly 22.**
47. **At least 7 dev problems pass the tests: holds.** 10.
48. **At least 10 tokens a second: holds.** 15.5.

**Reading.** At 4 bits the student keeps its English-to-`t` behaviour on dev (the same two
problems proved on complete specifications) and loses about one proof in six when the
specification is given, by writing bodies a kernel refutes. llama.cpp's own remedies are a
higher-precision type or an importance matrix; the next measurement is the same 33 questions at
Q8_0 and at Q4_K_M with an importance matrix computed from training rows.

## Amendment, 2026-10-01 10:20Z, before either file exists: which quantization keeps the proofs

llama.cpp's own answers to a quantization loss (`tools/quantize/README.md` and
`tools/imatrix/README.md`, fetched 2026-10-01) are a type with more bits and an importance matrix
computed on calibration text (`llama-imatrix -m model.gguf -f text -o imatrix.gguf`, then
`llama-quantize --imatrix imatrix.gguf ... Q4_K_M`). Both are measured the same way as above:

- **Q8_0** from the same bf16 file (8.5 bits a weight in the README's table).
- **Q4_K_M with an importance matrix** computed on the student's own training rows rendered with
  its chat template (the v4 rows it was trained on; checked to hold none of the 33 questions),
  100 chunks of 512 tokens, the output layer left out as the README advises.

51. At Q8_0 at least 30 of the 33 replies are word for word the bf16 student's. Falsified below 30.
52. At Q8_0 at least 27 of 33 are proved by one kernel or more (bf16 28). Falsified below 27.
53. Q4_K_M with the importance matrix proves at least 26 (plain Q4_K_M 23). Falsified below 26.
