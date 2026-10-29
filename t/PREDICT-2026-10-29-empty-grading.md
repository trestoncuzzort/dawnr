# Keep complete zero-task runs in the measured comparison

The frozen development grader rejects an empty task table because its coverage
guard requires a nonempty name set. Its later `score_levels.py --larger` command
also refuses an empty reference-verdict set. Both refusals reproduced without a
model, prover or reference call. A complete generation with no accepted task is
a zero-coverage observation and must not disappear from the multi-decode result.

Use the existing given-specification grader's treatment of all-failed answers as
the precedent. After the existing extraction/tests steps, a nonempty task set
continues through every original proof/reference command. A complete zero-task
set instead writes an empty seven-column table, empty verdicts and zero levels
through the existing scorer. Require exact generation, raw-answer and extraction
accounting first. Missing tasks or stale/incomplete evidence remain errors.
No answer can be admitted by this branch and no reference requirement is relaxed.

Before using the changed grader on candidate data, predict:

1. Synthetic complete zero-answer and unextractable-answer controls produce
   complete zero scores, and the existing full-panel reader accepts those scores.
2. Missing/foreign generation evidence and a claimed task missing its file are
   refused. Nonempty input leaves the existing grader path untouched.
3. A cloud zero-answer control succeeds with no admitted programs.
4. One fresh matched regrade of the same six saved baseline parts preserves its
   clean 20/19/19 and all-seven 9/8/9 counts on the 206. Preserve and investigate
   any changed cell; do not substitute a favorable retry.

The grader source is part of every receipt, including the new helper. The current
collector remains on its old frozen workflow until the cloud controls validate
the amendment and a new workflow/grader reference is registered. Model training,
generation inputs, release thresholds and held-out restrictions do not change.

Sources: `t/recipes/grade_spec33.py` and its all-failed-answer test;
`t/recipes/v6-grade.sh`, `t/score_levels.py`, and `t/recipes/v7_local_pair.py`.
