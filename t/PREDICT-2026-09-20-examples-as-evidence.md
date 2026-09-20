# Can the problem's own examples supply evidence where random draws cannot?

**Written 2026-09-20, before reading the repopulated `spec_check` columns.** The
run that produces them (`spec_check.py <the 35 r6 tags> --pool v5 --n 100 --only
clean`) is in flight; no number from it has been read.

## The question

`positive_rejection` admits an answer only when `check_task` returns `agrees`
with at least one valid draw. `check_task` runs the problem's reference solution
on randomly drawn arguments of the shapes the problem's own assertions use. When
`t` cannot express the argument shape — every string problem, because `t` has no
string type — no draw is valid, the status is `no valid draws`, and the answer is
rejected for want of evidence rather than for being wrong.

Measured today: rebuilding r6 from its own 35 tags yields 75 positives against the
87 recorded on 2026-09-18, and **14 of the 14 dropped are that case**:
`remove_splchar`, `replace_blank`, `remove_whitespaces`, `remove_lowercase`,
`fill_spaces`, `replace_spaces`, `remove_extra_char`, `replace_specialchar`,
`is_allowed_specific_char`, `countSegments`, `is_vowel`, `switcheroo`,
`remove_chars`, `dog_age`. Each passed its problem's own tests and read
`verified / refuted` in all seven kernels.

`spec_check.check_points` is a second, independent evidence path. It evaluates the
specification at the problem's **own stated input/output pairs**, which need no
reference run, no random draw and no model. Its docstring records that it reaches
answers `check_task` gives up on: 78 of 149 in one arm today. This is the signal
VeriAct's Spec-Harness gates on as `PostCorr` (5 example pairs sufficed,
`github.com/Mondego/VeriAct`), and Coins' `Pass_all`, whose funnel from
`Pass_first` 60.98% to `Pass_all` 28.05% is where their discrimination lives.

**The proposed change:** admit an answer whose specification holds at every
example its problem states and fails none (`points_held > 0 and points_failed ==
0`) as an alternative to `agrees`, keeping every other gate exactly as it is.

## Predictions

1. **At least 8 of the 14 come back.** Falsified at 7 or fewer. Each has at least
   one stated example in `points`, the interpreter evaluates their `ensures`
   without needing a reference run, and each already survived the seven kernels.
   If fewer than 8 return, the examples path does not reach where I claim it does
   and the honest conclusion is that string problems need a string type, not a
   second evidence path.
2. **None of the 14 is admitted with `points_failed > 0`.** Falsified by any. This
   is the check working at all: an answer whose specification contradicts a stated
   example must be rejected by the gate committed today, not admitted by the new
   path.
3. **The r6 rebuild lands between 83 and 89 positives.** Falsified outside. 75 plus
   at least 8 recovered; above 89 would mean the path admits answers that had
   other evidence problems, which is a bug, not a gain.
4. **At least one answer is newly REJECTED by the examples path** — a specification
   that agreed on random draws and fails a stated example somewhere in the 35 tags.
   Falsified if none is. Measured on the 42 rows that carried these columns before
   today, that count was 0, so this prediction is the risky one: if the examples
   check never disagrees with the draws on several hundred rows either, then it is
   a redundant instrument on this corpus and its only value is reach, not strength.
5. **The 232 held-out problems are untouched.** Falsified by any change to an eval
   count. This change alters which train-split answers become training data; it
   must not move a single evaluation number.

## What this cannot settle

Whether the 14 recovered answers are *correct*. The examples path proves a
specification agrees with the problem at the three or so points the problem
states, which is weaker than agreeing with a reference solution on 100 draws. It
is strictly stronger than the `no valid draws` it replaces, which is no evidence
at all, and weaker than what every other positive in the pool carries. If the
change lands, those answers must be marked with which evidence path admitted
them, so a later reader can tell the two populations apart — and a round trained
on them is comparable to r6's 87 only in size, never in provenance.

## The pre-committed consequence

If prediction 1 holds and 3 holds, the supervised pool goes from 75 to the low
eighties and `LIMITS.md` reports both numbers with the evidence path named. If
prediction 1 fails, the 14 stay out, `t` needs a string type before they can come
back, and that is a WS-13.1 construct item with a measured 14-example price tag
rather than a guess.
