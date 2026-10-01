# Two more seeds of the recipe that went to the clean 200, and the reference under the grammar: registered 2026-10-01 15:40Z

At 14:46Z the 4B on v5 with the Python first was proved on 18 of the clean 200 on complete specifications by
at least one kernel and on 5 by all seven; Phi-4-mini, given the same 17 answers a problem, on 3 and 2
(`t/PREDICT-2026-10-01-several-answers.md`). `AMBITION.md` section 1 asks two more things before that
comparison counts, and nothing it says is relied on until it is proved, so both are registered now, before
any result:

**1. Three seeds.** The same recipe twice more: the same rows (`sft-student-v5-0750.jsonl`, 3,988), the
same trainer and settings (`t/student_sft.py`, Qwen3.5-4B, rank 64, five epochs, rows up to 2,845 tokens,
the reference attention path as seed 1 used), `--seed 2` and `--seed 3`; each merged student takes the
same route (the Python first, three attempts) on the clean 200, once, graded as seed 1 was. This is a
replication of the system already run there, registered before either seed exists; the held-out set is
not used to choose anything. On our own card after the RL run (`~/scratch/replication/run.sh`).

99. Each new seed is proved on at least 12 of the clean 200 on complete specifications by at least one
    kernel, and on at least 3 by all seven.
100. The mean of the three seeds is at least 14 at one kernel.

**2. The reference under `t`'s grammar.** Phi-4-mini decoding against `t/t.gbnf` (xgrammar, the backend
vLLM decodes with; the grammar was checked against the parser in both directions, `t/grammar_check.py`),
the same prompt and the same 17 answers a problem. On record it costs about 124 s an answer
(`t/RUN-NEXT.md`): 3,400 answers is about five days on one card at that rate. vLLM is installed on the lab,
whose cards may be used only when one has 30 GB free and under 10% use on two polls (today each has about
8 GB free). It runs when that rule is met, greedy set first; until then this condition stays open and
the comparison is not called a win.

## Amendment, 2026-10-01 18:46Z, before either seed exists: the seeds go first

The desktop card is idle (the 4B on v6's grading is CPU and lab work) and the specification round and the
RL run ahead of the seeds would hold it for most of a day. Goal 1's claim waits on the seeds, the round and
the RL run do not, so both seeds now train and take their held-out route back to back under one hold of
the card, before the round. The recipe is unchanged: `t/student_sft.py` has not changed since 02:48Z,
before seed 1 trained. Predictions 99 and 100 are unchanged.
