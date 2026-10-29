# Audit complete grading evidence before selecting weights

The current collector submits the registered measurements, and the selection core
assumes independently audited evidence. Connect them by checking the saved grader
outputs against the original generation files, exact frozen evaluator manifests,
complete panels, task tables and recomputed aggregate scores. Archive digests and
workflow identity are authenticated by the collector before this content audit.

The precision instrument records all kept candidates before its top-three
selection-gap ranking. The new selection guard incorrectly capped its denominator
at 95 times three. A synthetic 300-kept, 210-correct case exposes the mismatch;
the guard must instead require kept <= scored <= 95 times twenty. The precision
floor remains 0.70. No candidate measurement or release threshold changes.

Predictions before implementation and candidate results:

1. The six complete matched baseline parts reproduce their original full-panel
   readings and combine to 20/19/19 clean and 9/8/9 all-seven on the clean 206.
   Preserve the established removal of unconfirmed admissions before comparison.
2. The saved precision control reconstructs 93 kept, 73 reference-correct from
   its per-problem source lists and original scored candidates. Reference verdicts
   come from the authenticated frozen cloud instrument; no reference is rerun on
   the local machine.
3. The saved specification-33 control reproduces its preparation, task files,
   complete kernel table and 27 all-seven result using static preparation and
   score recomputation only. No model or proof invocation occurs.
4. Missing/duplicate/foreign answers or tasks, altered source identities, changed
   inputs, incomplete tables and inconsistent aggregates are refused. A complete
   zero-task run remains valid evidence of zero coverage.
5. The precision guard accepts a valid denominator above 285, refuses counts above
   the actual scored population or the registered sampling limit, and retains the
   exact 0.70 boundary.

The content auditor cannot establish artifact origin from files alone or certify
an unobserved model identity. Those bindings remain explicit prerequisites in the
collector and generation audit. No held-out launch or model choice follows from
a unit test or a baseline control. The full release protocol remains in force.

Sources: `v7_local_pair.py`, `v6_compare.py`, `grade_spec33.py`, `spec_ceiling.py`,
`spec_first.kept_specifications`, and the existing cloud-control receipts.

## Local content checks

The five precision-count regression cases failed before the guard repair and
passed afterward. The combined selection, content-audit and zero-task checks pass
67 cases without model, program-test, reference or prover execution.

The content reader reproduces all six previously authenticated baseline parts,
including the existing removal of unconfirmed problem 261 on the wider parts,
then the registered 20/19/19 and 9/8/9 counts on the 206. It also reconstructs
93 kept and 73 correct for precision, the 33 specification task files and 27
all-seven score, and the new cloud zero-task control's zero result. It excludes
only the historical empty `raw/.generate.lock` execution file from the original
baseline inputs. The first strict table scan mistakenly treated later summary
tables as task rows; a regression check now distinguishes the task table from
those summaries while rejecting duplicate task rows.

These replay the existing authenticated controls without repeating their model
or reference calls. The six fresh matched regrades under the zero-task repair
remain a separate pending requirement before the collector changes graders.
