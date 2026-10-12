# Judge problems at scale: a teacher writes t tasks for uDebug's stored cases (registered 2026-10-12)

## What changed

`t/PREDICT-2026-10-08-math.md` proved and judge-checked 25 UVa problems by hand against a small uDebug
export. The export is now a research corpus collected with the judge's permission (private, not committed):
**13,531 problems** of the 14,243-entry catalog finished the input/output pass; **7,682** carry at least one
stored case (18,924 input files, 18,854 with a stored output); **3,407 UVa problems** carry both stored cases
and the publisher's statement text. `t/udebug_bank.py` joins them into one record per problem
(`t/out/udebug/bank.jsonl`, 7,682 records, built in 8.6 s): statement, case counts, the smallest stored case
as a sample, an `io_shape` flag (`int` when every token of every stored input and output is an integer: the
shape of all 25 hand solutions; 2,279 problems, 972 of them UVa), the 21 hand-solved problems present in the
corpus marked `measured`, and a 10% hash held-out split (seed 1338; 804 problems).

Two scripts turn the bank into the setting of ReST-EM (Singh et al., arXiv:2312.06585, read 2026-10-12: sample
K per problem, keep what a binary oracle accepts, fine-tune once from the base model; the paper's own warning
is that on APPS "most of the gains come from the first iteration" and a second iteration regressed through
"overfitting on the small set of training problems", so rows are capped per problem and the held-out and
measured sets are never trained on):

- `t/udebug_teacher.py`: DeepSeek-V3.2 on Bedrock (MIT; `t/bedrock_generate.py`'s transport, backoff,
  ledger and spend cap) answers a problem with a t task `p<id>` plus an io module, prompted with prompt v5's
  reference text and few-shots, the io contract from `t/judge.py`, and three hand exemplars read at run time
  (p495, p10302, p343: one int per case, a lemma, two sequences in and a sequence out).
- `t/udebug_gate.py`: the judge first (`t/judge.py` on every stored case; a FAIL is an execution refutation,
  cheaper than a proof), the provers second (`cli.py verify --json`; a kernel counts only on `COUNTS`, real
  verified and twin refuted), then rows: `statement-given` (statement and sample to the full task),
  `spec-given` (`t/student_rows.row_for`), and `judge-pair` (an accepted task against a same-problem sample
  the judge refuted at a stored case).

**Self-test before any model call (2026-10-12, this laptop, Dafny only).** The 21 hand solutions whose cases
are in the corpus reproduce every stored output (`t/out/udebug/judge-regress.log`: 21 of 21; p495's sixth file
is uDebug's placeholder and is skipped by name; 369, 496, 575, 991 are in the corpus's uncollected tail).
Three hand solutions staged as samples beside a twin with a broken `render`: 3 judge-pass + Dafny COUNTS,
3 judge-fail with the first differing line recorded, 0 rows because all three are `measured` (refused by
name, `rows_skipped.hand-solved: 3`); with the mark lifted, 6 rows and 3 pairs.

## The pilot run (registered before the first call)

- Teacher DeepSeek-V3.2 (MIT), temperature 0.7, k = 4, 4,096-token budget, concurrency 4. Registered on Bedrock
  (`deepseek.v3.2`, us-east-1); run on Vertex AI instead (`deepseek-ai/deepseek-v3.2-maas`, location `global`,
  `--provider vertex`) because the AWS session had expired and the operator chose Google Cloud at 13:5xZ; the same
  weights behind a different API, and the record names provider, endpoint and model. Launched 2026-10-12 14:11:24Z.
- Problems: the first 20 bank records with `judge = UVa`, `io_shape = int`, `split = train`, not hand-solved,
  stored inputs under 200 kB, in bank order (`--limit 20 --max-in-bytes 200000`).
- Gate on this laptop: Dafny only (`--kernels dafny`), `--min-kernels 1`, cap 4 rows per problem.
- Spend cap $2 by the ledger at Sonnet list prices (an overestimate for DeepSeek).

## Predictions, with what falsifies each

- **P1, the reply is parseable:** at least 60 of the 80 replies carry both fences and the t block parses.
  *Falsifier:* fewer than 60 ⇒ the prompt, not the problems, is the first thing to fix.
- **P2, yield:** at least 4 of the 20 problems have an accepted sample (judge pass on every stored case AND
  Dafny COUNTS). The hand rate was 25 of 25 by a person; the teacher's validation round on English problems
  was 3 of 10 clean in seven kernels; judge problems add an unverified io format the teacher must match
  exactly, so the bar sits at 20%. *Falsifier:* fewer than 4 ⇒ reported as the yield, and the first
  differing lines say whether the io glue or the task is what fails.
- **P3, the gate is honest:** every judge FAIL in the report carries the first differing line or a named
  error; no sample is accepted with a kernel verdict other than COUNTS. *Falsifier:* one accepted row whose
  verdict message is not COUNTS, or one FAIL without a recorded reason.
- **P4, cost:** at most $1 by the ledger. *Falsifier:* the cap trips.

## Read

(filled in after the run, from `t/out/udebug/teacher-deepseek-udebug-1/report.json`)
