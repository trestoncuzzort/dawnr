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

## The headline arm was sampled, not greedy, found 2026-09-20

Every one of the 232 answers in `locallm-r7b-headed2`, the arm behind the
README's tie with Phi-4-mini, records `temperature 0.5, top_k 20, seed 1`.
`locallm/FINDINGS-round8-2026-09-19.md:18` names that row
"locallm r7b headed2 (heads, **greedy**)". It was not greedy. The same is true
of `locallm-r7-92m`. Every other recent arm really is greedy at 0.0:
`locallm-r7b-greedy`, `locallm-r8`, and all three r9 seed arms.

Where it came from: `t/loop_locallm.py:338` defaults `--temperature` to 0.5, so
an arm generated without that flag is sampled. `t/gen_fleet.sh` was supposed to
forward the caller's flags and did not, because commit `75a43fa` changed the
call site to read `"${EXTRA[@]}"` and never added the assignment that fills
`EXTRA`. On bash 4.4 and later an unassigned array expands to zero words
instead of failing, so the script dropped `--temperature 0`, printed its answer
count, exited 0 and wrote its sentinel. Fixed 2026-09-20; the diagnosis and the
citation are in that commit.

**What this does and does not change.** The three clean answers are still three
clean answers: they passed the problem's own tests, verified in all seven
kernels with the twin refuted, and survived `spec_check.py`. Nothing about the
grading is affected. What changes is the provenance. The headline is one sample
from a temperature-0.5 distribution rather than the deterministic output of a
fixed recipe, reproducible only at seed 1, and "greedy decoding" is listed in
`SCOREBOARD.md` among the things that worked.

It also breaks a premise in `t/PREDICT-2026-09-20-seeds.md`, which registers the
three r9 arms as "one recipe" with the headline, "greedy decoding". They are
greedy and the headline is not, so those arms measure seed variance of a
DIFFERENT recipe than the one in the README. A note saying so is appended to
that file; the predictions themselves are left exactly as registered.

- **Two scoreboard rows understated their own parameter count by 3.4x and 8x.**
  `SCOREBOARD.md` called locallm round 4 and round 5 "3.2M". Every one of the 232
  answer records each arm wrote carries the true figure in its `digest` field:
  **10,875,648** for `locallm-r4` and **25,524,224** for `locallm-r5`, unanimous
  across all 232 in both arms. The same field reads `4,891,136` for `locallm-r0`,
  also published as "about 3.2M", and `92,920,320` for every 92M arm, which was
  labelled correctly.

  Where it came from: 3,213,312 is what `locallm/train.py`'s own defaults build
  (4 layers, 4 heads, width 256, block 128), and `cmd_train` never uses them.
  `t/loop_locallm.py` defaults to 6 layers, 6 heads, width 384, block 512, which
  is r4's 10.9M; r5 then ran `--layers 8 --width 512`, which is r5's 25.5M. The
  label was read off the wrong end of the code and never checked against a run.

  Three independent confirmations, because the arithmetic had a trap in it. The
  checkpoints are 43,502,592 and 102,121,472 bytes in 76 and 100 tensors; 76 and
  100 are exactly `12n+4` for 6 and 8 transformer blocks, which rules out
  optimizer state, since an Adam save carries roughly three times the tensors. So
  these are weights only and bytes over four gives the same 10.88M and 25.53M.
  Had they instead held optimizer state, 3.2M would have been consistent with
  r4's 43.5 MB and this correction would have been the error.

  **What it changes.** The README's "Phi-4-mini, about 1,200 times larger" and
  the scoreboard's "about 1,200 times smaller" are **about 350 times**, against
  r4's 10.9M. The claim they support does not move: 209 well-formed answers of
  232 against Phi's 12 is the measured number either way, and the 3-clean tie is
  a 92.9M arm, which was never mislabelled. What does move is the size curve the
  project reasons with. `LIMITS.md` and `internal/RESEARCH-NEXT-2026-09-20.md`
  argued that "a bigger model alone" failed because 92M wrote fewer well-formed
  answers than 3.2M, a 29x span. The real span is 10.9M to 92.9M, **8.5x**, and
  the same comparison moves seven things at once: parameters, tokenizer,
  pretraining, epochs over t, learning rate, dropout, and what `block_size 512`
  means in characters. Corrected in place in `SCOREBOARD.md`, `README.md`,
  `LIMITS.md`, `AMBITION.md`, `locallm/ACHIEVEMENTS.md`, five `locallm/FINDINGS-*`
  files and three `internal/` documents.

  **Left as written, deliberately.** The `t/PREDICT-*` files reason against "the
  3.2M rows"; registered predictions are never edited after the fact, and the
  note above is the record instead. `internal/ROADMAP-LOG.md`'s 2026-09-16 entry
  and `t/runs/2026-09-17/README.md` describe an earlier filter-loop model as
  3.2M; no `digest` was recorded for that run, so the figure is unverified rather
  than known-wrong and is left alone rather than replaced with a guess.

- **Two scoreboard cells counted an answer nobody could check as an answer that
  passed.** `SCOREBOARD.md` gave locallm rounds 4 and 5 a 2 in "after the
  specification check". Each arm has two clean answers and in each only one is
  checkable; both arms' other one is `mbpp_800__remove_all_spaces`, which returns
  `no valid draws` because it is a string problem, `t` has no string type, and no
  drawn argument shape fits the reference solution. The scoreboard's own sentence
  says how to count that case — "one of Phi's three cannot be checked at all, so
  on that column it reads 3 against 2" — so the cells are **1 and 1**. This is
  the first entry in this file recurring: the tool was fixed to print
  `not checked`, and the published table was never regenerated from it.

  Found while fixing a worse version of the same thing. `t/out/spec-disagree.json`
  held 496 result rows and none at all for `locallm-r7b-headed2`, `locallm-r8` or
  `phi4-mini-eval2-2026-09-19`, the three arms behind "3 against 2", because two
  runs had asked for `--pool v5` on arms graded against the v3 held-out split and
  every answer was skipped as out-of-pool while the tags were still recorded as
  checked. Re-run against the right pool, **the headline holds exactly**: 3 of 3
  agreeing for `locallm-r7b-headed2`, 2 for Phi's regrade with
  `mbpp_269__ascii_value` uncheckable. The measurement, the per-tag table and the
  code fix are in `t/FINDINGS-spec-evidence-2026-09-20.md`; `spec_check.py` now
  refuses to add a tag it checked nothing for, and says so on the way out.

  Phi's historical `phi4-mini-v3` arm, measured for the first time in the same
  run, has a real disagreement: `mbpp_20__is_woodall` is false at `n = 63` where
  the problem's solution answers `True`.
