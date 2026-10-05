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

## Outcome, 2026-10-05 10:44Z (X1 to X5)

Run on the lab from commit 35c2b88e, one llama-server (build b11325) holding the base model at 4 bits, 600 questions,
three requests a question. `locallm/extract_eval.py report`:

| arm | shown, of 300 answerable | exact, of 300 answerable | F1 of those shown | left empty, of 300 unanswerable | shown in all | exact of shown | not in the paragraph word for word |
|---|---|---|---|---|---|---|---|
| schema | 284 | 227 | 0.907 | 223 | 361 | 62.9% | 10 |
| located | 278 | 225 | 0.912 | 227 | 351 | 64.1% | 0 |
| span | 283 | 165 | 0.741 | 197 | 386 | 42.8% | 2 |
| twice | 256 | 165 | 0.784 | 220 | 336 | 49.1% | 2 |

- **X1: holds for `schema` (10, the bar was 10); reads 2 for `span` and `twice`, and both are the scorer's.** The
  two values are `CO 2` and `O 2`. The command shows a sentence with its whitespace collapsed (`CO 2`), and the
  value is a run of that sentence; the paragraph as SQuAD stores it has two spaces there, and the report compared
  with the stored paragraph. Against the sentences as they are shown, 0. The report now prints both counts.
- **X2: fails, and by a wide margin.** `span` is 20.1 points below `schema` (the prediction was 5 above) and 21.3
  below `located` (the prediction was within 3).
- **X3: holds.** `span` leaves empty 197 of the 300 unanswerable (65.7%; the bar was 40%). `schema` leaves 223.
- **X4: half holds.** `span` is exact on 165 of 300 (55.0%; the bar was 55%), and 20.7 points below `schema` (the
  bar was within 8).
- **X5: holds.** `twice` raises the share of shown values that are exact by 6.3 points and loses none of the 165.

**Why `span` loses.** It finds the place as often as `schema` does (283 shown against 284) and then quotes too
much of it: of its 118 answers on answerable questions that are not exact, 90 contain a gold answer. The grammar
lets a run stop at any word, and the model's habit under it is to carry on to the end of the sentence; written
freely under a schema it gives the two words. Holding the value to the source did what it was built to do (nothing
shown is outside the document) and made the value worse.

**What the registered rules say, and what is done.** X2 fails: the README claims only what X1 shows, every value
has its sentence, with the measured precision stated. X5 holds, but its rule ("`twice` becomes what the command
does") was written on the expectation that `span` was the better reader, and `twice` is still 13.8 points below
`schema`; taking it would ship the worse of two measured methods, so it is not taken.

## What the command does now, registered 2026-10-05 11:00Z before it is run on any benchmark question (X6 to X9)

Looking at the 600 answers again, without asking the model anything, three rules that use both kinds of reading
were compared. These are counts from answers already in hand, and the rule below was chosen from them, so none of
this is a result:

| rule, on the first sample's answers | shown, of 300 answerable | exact | left empty, of 300 unanswerable | exact of shown |
|---|---|---|---|---|
| the schema answer when it is inside the sentence `span` names | 256 | 208 | 242 | 66.2% |
| the schema answer when it shares words with `span`'s run | 253 | 206 | 247 | 67.3% |
| `located`, unless `span` says NONE | 270 | 218 | 236 | 65.3% |

The first is the one built (`extract_docs.held`), because it can be said in a line and each half does one job: the
free reading gives the words, the grammar-held reading gives the sentence, and a value is shown only when its
words are in the document as words (`stated_in`: `12` is not in `2012`) and inside that sentence. Two things differ
from what the table counted, so the table cannot stand in for a measurement: the command's free reading is given
the numbered sentences with the instruction last (so that the server reads the document once for both readings and
every field), where the `schema` arm was given the bare paragraph; and the grammar-held reading's prompt is
rearranged the same way. A typed field (number, date) is unchanged.

**The sample.** 300 answerable and 300 unanswerable questions of the same split, seed 2027, none of them among the
first 600 (`--seed 2027 --skip` the first run's answers). Same model, same server build, temperature 0. The four
arms above are run again as they were (the first method's prompt is kept in `extract_eval.SPAN_SYSTEM`), and two
are added: `value`, the command's free reading kept when its words are in a sentence as words; `both`, `held` over
the two readings, which is what `dawnr extract` shows.

- **X6, in the document.** `value` and `both` show no value that is not in a sentence as the command shows it (0).
- **X7, the first sample's finding repeats and the new rule escapes it.** Of the values shown, the share that are
  exact: `span` is at least 10 points below `schema` again; `both` is at least 15 points above `span` and not
  below `schema`.
- **X8, what it costs.** On the 300 answerable, `both` is exact on at least 60% and within 10 points of `schema`.
  It leaves empty at least 75% of the 300 unanswerable.
- **X9, whether the second reading earns its request.** Going from `value` to `both`, more of the values that stop
  being shown are not exact than are exact (on the first sample's answers the nearest comparison, `located` to the
  first rule in the table, withheld 20 that were not exact and 17 that were).

What each outcome changes:

- X6 fails: a fault in `held` or in the report; fixed before anything else is read.
- X7 and X8 hold: the README and DISCLAIMERS carry this sample's numbers for `both`, beside `schema`'s.
- X7 fails against `schema`: the command's text fields go to whichever of `value` and `both` is not below
  `schema`; if neither, the README says a schema is as often right and the command's claim is the sentence shown.
- X9 fails: the second reading is dropped for text fields (`value` alone, one request a field, the sentence shown
  is the first that holds the words) and the documents say that.
- `value` against `located` shows what numbering the sentences and moving the instruction changed; no prediction,
  both are reported.

