# Frama-C adapter controls

Before this repair, the four container controls have zero all-seven passes:
Frama-C rejects all four while the other six kernels accept their real/twin
pairs. Direct measurements identify three adapter errors introduced by the
October 13 review: the kernel prints negation as `¬`; statement smoke classes
end in `_s8` and similar suffixes; and a termination lemma's quantifier contains
a semicolon while its conclusion compares measures rather than calling the
recursive function. The original C source and kernel-normalized text were
read before this change, together with `lower_framac.spec_fun_acsl` and the
adapter's consistency-probe and per-goal-audit machinery.

Prediction: abs, gcd, reverse and swap_at each return verified/refuted in all
seven kernels, with three repetitions per side. Negative controls must still
reject an unrelated certificate assertion, a vacuous precondition hidden by
a function name, an inconsistent recursive definition, and a tautological
termination marker. No specification, solver budget, or invariant is changed.

The termination-name check remains a structural backstop, as documented in
the adapter. Recognizing the lowering's bounded-decrease shape is not a proof
that arbitrary ACSL lemmas describe the corresponding recursion. The kernel
must discharge every emitted goal and the existing consistency probes remain.

Sources: the measured Frama-C 33.0 `-print` output, its WP JSON report, and
https://www.frama-c.com/download/frama-c-wp-manual.pdf.

Measured: the [four-task matrix](evidence/2026-10-18-framac-controls/positive.md)
now passes all 28 cells, with 168 actual kernel calls and no cache. The
[native negative and syntax controls](evidence/2026-10-18-framac-controls/negative.txt)
pass all seven checks. The four previous review tests also pass. These are
instrument controls; they say nothing yet about a new model's performance.
