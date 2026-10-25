# Keep certificate negation through Frama-C normalization

The dawnr fixed-answer control found a Frama-C false refusal: its printer turns a negated inequality into an
equality, and the adapter's negation guard then rejects the certificate despite the kernel accepting its proof.
Three diagnostic repetitions reproduced the explicit guard reason. The original control remains recorded;
this repair does not substitute favorable diagnostic results into it.

The existing negative controls are in `test_framac_adapter_controls.py` and `test_verifiers_framac_review.py`.
Keep the adapter unchanged. Encode a certificate's original predicate using a fresh ACSL local binding inside
the negation. By the documented local-binding semantics, `!(\let p = P; p)` means `!P`; it adds no assumption,
axiom, or changed invariant. A printer-only probe on Frama-C 33.0 retains the outer negation for this form.
The binding name must avoid existing identifiers. Apply the same encoding to value, undefined-expression,
loop-exit and termination-measure certificates.

Sources: [ACSL local bindings, section 2.2](https://frama-c.com/download/acsl-implementation-20.0-Calcium.pdf),
`lower_framac.py`'s four certificate builders, and the
[fixed-source diagnosis](https://github.com/trestoncuzzort/dawnr/blob/main/release/evidence/spec33-framac-diagnostic-2026-10-25.json).

Before the repaired kernel runs, predict:

1. A fresh scalar nonzero example with a broken zero-return branch reads verified/refuted with three agreeing
   repetitions per side. Its printed certificate passes the unchanged negation guard. Any refusal or
   disagreement falsifies this prediction.
2. The existing negative certificate, vacuity and inconsistent-definition controls remain rejected. An accepted
   negative control falsifies the repair and stops promotion.
3. Re-run the entire registered `t/tasks` Frama-C column on the same pinned binaries and unchanged budgets,
   once at the base revision and once with the repair. No previously agreeing cell becomes non-agreeing.
   Any such change falsifies this prediction and must be examined by name before landing.
4. The existing four-task, seven-kernel container control remains 28 agreeing cells. Any loss falsifies it.

The full column and native proof tests run on GitHub. Local checks cover syntax, name hygiene and printer
behavior only. Results, including failures, will be appended here. No dawnr grading pin changes until the
engine repair is validated; changed evaluator code will need a fresh matched dawnr baseline and control.

## Result, 2026-10-25

All four predictions held in [container run 40146610056](https://github.com/trestoncuzzort/t-language/actions/runs/40146610056),
at repair revision `2cd6a8c43eb062b84d06d10d57251a6068bf8a82` against base
`5828ed07aaba864a4dc4ae06ab20a4a01a5d686b`.

1. The fresh nonzero example is verified/refuted with three agreeing repetitions per side; its kernel-printed
   certificate passes the unchanged negation guard. All four binding tests ran and passed.
2. All seven existing adapter-control tests ran and passed, including the three native negative probes for an
   unrelated certificate, a vacuous precondition and an inconsistent definition. No test was skipped.
3. Both full columns cover exactly the same 114 task names, matching every registered task file. Every cell is
   unchanged: 71 verified/refuted, 42 abstain/abstain and one timeout/refuted (`double_all`). There are zero
   agreement gains and zero losses in this column; the new regression supplies the positive repair evidence.
4. The four-task control (`abs`, `gcd`, `reverse`, `swap_at`) remains 28 verified/refuted cells across all seven
   kernels, with three repetitions per side.

The artifact digest, complete column tables, native-control log and four-task table are retained in
[`t/evidence/2026-10-25-framac-certificate-binding`](evidence/2026-10-25-framac-certificate-binding/receipt.json).
The adapter file is byte-identical to the base. The Ubuntu/macOS Python 3.10/3.12 unit matrix also passed in
[run 40146638952](https://github.com/trestoncuzzort/t-language/actions/runs/40146638952).
This is a lowering repair with its existing-column behavior preserved. It changes neither the installed
`AGREEMENT.md` nor README counts; downstream model results still require matched controls with this evaluator.
