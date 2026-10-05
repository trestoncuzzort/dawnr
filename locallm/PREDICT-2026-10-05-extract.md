# `dawnr extract`: values that must be in the document, measured beside the schema-only way; registered before any measurement

Registered 2026-10-05 09:12Z. `locallm/extract_docs.py` is written and unit-tested, and has been run on one
hand-made invoice (eight fields, all right, the absent one left empty). It has been run on no benchmark question.
Plan row 4 of `internal/PLAN-2026-10-05-usable-for-everyone.md`; research receipt f949bfc4e047.

## What is measured

SQuAD 2.0's validation split (arXiv:1806.03822): 300 answerable and 300 unanswerable questions drawn with seed 2026
(`locallm/extract_eval.py sample`). The paragraph is the document; the question is the field's description. One
model for every arm: the base Qwen3.5-4B at 4 bits, as the installer puts it, temperature 0.

| arm | what holds the reply | 
|---|---|
| schema | a JSON Schema (`{"answer": string or null}`), the string free: what a schema-holding deployment does |
| located | the schema arm, an answer dropped when it is not in the paragraph word for word (LangExtract's rule) |
| span | `dawnr extract`: `NONE`, or a sentence's number and a run of that sentence's own words |
| twice | span asked again with the sentences listed in reverse; kept when both name the same sentence and one run contains the other |

Scored with SQuAD's own exact match and F1. A value shown for an unanswerable question is wrong.

## Predictions

- **X1, the build does what it says.** `span` and `twice` show no value that is not in the paragraph word for word
  (0 of all shown). `schema` shows at least 10 such values of its 600 replies.
- **X2, what is shown is more often right.** Of the values shown, the share that are exact: `span` is at least 5
  points above `schema`, and not more than 3 points below `located`.
- **X3, absent fields.** `span` leaves empty at least 40% of the 300 unanswerable questions. These were written to
  look answerable, so this is expected to be far below the 95% the same model reached when the documents were about
  something else (`PREDICT-2026-10-01-retrieval-on-the-base.md`).
- **X4, what it costs.** On the 300 answerable, `span` is exact on at least 55%, and within 8 points of `schema`.
- **X5, asking twice.** `twice` raises the share of shown values that are exact by at least 5 points over `span`
  and loses at most 10 points of exact answers on the answerable.

## What each outcome changes

- X1 fails for `span`: the grammar or the parser is wrong; fixed before anything else is read.
- X2 and X4 hold: `dawnr extract` is documented with these numbers beside it.
- X2 fails: holding the value to the source does not make it more often right than a schema does on this data; the
  README then claims only what X1 shows (every value has its sentence), with the measured precision stated.
- X3 fails (fewer than 40% left empty): the README says plainly that a field that is not in the document is often
  filled with something that is, and that the printed sentence is what the reader checks.
- X5 holds: `twice` becomes what `dawnr extract` does (two readings a field). X5 fails: it stays one reading.

## Not measured here

Typed fields (numbers, dates): SQuAD's answers are text. The typed grammar offers only runs that read as the type;
that is tested by unit tests and the invoice, not by a benchmark. Long documents cut by BM25: every SQuAD
paragraph is read whole.
