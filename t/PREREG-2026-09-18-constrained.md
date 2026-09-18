# Preregistration: does decoding against t's grammar produce more clean answers?

Written 2026-09-18, before any constrained answer was generated. The grammar, the arms, the metrics and the
decision rule below are fixed now. WS-21 in [`ROADMAP.md`](../ROADMAP.md) is the measurement this opens.

## The claim under test

[`t/FUNNEL-2026-09-18.md`](FUNNEL-2026-09-18.md) measured that 62 percent of a prompted stock model's replies
never reach a proof system, because they do not parse as t. A generator can be made unable to emit them: the
lab workstation's vLLM accepts a grammar per request and constrains decoding to it.

The tempting claim is that this recovers the 62 percent. It may not, and the same document says why: locallm
writes t the parser accepts 98 percent of the time and passes the problems' own tests in 2 of 464 answers. A
constrained stock model could be locallm with a bigger vocabulary -- syntactically perfect, semantically empty.

So the number that decides this is **clean answers**, not parse rate. Parse rate is guaranteed by construction
and measuring it would prove only that the constraint was applied.

## Before the arms may run

The grammar must be the same language the parser accepts. Two mechanical checks, both of which must pass, and
the experiment is void if either is skipped:

1. Every task committed in `t/tasks/` and every answer in `t/out/spec-experiment/*/tasks/` -- every program the
   parser has ever accepted -- is accepted by the grammar.
2. A sample of at least 500 replies the parser refused (`extract.json`, stage `parse`) is refused by the
   grammar as well. A grammar looser than the parser would move answers from "unparseable" to "unparseable
   later", which is not the thing being tested.

## The arms

Both arms answer **the same 1,133 problems** (`t/out/loop/apps-upper.txt`), with the same model
(`Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8`), the same prompt (`build_prompt` v3), temperature 0, seed 1 and 2,048
predicted tokens. Nothing differs but the constraint.

| arm | tag | generation |
|---|---|---|
| control | `qwen3-coder-30b-apps-s1` | already generated, unconstrained |
| constrained | `qwen3-coder-30b-apps-g1` | the same request with `structured_outputs.grammar` |

Both are extracted, tested, filtered by `pool_pick.py --control 40` and graded by the same seven checkers at the
same 32 cells. The control arm's grading is already running and its numbers are not read before the constrained
arm is generated.

## What is reported, per arm

1. Replies that parse, are well formed, and pass the problem's own tests.
2. **Clean answers**: tests pass, all seven verify, all seven refute the twin. The primary outcome.
3. Distinct problems with at least one clean answer.
4. Test-pass rate **among answers that parse**. This separates "the model wrote good programs in the wrong
   notation" from "the model wrote bad programs", and it is the one number that says whether the semantics were
   ever the limit.
5. Generation seconds per clean answer, so the cost of the constraint is beside its yield.

## The decision rule, fixed now

- **Adopt** if the constrained arm produces at least **1.5 times** the clean answers of the control. Constrained
  decoding becomes the default for every later generation run, and the README says the parse wall was the limit.
- **Reject** if the constrained arm produces **fewer** clean answers than the control. The constraint is then
  buying syntax at the cost of sense, which is locallm's failure at a larger scale, and it is reported as such.
- **Inconclusive, and the more informative outcome**, if the two are within 1.5x of each other in either
  direction: the parse wall is real but the gates below it absorb whatever passes, and the project's limit is
  semantic. The pool then has to teach proof rather than notation, and WS-21 move 3 becomes the work.

Whatever the outcome, metric 4 is reported next to it, because it is the measurement that tells the three
outcomes apart rather than merely ranking them.

## What would make this experiment worthless

- Reading the control arm's clean count before generating the constrained arm and then adjusting the grammar.
- A grammar that accepts more than the parser (check 2 above).
- Grading the two arms at different job counts: SPARK's wall-clock backstop fires under load, and a timeout is
  not a verdict ([`t/preflight.py`](preflight.py) refuses a clean answer that rests on one).

## Amendment, 2026-09-18, written before any constrained answer was graded

Constrained decoding is 35 times slower per answer on this server, measured
rather than estimated: 0.9 s unconstrained, 32 s with the grammar's identifier
rules replaced by one loose rule, 37 s with the grammar as written. The cost is
the grammar itself, not its size -- the generated keyword trie accounts for 14
percent of it. Concurrency does not recover it (16 jobs and 32 jobs both give
about 40 to 55 answers an hour, and the four cards sit at zero percent while it
runs), because the per-token mask is computed on the engine's own path.

The full 1,133-problem arm is therefore about a day of four shared GPUs that
are lent to this project, not owned by it. Two things change, and both are
fixed here before any constrained answer has been extracted, tested or graded:

1. **The sample is a prefix.** The arm answers the same 1,133 problems in task
   id order and may be stopped whenever the cards are wanted back. The
   comparison is made over the ids *both* arms answered, so any stopping point
   is a matched sample and none of it is chosen after seeing an outcome.

2. **The primary outcome moves from clean answers to answers that pass their
   own tests.** The control arm produced 16 clean answers over 1,133 problems,
   1.4 percent; at a few hundred problems the clean counts of the two arms
   cannot be told apart by any rule, and a rule that cannot decide is not a
   preregistration. Test-passing answers are 10 percent of the control's
   problems, which a few hundred can separate. The clean counts are still
   reported beside them, and the decision rule's thresholds -- 1.5 times better
   to adopt, fewer to reject, between the two to call it inconclusive -- apply
   unchanged to the new primary outcome.

The reason this remains worth running at that price is metric 4, unchanged:
the test-pass rate among answers that parse is what tells apart "the model
wrote good programs in the wrong notation" from "the model wrote bad
programs", and only the constrained arm can measure it without the syntax gate
in the way.
