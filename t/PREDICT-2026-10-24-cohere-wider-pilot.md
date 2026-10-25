# Cohere teacher: a wider pass on the original training pilot

Registered before dispatch on 2026-10-24. The grant explicitly permits training dawnr on outputs that pass our
checks. The full Command A pass over 1,705 other training problems is already running on GitHub. This small
parallel pilot decides whether more samples and longer replies earn their cost before a wider second pass.

## Inputs and procedure

- The same 50 training problems as the first three teacher pilots, SHA-256
  `446fbee835307badfa317826dceee48c9f5f6b7c26921d051503b86ed02351d4`. None occur in the full pass's 1,705.
- Command A (`command-a-03-2025`), the same primer, reference Python and acceptance checks. Twenty candidates per
  problem (one greedy, nineteen sampled), seed offset 10000, at most 4096 output tokens, no thinking.
- One GitHub teacher job, $25 ceiling. The $83.082037 already recorded plus the full pass's $600 allocation and
  this $25 allocation total $708.082037, below the $950 stop. These allocations are not actual spend.
- The strict check stays at 1000 draws and a 0.9 floor on both mutant families. All outputs stay encrypted on
  GitHub and are opened privately. Kept examples remain eligible for candidate B even if this pilot fails its
  expansion rule.

## Predictions and decision

The original Command A pilot kept specifications for 4 problems, 9 candidates, at $6.48. This pilot predicts at
least 8 strictly kept problems and at least 62 strictly kept problems per $100 of its recorded cost. Fewer than
8 or a yield below 62 falsifies the respective prediction. Both must hold before this wider recipe is used for
a larger second pass. If the budget ends the run early, the count and actual call count are still reported;
an incomplete run cannot qualify the recipe for expansion.

This is a practical choice of a data-generation recipe on training problems, not evidence that dawnr's model
improved. Sampling and reply length change together, so it cannot identify which change caused a difference.
The model still has to pass the five conditions in `internal/RELEASE-6.0-PLAN.md`.

Sources: the first pilot table in that plan; `t/recipes/teacher_cohere_specs.sh`; `t/recipes/v9_strict_specs.py`;
[Cohere Chat](https://docs.cohere.com/reference/chat) for the token limit and best-effort seeded sampling.

## Result, 2026-10-25

Run `40139205280` completed all 50 problems. The strict check kept 5 problems and 9 candidates for a recorded
$13.064852, or 38.27 kept problems per $100. Both predictions failed: fewer than 8 problems and below 62 per $100.
The 1,000 logical requests comprise 990 successful calls and 10 HTTP 422 errors; 22 replies hit the token limit.
The $25 ceiling did not stop the run. The verified encrypted artifact and aggregate receipt are recorded in
`release/evidence/cohere-wider-pilot-2026-10-25.json`.

All five kept problems were already covered by the original pilots and the 6,803-row draft. Two overlap with
the original North Mini Code pilot. The skip-covered rule therefore adds no rows. Do not expand this recipe
unchanged. Its $25 reservation is replaced by the recorded $13.064852 in subsequent allocation calculations.

## Where candidates were lost

Parsing the saved replies with the unchanged parser reproduces the run's 328 parsed specifications exactly.
Of 1,000 cached replies, 639 fail parsing, 23 have nonempty text without a recognized t block, and 10 are empty
provider errors (`NO_VALID_RESPONSE_GENERATED`). Of the 968 complete replies, 623 still fail parsing. Only 22
requests hit the token limit, so token-limit termination does not explain most failed replies.
The first parser failure occurs in an expression for 371 replies. This counts the first reported failure, not
every syntax defect or the semantic quality of a hypothetical repaired answer.

Two of the 328 parsed tasks fail the subsequent printing check. Of the 326 scored records, 45 pass the three-test
gate on 11 problems, 15 are duplicates, 224 are dropped and 42 are unscorable. The three-per-problem cap leaves
21 candidates, and the first reference filter leaves 12 for the stricter check; nine survive. All ten three-test
passing candidates on the six problems absent from the current draft already fit that cap. Removing the cap
cannot recover an excluded candidate on an uncovered problem from this saved pilot. Counts and source hashes are in
`release/evidence/cohere-pilot-attrition-2026-10-25.json`. This analysis made no model calls and reran no reference
or proof checks.

The earlier record matters to the next hypothesis. `t/PREDICT-2026-10-12-udebug-teacher.md` already measured extra
syntax prose, parser-feedback repair and a Dafny target: those pilots failed their coverage predictions, and the
Dafny target accepted the same three problems as the t target. Those were different teachers and whole judge
programs, so they do not settle a Cohere specification-only variant. They do rule out treating the representation
change or a repair prompt as an established solution. The primed 9B's complementary coverage is separately measured
in `t/PREDICT-2026-10-21-v8-spec-rows.md`; the current Cohere run already uses that grammar-and-examples primer.
Wait for the registered North thinking-budget follow-up and the full pass before choosing another grant allocation.
