# Four-GPU training and source-pretraining study

The core now trains on four GPUs with reproducible checkpoint continuation on the
tested stack. These are infrastructure and capacity results; they do not establish
useful learned answers or a win over Phi. The measured evidence, including failed
resume checks, is in [distributed-diagnostics-2026-09-19.json](distributed-diagnostics-2026-09-19.json).

[train_distributed.py](train_distributed.py) keeps corpus tokens and batch RNGs in
CPU memory, uses BF16 and gradient accumulation, and saves optimizer state plus
each rank's Python, CPU, CUDA and batch RNG state after completed optimizer steps.
Resume checks the schedule, tokenizer, raw data hashes, source, runtime and
evaluation settings. Explicit training/validation files retain their exact UTF-8
bytes and order; the shared frozen tokenizer is copied into each run. Initial
train/validation losses are measured before step one and retained through resume.

## Resume failure and fix

The first four-GPU full-versus-resumed comparison failed: maximum model-state
difference was 0.0075533. Independent runs had already diverged before the resume
boundary. Deterministic kernels and `CUBLAS_WORKSPACE_CONFIG=:4096:8` made the
first two steps identical, but restarting still produced a 0.00028286 maximum
difference. DDP's first-backward bucket rebuild changed reduction order after a
restart. Keeping registration-order buckets with `find_unused_parameters=True`
removed that difference. The extra graph traversal is an explicit reproducibility
cost; deterministic mode is the default.

The fixed small-core check matched all model state, optimizer state, rank RNGs
and losses exactly. A separate medium-core run at the selected full batch also
matched exactly at step two and after resuming to step four. Both comparisons
kept the same four-step learning-rate horizon. Five final regression tests passed,
including actual two-rank CPU and four-rank BF16/CUDA training with dropout.

```sh
# Run only on the lab workstation. The GPU test is opt-in and uses four cards.
cd locallm
T_DDP_GPU_TEST=1 python -m unittest -v test_train_distributed
python -m unittest -v test_run_pretraining_study
```

## Capacity at context 2048

The modern medium model has 91,245,312 parameters; the matched GPT control has
92,920,320. Probes used vocabulary 8192, BF16, dropout zero and the same model
dimensions: twelve layers, width 768 and twelve heads. The modern capacity probes
ran four optimizer steps. Throughput below is the median of steps two through
four, excluding evaluation and checkpoint writing.

| Four-GPU modern configuration | Tokens/update | Reserved GiB/GPU | Optimizer tokens/s |
|---|---:|---:|---:|
| Microbatch 4, accumulation 2 | 65,536 | 7.04 | 272,426 |
| Microbatch 8, accumulation 1 | 65,536 | 11.90 | 271,194 |
| Microbatch 16, accumulation 1, checkpointing | 131,072 | 7.48 | 209,937 |

Microbatch 8 without activation checkpointing is the largest measured productive
fit. Microbatch 16 without checkpointing was skipped after smaller batches
projected 21.8 GiB reserved against approximately 14 GiB then available on the
least-free card. The GPT control also fit microbatch 8: 8.27 GiB allocated and
9.14 GiB reserved per rank. Its second optimizer step measured 324,832 tokens/s;
this shorter probe is not a controlled architecture speed comparison. All timings
come from shared hardware. Allocator figures exclude driver/context allocations.

## Run the fixed comparison

[run_pretraining_study.py](run_pretraining_study.py) runs modern then GPT for seeds
1337, 7 and 42. Each arm uses 1,000 updates of 65,536 tokens, learning rate 0.0003,
50 warmup updates, zero dropout, no activation checkpointing, and evaluation/save
interval 100. All six arms are retained. The protocol and learning predictions are
in [PREREG-source-pretrain-2026-09-19.md](PREREG-source-pretrain-2026-09-19.md).

From the repository root, with the training environment active:

```sh
python locallm/run_pretraining_study.py \
  --corpus t/out/source-corpus-2026-09-19-v2 \
  --tokenizer-dir t/out/source-tokenizer-2026-09-19-v2 \
  --out t/out/source-pretraining-2026-09-19 --check-only
```

Remove `--check-only` to launch. The runner requires accepted manual inspection
bound to the exact audit/tokenizer hashes, and rechecks raw corpus and frozen
source hashes before every arm. It selects four GPUs with at least 13 GiB currently
free, based on the measured 11.90 GiB reservation plus headroom, and retains their
rank order. A process lock prevents concurrent study runners.

`study.json` records every arm and attempt, measured free memory, relative output
and log paths, return codes and endpoint evidence. Seven orchestration tests passed,
including real descendant-process termination and mocked failure/resume sequences.
Any failed process or interrupt stops the study without starting another arm.
After inspecting the failure, the same command with `--resume` verifies completed
artifacts and continues an existing checkpoint. If an interrupted arm has no saved
checkpoint, that explicit resume restarts the arm from step zero. Core/data changes
are refused; they require a separately identified study. There is no automatic
repair or retry. The external completion/failure monitor is separate from this runner.
