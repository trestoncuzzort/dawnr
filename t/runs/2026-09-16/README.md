# Runs of 2026-09-16

The data behind the paragraphs dated 2026-09-16 in `internal/ROADMAP-LOG.md`, kept so the loop can continue on another machine.

- `27b-answers/`: Qwen3.8-27B-FP8 answers on MBPP. `qwen3.8-27b-fp8` is pool v1 at temperature 0, `-v3` is pool v3 at temperature 0, `-v3-s2` is pool v3 at temperature 0.7, seed 2. Each has the raw replies, the extracted tasks, `tests.json` and `kernels.md`. Set 2's kernel grading was stopped unfinished.
- `loop-data/`: the fixed train and eval split (`split-v3.json`), the clean SFT set and bug pairs built from the 27B answers (`sft-r3-27b.jsonl`, `pairs-r3-27b.jsonl`), the clean corpus (`corpus.txt`), the size-matched raw corpus, and the copy-check keys.
- `filter-loop/`: `t/loop_filter.py` runs. `clean/` builds each model from the clean corpus plus every clean program so far (round 2's grading was stopped). `raw-matched/` builds one from the same amount of raw 27B output. `raw-full/` builds one from all raw output. Each round has its corpus, the model locallm built, the 500 samples, the novel tasks and `kernels.md`.
- `heldout-locallm-r0/`: the model built from the clean corpus answering 232 held-out problems, graded.
- `logs/`: the run logs.

Headline: at the same data size, 46 of 500 programs were clean from the clean corpus against 3 from raw output. The clean loop reached 57 at round 1.

2026-09-17: those counts include exact copies of corpus tasks the copy check missed (it compared the format version, and the 27B answers are `t 0` while samples are `t 1`). With copies removed: 29 against 1, and 31 at round 1 (`t/runs/2026-09-17/README.md`).
