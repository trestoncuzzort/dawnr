# Lifter design, raw workflow output (unaudited)

These five files are the untouched output of the design workflow
`wf_75f9712b-7db` (2026-09-05, session a9f0da81): four independent designs for
the Dafny-to-t lifter (ROADMAP 12.4) and the aggregated corpus inventory they
were written from. The workflow's judge, synthesis and critique phases never
ran (five-hour rate cap); the reconciliation was done by hand in
`t/LIFTER-DECISIONS.md`, and `t/LIFTER-DESIGN.md` is `verified-lift.md` with a
provenance header and a grafts section.

They are kept for provenance, not as normative documents. Where they disagree
with LIFTER-DECISIONS.md, the decisions file wins. Where a number here is a
prediction (each design's "expected lift of the 77"), the measurement in
`t/out/lift/` replaces it.

| file | what |
|---|---|
| `verified-lift.md` | base of LIFTER-DESIGN.md: rprint front end, six flat modules, Dafny-verified equivalence lemmas as the lift check |
| `dafny-print-normalised.md` | most conservative defaults, 65 mapping rules, LIFT RECORD vocabulary, census-join verdict classes |
| `recursive-descent.md` | parses source and rprint both, body oracle by `dafny run`, 8 of the 77 hand-lifted end to end |
| `two-stage-generic.md` | most instruments: exit-code discipline, two-arm differential, checker mutation test, decreases probe ladder |
| `inventory.md` | 126-program inventory (77 in fragment, 49 refusal samples) the designers and this file's readers worked from |

The full scratch of the run, including per-file inventories, census.json, the
hand-lift seeds and every experiment the designs cite, is banked outside the
repo at `~/tup/t-corpora/lifter-design-2026-09-05/`.
