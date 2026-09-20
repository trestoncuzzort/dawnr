# Corrections this project made against itself

Published claims that turned out to be wrong, and what they are now. They are
kept here rather than quietly fixed, because a project that only reports its
successful measurements is not measuring anything.

- **A column said "checked" when nothing had checked it.**
  `score_heldout.py` counted an answer as specification-checked whenever it was
  absent from the disagreement list, so an answer set nobody had run
  `spec_check.py` over scored full marks. Round 5's student was reported as 3
  clean surviving the check against Phi's 2, "one ahead". Checked properly it
  is **2 against 2**, a tie. The tool now records which tags it checked and
  prints `not checked` for the rest.

- **"Not one weak specification" was a property of the search, not the data.**
  A first pass over 388 proved answers found no weak specification anywhere and
  it was written up that way. Widening the search found one: a
  maximum-of-three problem whose specification forgot `r >= c`, so at
  `a=15, b=28, c=30` it also accepts 28. It is nearly tight, rejecting 345 of
  350 wrong answers, which is exactly why a narrow search missed it. The
  substance held (weakness is rare, wrongness dominates) and the headline
  number did not.

- **The copy check kept each task's format version**, so exact copies counted
  as new: the filtered-against-raw result was first recorded as 46 against 3
  and is **29 against 1** recounted.

- **Repair looked obvious and does not work:** a 14B model handed seven
  verdicts writes worse proofs more often than better ones.

- **A "constrained" run was not constrained.** A `--grammar` flag reached three
  `model.generate` call sites and missed the one every held-out run takes. It
  was caught by its own numbers: 158 parse failures against the unconstrained
  run's 159.

- **A tokenizer silently destroyed sound answers.** DeepSeek-Prover-V2's drops
  every space under transformers 5.17, turning sound answers into
  `t1tasksmall_nnum(...)`. The generator now round-trips a line of t through a
  tokenizer before trusting it.

- **Three readers did not know the corpus format had grown.** Training
  documents gained a `Signature:` line and then an `Example:` line. Each
  addition broke a different reader that knew only the heads existing when it
  was written: the answer splitter left two programs in one reply and 216 of
  232 answers failed to parse; the copy check's stripper dropped documents
  silently; the generator failed to strip a head off the model's own reply and
  all 24 answers of a run were lost. There is now one stripper every reader
  calls, and a test that fails if a reader is written without it.

- **A grading command reported success without grading.** A load guard added to
  `t/grade_lab.sh` used `set -- $BUSY`, which replaces the positional
  parameters, so the script's mode argument was overwritten, the case statement
  matched no branch, and it exited 0 having graded nothing. Every call in that
  window believed it had a table. The same root cause had already silently
  dropped the caller's decoding flags in `t/gen_fleet.sh`.

## A token count with no file behind it, removed 2026-09-20

`README.md` said locallm was trained on "46M tokens of source plus **50,142
tokens of specialization**". The string `50,142` occurs nowhere else in this
repository. No run record holds it: the `run.json` beside the round-7b
checkpoints stores losses and `steps_run` and no corpus statistics, and the
tokenizer those models use is character level, so none of the candidate corpora
(`corpus-r7.txt` 77,345 bytes, `corpus-r7-headed.txt` 118,818,
`corpus-r8-headed.txt` 133,082) yields that number under it. The nearest figure
on record is a different one, "39,191 tokens of specialization", in
`t/PREDICT-2026-09-19-round7.md`, for round 7 rather than for the arm the
headline uses.

`README.md:94` states the rule this broke: *"Every number links to the script
that produced it. If a number here has no file behind it, it is a bug."* The
sentence now cites the source-corpus figure to the file that measures it and
gives the specialization corpus as the byte size of the file itself, which is
checkable with `ls`. The token count returns when something measures it.

