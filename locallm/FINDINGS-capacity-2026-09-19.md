# What this machine can actually train, and why that matters

The core report checked that an optimizer step runs at 312M parameters. That is
not the same question as **how large a locallm trains here**, and until today
nobody had asked it. The locallm rows trained from random weights on the project
scoreboard are **10.9M** and **25.5M** parameters with a character tokenizer on a
77 KB corpus; the pretrained-core rows are **92.9M** with a byte-BPE tokenizer.
Each figure is the `digest` its own 232 answer records carry.

`locallm/measure_capacity.py` runs real optimizer steps at each size on real
data shapes and reports what fits and how fast, or that it did not fit.

## Measured, one card, shared with another user

RTX 6000 Ada, 47.4 GiB total, **16.4 GiB free at the time**; GPT architecture,
gradient checkpointing on, block 512, vocabulary 8,192, bf16.

| size | parameters | batch | status | peak reserved | tokens/s |
|---|---:|---:|---|---:|---:|
| 91M | 91,740,672 | 2 | trains | 1,664 MiB | 23,539 |
| 162M | 210,454,528 | 2 | trains | 3,444 MiB | 10,991 |
| 312M | 311,224,320 | 2 | trains | 5,026 MiB | 7,677 |
| 500M | 483,402,240 | 2 | trains | 7,728 MiB | 4,697 |
| **780M** | **874,672,000** | 2 | **trains** | 13,790 MiB | 2,693 |
| 1.2B | 1,629,294,592 | 2 | out of memory | — | — |
| 780M | 874,672,000 | 8 | trains | 14,792 MiB | 2,643 |
| 500M | 483,402,240 | 8 | trains | 8,548 MiB | 4,809 |
| 312M | 311,224,320 | 8 | trains | 5,706 MiB | 7,396 |

**Optimizer steps at 875M parameters fit on one shared card**, at 2,693 tokens
a second: 80 times the parameter count of the 10.9M model on the scoreboard and
nine times the 91M cores the pretraining studies used. What this establishes is
that such a model steps, and how fast. It does not establish that size is why
earlier work stalled; nothing here has trained a large model to a score. The
1.63B configuration fails for an arithmetic reason, not a mysterious one: AdamW
in fp32 holds parameters, gradients and two moments, sixteen bytes per
parameter, so 1.63B needs about 26 GiB of state before a single activation.

What follows from that arithmetic, stated as arithmetic rather than as
measurement: a **free** 47 GiB card should carry roughly 2.5B parameters, and
four cards under `train_distributed.py` do not raise that ceiling at all,
because it uses DDP, which replicates the whole model and optimizer on every
rank. Four cards buy throughput, not size. Sharded optimizer state (FSDP or
ZeRO) is what raises the ceiling, and this repository does not implement it.

## The other half of capacity, which is the binding one

The frozen source corpus is 153 MB of training text, about **46M BPE tokens**.
The 4000-step studies consumed 262M tokens per arm, so they made roughly six
passes over it. A 91M model at 46M tokens is already far below the usual
compute-optimal ratio; a 312M or 875M model on the same corpus would be further
below it still. The measured headroom is in parameters. That data is *the* binding constraint
is an **inference** from 46M tokens against the usual compute-optimal ratios,
not a measurement made here: no run in this repository has varied corpus size
with everything else held still. It is the inference the roadmap's own order --
core, then t capability, then data beyond `nl/`, already encodes, and it
remains to be tested.

So "scale the model" and "scale the data" are not the same lever, and only one
of them has been measured to have room. Both numbers belong next to each other
whenever this project decides a size again.

## What was done with it immediately

The first thing this measurement makes obvious is not a bigger model. It is
that a **pretrained** core had never been put through the pipeline at all:
locallm's scoreboard rows are models trained from random weights on 77 KB.
`locallm/continue_from_checkpoint.py` now specializes an existing checkpoint on
the filtered t corpus, keeping its frozen tokenizer and weights, and exports an
ordinary project checkpoint the existing generate and grade paths already read.
The 92M GPT core from the 4000-step study, specialized on 39,191 tokens of
filtered t data in 30 seconds, moved held-out corpus loss from 3.104 to 0.574.
Whether that turns into clean answers on the 232 held-out problems is being
graded now, and loss has already failed to predict behaviour twice this week.
That comparison moves size, tokenizer, pretraining corpus and training recipe
at the same time, so it can show whether the pipeline's number moves and never
which of the four moved it. Isolating controls, the same 92M from random
weights on the same corpus and the 10.9M recipe with the byte-BPE, are not
run yet.
