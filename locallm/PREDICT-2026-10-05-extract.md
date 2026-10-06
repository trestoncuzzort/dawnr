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

Run on the lab from commit 9278405e, one llama-server (build b11325) holding the base model at 4 bits, 600 questions,
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

## Outcome, 2026-10-05 11:22Z (X6 to X9)

Run on the lab from commit 852e0b99, its own llama-server (build b11325, the base model at 4 bits), 600 questions
none of which was in the first sample, five requests a question. `locallm/extract_eval.py report`:

| arm | shown, of 300 answerable | exact, of 300 answerable | left empty, of 300 unanswerable | shown in all | exact of shown | not in a sentence as shown |
|---|---|---|---|---|---|---|
| schema | 291 | 235 | 217 | 374 | 62.8% | 14 |
| located | 287 | 232 | 218 | 369 | 62.9% | 9 |
| span | 280 | 154 | 200 | 380 | 40.5% | 0 |
| twice | 258 | 150 | 220 | 338 | 44.4% | 0 |
| value | 282 | 223 | 152 | 430 | 51.9% | 0 |
| both | 270 | 217 | 180 | 390 | 55.6% | 0 |

- **X6: holds.** `value` and `both` show nothing that is not in a sentence as the command shows it.
- **X7: fails on its last clause.** `span` is 22.3 points below `schema` again (the bar was 10), and `both` is 15.1
  above `span` (the bar was 15), but `both` is 7.2 points **below** `schema`, where the prediction was not below.
- **X8: fails on absent fields.** `both` is exact on 217 of the 300 answerable (72.3%; the bar was 60%) and 6.0
  points from `schema` (the bar was within 10), but it leaves empty only 180 of the 300 unanswerable (60%; the bar
  was 75%).
- **X9: holds.** Going from `value` to `both`, 40 values stop being shown: 34 that were not exact and 6 that were.

**What went wrong, read from the same answers.** The rule did not fail; the prompt I rewrote for it did. `value`
is the same free reading as `located` with two changes made so that the server would read the document once (the
sentences numbered, the instruction moved after the field), and with those changes the model filled in 148 of the
300 absent fields where `located` filled in 82. The rule applied to the arms that kept their prompts, the `schema`
answer shown when it is, as words, in a sentence that holds the `span` reading's words, gives on these 600 fresh
questions 262 shown and 214 exact of the answerable, 238 of the 300 unanswerable left empty, and 66.0% exact of 324
shown (first sample: 256, 208, 242, 66.2% of 314). That is computed after the fact from two registered arms'
answers; it was not a registered arm, so it is a reason for the change below and not yet a result.

**What the registered rules say, and what is done.** X7 fails against `schema` and neither `value` nor `both` is
above it: as built at 852e0b99 the command's text reading is less often right than a schema's, and DISCLAIMERS says
so with these numbers until the next measurement is in. X9 holds: the second reading stays. The lesson is kept in
the code: the two prompts are now the measured arms' prompts word for word, and a test holds them equal.

## The command with the measured prompts, registered 2026-10-05 11:29Z before it is run on any question (X10 to X13)

`dawnr extract` reads a text field with `ask_value` (the `schema` arm's system prompt, its JSON Schema, the
sentences joined as the passage, what the field is as the question) and `ask` (the `span` arm's prompt and
grammar), and shows `held` of the two. Every free reading is asked before any grammar-held one, so the document is
read once for each kind. The eval's `value` and `both` arms call those functions.

**The sample.** 300 answerable and 300 unanswerable questions, seed 2028, none of them among the first 1,200.
Same model, server build and temperature.

- **X10, in the document.** `value` and `both` show nothing that is not in a sentence as shown (0).
- **X11, the rule on fresh questions.** Of the values shown, the share that are exact: `both` is not below
  `schema`, and at least 15 points above `span`.
- **X12, what it costs and what it withholds.** `both` is exact on at least 65% of the 300 answerable and within
  10 points of `schema`; it leaves empty at least 75% of the 300 unanswerable, and more of them than `schema` does.
- **X13, the command is the measured combination.** On at least 97% of the 600 questions `both` shows what the
  rule gives when applied after the fact to that sample's `schema` and `span` answers (the same value, or nothing
  in both). A larger gap means the command's passage (the sentences joined) or its use of the sentence's number
  differs from the arms in a way that matters, and is read by hand.

What each outcome changes:

- X10 fails: a fault; fixed first.
- X11 and X12 hold: README and DISCLAIMERS carry this sample's numbers for `both`, beside `schema`'s.
- X11 fails: three samples then say a text field is not more often right this way than under a schema; the
  second reading is kept only for the sentence it prints, the README says a schema is as often right, and the
  claim is the one X10 shows.
- X12 fails on absent fields: the README says how many absent fields were filled in, and that the printed
  sentence is what the reader checks.

## Outcome, 2026-10-05 11:55Z (X10 to X13)

Run on the lab from commit f00b92a1, its own llama-server (build b11325, the base model at 4 bits), 600 questions
none of which was in the first 1,200. `locallm/extract_eval.py report`:

| arm | shown, of 300 answerable | exact, of 300 answerable | left empty, of 300 unanswerable | shown in all | exact of shown | not in a sentence as shown |
|---|---|---|---|---|---|---|
| schema | 293 | 244 | 215 | 378 | 64.5% | 9 |
| located | 290 | 242 | 216 | 374 | 64.7% | 5 |
| span | 289 | 157 | 189 | 400 | 39.2% | 0 |
| twice | 272 | 159 | 218 | 354 | 44.9% | 0 |
| value | 287 | 237 | 217 | 370 | 64.0% | 0 |
| both | 270 | 224 | 230 | 340 | 65.9% | 0 |

- **X10: holds.** `value` and `both` show nothing that is not in a sentence as shown.
- **X11: holds.** `both` is 1.4 points above `schema` (the bar was not below) and 26.7 above `span` (the bar was 15).
- **X12: holds.** `both` is exact on 224 of the 300 answerable (74.7%; the bar was 65%), 6.6 points from `schema`
  (the bar was within 10), and leaves empty 230 of the 300 unanswerable (76.7%; the bar was 75%), 15 more than
  `schema` does.
- **X13: holds.** On 597 of the 600 questions (99.5%; the bar was 97%) `both` shows exactly what the rule gives
  when applied afterwards to this sample's `schema` and `span` answers, computed with the registering commit's code.

**What `dawnr extract` is measured to do for a text field, then.** Against the same model filling a JSON schema,
on questions neither had seen: about as often exactly right when it shows a value (65.9% against 64.5%), silent on
77% of the fields the document does not hold where the schema is silent on 72%, at the cost of 20 exact answers in
300 that it withholds, and with nothing shown that is not in the document as words where the schema showed 9
such values. The same rule over the same two prompts read 66.2% and 66.0% on the first two samples, after the
fact. The second reading withholds 30 values the first would have shown, 17 not exact and 13 exact.

**What three rounds in one day were for.** Each of the two builds that failed had been tried by hand on an
invoice and looked right. Held to a run of the sentence's words the model quotes too much (X2); given a prompt I
rearranged for speed it filled in fields that were not there (X7, X8). The form that held is the one whose two
halves had each already been measured, and it is now pinned to them by a test. Typed fields (numbers, dates) are
still not measured by any of this.

