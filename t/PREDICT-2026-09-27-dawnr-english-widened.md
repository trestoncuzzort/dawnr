# Widening the English decontamination filter: prediction before the rerun

Written before `t/dawnr_ngram_decontam.py` reruns on the lab with the widened protected set.
Nothing below was tuned to a result. Background: `t/PREDICT-2026-09-26-dawnr-english.md`
registered and resolved the original run (332 MBPP held-out/dev ids, 53 of 12,417,226 documents
flagged); `internal/PRETRAIN-DAWNR-GENERAL.md`'s "Required before the English corpus is
assembled" section requires widening that protected set before any shard becomes training data.

## What is changing

`widened_protected_set` (`t/dawnr_ngram_decontam.py`) adds two families on top of the unchanged
332-id held-out/dev boundary:

- **3 HumanEval ids** (`humaneval:13`, `humaneval:23`, `humaneval:57`) that
  `t/loop_filter.decontamination()` already excludes from training as same-task or behavioural
  duplicates of a held-out MBPP problem. Measured locally: +180 distinct 13-grams (20,858 to
  21,038) from these 3 problems alone, in line with MBPP's own density (~63 distinct 13-grams per
  problem).
- **13,610 CodeContests problems' name+description** (13,328 train + 117 valid + 165 test,
  `nl/data/codecontests_*.jsonl.gz` on the lab, measured directly: 23,928,743 characters of
  name+description in the train split alone, average 1,795 characters per problem), standing in
  for the not-yet-frozen confirmation panel held for the Phi comparison
  (`t/freeze_confirmation_panel.py`, `t/v7_panel.py`, unmerged on `r12-phi-win`).

## The one thing that is not a prediction: a floor

The widened protected set is the old one plus more n-grams; nothing is removed. Every document the
original run flagged must still be flagged (the same 20,858 MBPP-derived 13-grams are still in the
index). **The flagged count cannot go below 53.** If it does, `widened_protected_set` has a bug
that lost the original ids, not a finding about English text.

## The actual prediction

CodeContests is roughly 41x more problems than the MBPP-only boundary (13,610 against 332) and
each problem averages far more text (1,795 characters against MBPP's "tens to a couple hundred
words"), which on its own would suggest many more chances to share a 13-gram with something on the
web. Against that: FineWeb-Edu is a classifier-filtered *educational* subset (`internal/PRETRAIN-
DAWNR-GENERAL.md`, section 1), which should trend toward beginner tutorial content -- exactly the
register MBPP's and HumanEval's "write a function to..." problems already share with "learn to
code" pages, and a register competitive-judge problems (Codeforces/CodeChef flavor text, unusual
premises, contest-specific formatting) fit far less well. The two effects push in opposite
directions and neither this project nor the two papers it already cites for this filter (GPT-3,
arXiv:2005.14165; BigCode's evaluation harness, cited in `t/freeze_confirmation_panel.py`) give a
rate for competitive-programming text specifically, so the range below is wide on purpose.

**Prediction, with the number that would prove it wrong:** the widened filter flags **between 53
and 3,000** documents out of the ~12.4 million scanned (up to roughly 60x the original count,
still under 0.03% of the corpus). Landing at exactly 53 (zero new flags from 13,945 added
problems) would not by itself prove a bug -- CodeContests' register may simply not overlap
FineWeb-Edu's -- but it is checked before being accepted: confirm `codecontests_records` actually
loaded 13,610 rows (not zero from a silent missing-file skip) before reading "no new flags" as a
finding rather than a no-op.

**Decision rule, fixed now:**
- **53 (no new flags):** verify `codecontests_records`/`humaneval_records` returned non-empty
  dicts of the expected sizes before trusting it; if they did, report it as a genuine finding
  (CodeContests' register does not overlap this FineWeb-Edu sample).
- **54 to 3,000 (the predicted range):** drop the flagged documents by id, log ids and examples
  exactly as the original run did, proceed to corpus assembly.
- **> 3,000:** read a sample of the *new* matches (those not already in the original 53) before
  dropping anything, the same review the original prediction file's decision rule specifies for an
  order-of-magnitude surprise, checking specifically whether CodeContests' longer descriptions are
  surfacing generic boilerplate (test-case-format phrasing, constraint boilerplate like "1 <= n <=
  10^5") rather than problem-specific text.

## What this does not cover

This rerun does not re-measure the tokenizer (section 5 of `internal/PRETRAIN-DAWNR-GENERAL.md`,
already resolved: keep) or launch the pre-registered pilot (section 6, still gated on GPU
availability and its own prediction note at launch time). It only widens and reruns the
decontamination filter, and assembles + tokenizes the surviving documents into shards.
