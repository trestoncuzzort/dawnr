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

## Read of the v1 pilot (2026-10-12 14:37Z, this laptop, Dafny only)

80 calls (62 before the Sonnet-priced ledger tripped the $2 cap, 18 resumed at DeepSeek's listed rate),
466,956 input and 95,511 output tokens, **$0.42** at $0.56/$1.68 per million. Every reply carried both fences.

- **P1 failed.** 19 of 80 parse (`report.json`: judge pass 5, fail 1, ill-formed 10, error 2, timeout 1, not run 61). The parser's own words, by count: `expected '=', found '{'` 10 (a spec
  fun given a braced body), `'var' does not start an expression` 6, `expected 'id', found 't'` 5 (`t` is
  reserved), `expected 'decreases', found 'requires'` 5 (a spec fun given a contract), `';' does not start an
  expression` 4. The teacher writes spec funs as Dafny functions. Of the parsed, 10 are refused by the
  well-formedness gate (calls to helpers never declared: `pow10`, `seq_to_int`, `popcount_hex_digit`; a
  spec fun whose body type differs from its result).
- **P2 failed.** 5 samples reproduce every stored output; 3 of them count in Dafny, on **2 problems of 20**:
  10055 (`|a - b|`, t 0) and 10079 (`n(n+1)/2 + 1`). The other two judge-passers are Dafny refusals: 10019 s1
  "the solver gave up" (a loop over hex digits with `/ 16`), 10025 s1 "real is refuted" (the judge's cases
  agree with the body but the ensures is wrong: the judge tests the spec, as judge.py says).
- **P3 held.** Every non-accepted sample carries the parser's message, the gate's refusal, the judge's first
  differing line (10050 s3), or the named runtime error (10079 s1 recursion depth, s4 an empty int literal
  from the io module); no accepted row has a verdict other than COUNTS.
- **P4 held.** $0.42 against $1.

What it bought: the failure is almost entirely syntax the reference text does not forbid explicitly, which a
prompt can state in a few lines; the oracle did its job on everything that got through it.

## v2 registered (2026-10-12 14:40Z, before the first call)

Same 20 problems, k = 4, temperature 0.7, the same teacher and transport; prompt v2 = v1 plus `PARSER_RULES_V2`
in `t/udebug_teacher.py`, written from the five parser messages and the gate refusals above (a spec fun is one
expression, no braces/var/;/requires on it; `t` is reserved; no let-in, comments or literals; every called
helper declared above as a spec fun; keep it small). Ledger at the listed rate, cap $2.

- **P1':** at least 48 of 80 parse. *Falsifier:* fewer ⇒ the rules do not reach the model and the next lever is
  a repair pass (parse error back to the teacher), not more prose.
- **P2':** at least 4 of 20 problems accepted (judge pass AND Dafny COUNTS). *Falsifier:* fewer than 4.
- **P3':** every refusal named, as in v1. **P4':** at most $0.60.

## v2 read and the repair pass, registered (2026-10-12 15:15Z, before the first repair call)

**v2 read (DeepSeek-V3.2, prompt v2, 80 calls, $0.43).** The rules in prose did not reach the parser: the same
messages lead (`expected '=', found '{'` 9, `'var' does not start an expression` 5, `expected '{', found 'n'` 4,
`let ... in` and `seq<seq>` now appear as well), about 12 of 80 parse, and the gate was OOM-killed once
(10049's `f(k - f(k-1)) + 1` and 10025's search; now every judge and verify runs in a 3 GB scope) and the
three survivors ran to the judge timeout. Accepted: **3 problems of 20** (10019, 10055, 10079; 5 samples
counted in Dafny). P1' failed, P2' failed by one, P3' and P4' held. Exact counts land in that run's
`report.json` when its last timeout ends.

**Repair pass registered.** `t/udebug_repair.py`, round 1, on the v1 samples (the fully graded run): every
sample the parser or the gate refused gets its refusal back as a user turn in its own conversation
(Self-Debugging, arXiv:2304.05128, receipt `udebug-repair-pass`), temperature 0.3, one round, DeepSeek-V3.2
on Vertex, cap $2. The repairs are graded by the same gate and deduplicated by printed text.

- **R1, the message reaches the model:** at least half of the repaired samples parse (v1 had 61 parse
  refusals + 10 gate refusals). *Falsifier:* fewer than half ⇒ the model cannot write t from a message
  either, and the next lever is a deterministic rewrite of the recurring shapes or a different teacher.
- **R2, yield:** the accepted problem count of v1 rises from 2 to at least 4 of 20 after the repairs are
  graded. *Falsifier:* fewer than 4 ⇒ parse repair buys parsing, not judge-and-proof acceptance, the
  September finding again.
- **R3:** every refusal still named; **R4:** at most $0.60 for the round.

### Read of the repair round and of a second teacher (2026-10-12 15:32Z)

- **Repair round 1 on v1 (71 calls, 71 replies with a t fence, $0.44).** **R1 failed:** 16 of 71 repairs parse
  (55 still refused by the parser; of the 16, 9 are gate-refused, 4 pass the judge, 2 time out, 1 fails).
  **R2 failed:** the accepted problem count stays at 2 (the one new acceptance, 10055, was already accepted).
  R3 and R4 held. So the model cannot write t from the parser's message either: the exact line and expected
  token do not change what it writes next.
- **Qwen3-235B-A22B-Instruct-2507 (Apache-2.0) on prompt v2, same 20 problems (80 calls, $0.20, 66 replies
  with both fences).** 20 of 80 parse, 4 pass the judge, and **0 count in Dafny**: 0 problems accepted.
  Cheaper and faster (5-9 s a call), worse on proof.
- **v2 final:** 16 of 80 parse, 5 judge passes, 4 counted in Dafny, **3 problems of 20** (10019, 10055,
  10079), 8 rows and 2 judge-pairs.

What the three runs say together: a frontier model that has never seen t writes Dafny-shaped code by reflex
(braced function bodies, `requires` on functions, `let ... in`, `seq<seq>`, `forall ... ::`), prose rules and
parser messages do not move it, and the problems that get through are the one-line ones. The two levers the
falsifiers name: (1) let the teacher write Dafny, which it does write, and lift it to t with the repository's
own lifter (the MBPP-DFY lift of `t/COVERAGE-lifted-785.md`); (2) choose problems by shape, since bank order
(10018..10092) put a segment-cover and a Hofstadter recursion in front of a model that proves one-liners.
Both are registered below before they run.

## Selection by shape, registered (2026-10-12 15:33Z, before the first call; label corrected from an estimated 15:40Z to the unit's start time)

Same teacher, prompt and k as v2 (DeepSeek-V3.2, prompt v2, k = 4, T = 0.7), but the 20 problems are the top 20
of the UVa int-shaped train set by a statement score (`+1` per number-theory word such as prime, divisor,
digit, sum, gcd; `-2` per string/grid/graph/geometry word; minus length/1500), the list in
`t/out/udebug/math-shaped-top20.txt` (Smith Numbers, Composite Prime, Largest Prime Divisor, GCD LCM, ...).
The 21 hand-solved problems score -0.8 to 15.5 on it, the bank-order pilot -23 to 38 (median ~7); these
twenty score 20 to 38. Tag `deepseek-udebug-3`.

- **S1:** at least 5 of 20 problems accepted (judge pass AND Dafny COUNTS), against 3 of 20 in bank order.
  *Falsifier:* 4 or fewer ⇒ shape selection does not beat the syntax wall; the Dafny-lift path is the lever.
- **S2:** the parse rate stays within 10 points of v2's 20% (the score selects problems, not syntax).
  *Falsifier:* a parse rate above 30% would mean these statements elicit simpler programs, worth knowing.
- **S3:** refusals named; **S4:** at most $0.60.

## Dafny as the teacher's language, registered (2026-10-12 15:36Z, before the first call; label corrected from an estimated 15:55Z to the unit's start time)

The teacher writes a Dafny method `p<id>` (functions, lemmas, `requires`/`ensures`, the int/bool/seq<int>
subset) plus the io module; the gate lifts it to t with `t/lifter.py` (resolve, parse, classify, rewrite,
check; every refusal named; measured on the hand Fibonacci: lifted and checked in 2.4 s), then judges and
verifies the lifted task exactly as before. Exemplars are the engine's own Dafny lowerings of p495, p10302
and p343 (`cli.py lower --kernel dafny`). Same 20 bank-order problems as v1/v2, DeepSeek-V3.2, k = 4,
T = 0.7, concurrency 2 (the endpoint is throttling), tag `deepseek-udebug-dafny-1`.

- **D1, the model can write the language it is asked for:** at least 48 of 80 replies lift to a t task
  (resolve + parse + classify + rewrite pass; the lifter's check may still refuse). *Falsifier:* fewer than
  48 ⇒ the lifter's subset, not the language, is the wall, and its refusal reasons say which construct.
- **D2, yield:** at least 5 of 20 problems accepted (judge pass AND Dafny COUNTS on the lifted task), against
  3 of 20 for the same problems written in t. *Falsifier:* 4 or fewer.
- **D3:** every refusal named (lifter stage and reason, judge line, kernel verdict). **D4:** at most $0.50.

### Read of the shape selection (2026-10-12 15:50Z)

80 calls, every reply with both fences. **S1 failed:** 9 of 80 parse, 5 of those gate-refused, 3 runtime
errors, 1 judge timeout, **0 problems accepted** (Smith Numbers, Composite Prime, Largest Prime Divisor, GCD
LCM, ... all refused at the parser). **S2 held in the letter** (11% is within 10 points of 20%) and says the
opposite of the hope: harder statements draw longer programs with more of the constructs the parser refuses.
S3 and S4 held. Shape selection does not beat the syntax wall; the Dafny-lift run decides the next step.

### Read of the Dafny-target run (2026-10-12 16:03Z)

80 calls, 80 replies with both fences, $0.29 (the Dafny prompt is 2.8k tokens against 5.7k). **D1 failed:** 10
of 80 lift. The lifter's refusals by stage: Dafny's own parser 34 (C-style `? :`, a statement `if` inside a
function, a stray `{`), Dafny's resolver 11 (`abs` undefined, int compared with bool, a loop without
`decreases`), the lifter's check 13 (the lifted task does not verify: `L_fun_rev`, `L_fun_is_palindrome`,
`L_fun_countOnes`), the classifier 12 (unbounded quantifiers 5, mutual recursion, seq of pairs, nested
returns). **D2 failed:** 3 problems accepted (10019, 10055, 10079), the same three as in t. D3, D4 held.

What it bought: the refusals moved from a language the model cannot write to a language it can, and 45 of
the 70 are ordinary Dafny syntax and type errors with a line and a message, the Self-Debugging setting
proper. The repair pass now carries lift refusals back (Dafny's message, the lifter's stage and reason).

## Scale run and Dafny repair, registered (2026-10-12 16:03Z, before the first call)

- **Scale (tag `deepseek-udebug-dafny-scale`):** every UVa int-shaped train problem with a statement and
  stored inputs under 200 kB (662 by the bank), Dafny target with the contract extended by the measured
  mistakes above, k = 2, T = 0.7, concurrency 3, cap $8 at the listed rate. Graded on this laptop with
  Dafny as it runs; the seven-kernel pass waits for the lab.
- **Dafny repair, round 1 on `deepseek-udebug-dafny-1` (70 refused):** one round, T = 0.3, cap $1.

Predictions:
- **E1 (repair):** at least 25 of the 70 repairs lift (against 10 of 80 first-pass). *Falsifier:* fewer.
- **E2 (repair):** at least one new problem accepted beyond 10019/10055/10079. *Falsifier:* none.
- **E3 (scale):** accepted problems between 5% and 20% of 662, i.e. 33 to 132, read when the run and its
  grading finish; below 33 ⇒ the pilot's three were the easy end of the sample; above 132 reported as such.
- **E4:** refusals named at every stage; **E5:** scale run at most $8, repair at most $1.
