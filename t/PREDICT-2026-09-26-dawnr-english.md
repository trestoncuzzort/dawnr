# dawnr's general-English pretraining layer: predictions before any number

Written before the tokenizer is measured and before the decontamination filter runs on the
downloaded shards. Nothing below was tuned to a result.

## 1. Tokenizer compression: does the code-trained BPE read English?

The core's tokenizer (`tokenizer.json` beside the r12 core, e.g.
`~/scratch/dawnr-pipeline/core-wd08/tokenizer.json`) is a byte-level BPE, 8,192 entries, trained
on ~150 MB of the source-code corpus (`internal/PRETRAIN-R12-2026-09-25.md`). On its own training
domain it already measures 2.4994 chars/token on the DAWNR pipeline's train-side conversations and
2.5224 on validation (`~/scratch/dawnr-pipeline/core-1/report.md`, "Tokenizer" section) --
call the code baseline **~2.50 chars/token**. A general-purpose BPE at a much larger vocabulary
(GPT-2's 50,257) is well known to sit near 4 chars/token on English prose; nanochat's own
`tok_eval.py` compares against exactly that baseline for the same reason
(`DAWNR-PIPELINE.md`, stage 1). Because this tokenizer is byte-level it can never fail to encode
English -- every unseen sequence falls back to individual bytes -- but a small, code-tuned merge
table should waste more of its budget on single bytes and short code-only merges (`->`, `::`,
indentation runs, `requires`/`ensures` keyword fragments) than a tokenizer that ever saw natural
English sentences.

**Prediction, with the number that would prove it wrong:** chars/token on a downloaded FineWeb-Edu
sample will land **between 2.0 and 2.9**, i.e. close to or below the code baseline rather than
comfortably above it. If it is instead 3.0 chars/token or higher, the vocabulary already transfers
better to English than the code-training story predicts, and the finding is that the BPE merges
that matter (whitespace-prefixed word starts, common short words) are shared between code and
English rather than domain-specific.

**Decision rule, fixed now:**
- **< 2.0 chars/token** (badly fragmented, near single-byte encoding on ordinary prose): **retrain**
  a fresh tokenizer on a code+English mixture. The core's frozen embeddings would need re-learning
  either way at that level of fragmentation, so there is nothing to protect by extending instead.
- **2.0 to 2.9 chars/token**: **extend** the vocabulary with English-only merges appended past the
  existing 8,192 entries and initialised to the mean embedding (Hewitt; the same pattern
  `continue_from_checkpoint.py` already uses for FIM sentinels and `chat.py` uses for the chat
  tokens), rather than a full retrain, so the code-trained weights and the r12 core checkpoint stay
  usable.
- **>= 3.0 chars/token**: **keep** the tokenizer as is; a general-English pretraining stage adds no
  tokenizer work.

## 2. Decontamination: how much of the downloaded web text is dirty?

The protected set is every held-out eval problem (`t/out/loop/split-v5.json`, 232 ids) plus every
dev problem (`t/r12-dev-ids.json`, 100 ids) -- their statement text, test assertions and reference
solution, pulled from `nl/data/{mbpp,humaneval,apps_raw_train,apps_raw_test}*.jsonl.gz` on the lab.
That is on the order of 330 short programming problems (MBPP entries run tens to a couple hundred
words; APPS statements run longer). FineWeb-Edu's own pipeline already runs MinHash deduplication
against itself and a classifier for "educational" content, which should suppress most competitive-
programming judge pages, but Common Crawl is large enough that some "N ways to solve <MBPP-style
problem> in Python" tutorial or interview-prep page is plausible for at least the more famous
HumanEval-style problems.

**Prediction, with the number that would prove it wrong:** out of the ~9-10 million documents in the
downloaded FineWeb-Edu sample-10BT shards, the 13-gram filter will flag **between 1 and 10,000
documents** (roughly 0.00001% to 0.1%) as sharing a 13-gram with a held-out or dev problem's text,
tests or solution. Zero flagged documents would not be a clean bill of health, it would be grounds
to suspect the filter itself is broken (wrong tokenisation, case mismatch, or a bug in the sliding
window) rather than genuinely contamination-free data, since GPT-3's own contamination study found
measurable overlap at this exact filter design and scale (arXiv:2005.14165, `overlap_frequency.md`
in the paper's own repository). More than 1% flagged would say the n-grams themselves are too
generic (index-like sequences: line numbers, "for i in range", boilerplate the GPT-3 repository's
own top-frequency 13-gram list warns about) and the filter needs the same kind of boilerplate
exclusion before the count means anything.

**Decision rule, fixed now:**
- **0 flagged:** treat as suspicious, not clean. Run a smoke test first (a document built by pasting
  one held-out problem's exact text into a dummy record) before trusting a zero.
- **1 to 10,000 flagged** (the predicted range): drop them, log ids and examples, proceed. This is
  the expected web-scale base rate, not evidence of a systemic problem.
- **> 10,000 flagged** (order of magnitude above prediction): read a sample of the matches before
  dropping anything; check whether the shared 13-grams are generic boilerplate (numbers, common
  code idioms) rather than problem-specific text, and tighten the n-gram extraction (strip pure
  numeric/punctuation n-grams, as GPT-3's own filtering notes) before reporting a document count.

## What these two predictions are for

Both numbers get written into `internal/PRETRAIN-DAWNR-GENERAL.md` next to what was actually
measured, whichever way they land. The tokenizer decision rule and the decontamination decision
rule above are fixed before either script runs, so the report cannot be shaped to fit the result
after the fact.
