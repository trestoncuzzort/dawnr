# Local tokenizer check, 2026-09-19

Before measurement: train byte-level BPE on only the training document split of
the existing `t/out/loop-locallm/corpus.txt`, requesting 8,192 vocabulary entries.
The tokenizer uses the complete byte alphabet and performs no normalization.

Prediction: it preserves every character of both splits and the unseen Unicode
probe, while reducing token count below half the character count on each split.
Any round-trip difference fails correctness; a ratio above 0.5 falsifies the
compression prediction. Report actual vocabulary size and both ratios. This
measures representation and context efficiency, not model accuracy.

The character checkpoint format must still load. New checkpoints bind the
tokenizer's encoding configuration and token IDs to the weights by fingerprint.

Measured on the lab: all three round trips passed. The trained vocabulary had
1,382 entries. Training text fell from 85,593 characters to 33,654 tokens
(0.3932 tokens/character); validation fell from 9,441 to 3,775 (0.3999). Both
compression predictions held. The unseen Unicode probe used 20 tokens for 16
characters/24 UTF-8 bytes and was preserved exactly; no compression prediction
was made for that probe. Exact hashes and counts are in
[tokenizer-results-2026-09-19.json](tokenizer-results-2026-09-19.json).

Explicit train/validation files are also supported for source-module grouping.
In that mode the tokenizer fits only the supplied training text, and the corpus
preserves both partitions' exact text and order instead of reshuffling them.
