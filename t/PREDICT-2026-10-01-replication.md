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

## Amendment, 2026-10-01 19:00Z, before any constrained answer to a held-out question: the reference under the grammar runs on our own CPU

The lab's cards have been held by another user's jobs for three days (each 7 to 8.5 GB free of 49 GB, 43 to
74% busy, polled 18:41Z to 18:45Z), and the desktop card trains the seeds. So part 2 runs where it can:

- **Engine:** llama.cpp's grammar sampler (llama-server, the lab's CPU-only build) in place of vLLM's xgrammar,
  on **the same file the unconstrained reference used**: Ollama's `phi4-mini` blob (Q4_K_M, sha256 3c168af1...),
  copied to the lab. vLLM would have decoded the bf16 weights, a different build from the reference's.
- **Grammar:** `t/t.gbnf` with its continuation lines joined (`spec_experiment.llama_gbnf`: llama.cpp ends a
  rule at a newline before a `|`; only whitespace changes, tested). `t/grammar_check.py` on the joined file
  gives the original's counts exactly: 8,752 of 8,756 parser-accepted programs accepted in canonical form,
  7,055 of 7,055 as written, 493 of 493 refusals refused. The 4 it refuses are hand-written tasks using sets,
  a user datatype and a sequence-valued specification function; none of the 11,794 tasks in every answer set
  on record (Phi's 53, the student's held-out 43, every dev set) uses any of the three, so the gap cannot
  cost either side here. The 9/18 rule asked for exact agreement before any arm; this is a stated exception,
  measured.
- **Sampling** as the unconstrained reference: greedy, then temperature 0.7, top-p 0.95, no top-k, no
  repetition penalty, min-p 0 (Ollama's default), prompt v5, 3,072 tokens. The chat template is the one in the
  GGUF (llama.cpp's Jinja), where Ollama applied its own copy of it.
- **Speed, measured on a dev problem:** about 6 tokens a second for one request on 12 threads. One server
  with four slots on 40 threads (nice 19; our four idle Qwen servers stopped to make room) runs the greedy
  set first, then the sixteen sampled sets, as long as they take.

Serving note, 2026-10-01 20:40Z (speed only; weights, grammar, prompt and sampling unchanged): the four-slot
server ran about one core's worth (llama.cpp samples under a grammar on the server's main thread; the grammar
README warns of "performance gotchas"): 29 answers in the hour to 20:37Z, a third of them running to the 3,072-
token cap. It was replaced by six one-slot servers of six threads each, six workers each taking its own answer
sets. The 92 greedy answers already written stay.

## Outcome, seed 2, 2026-10-01 22:34Z

Trained as seed 1 (1,240 steps, final loss 0.0238, seed 1's 0.0238), the Python first on the clean 200 once,
graded by the same kernels, check and scorer (complete specifications):

| | Python that passes its tests | a kept specification | answers (all pass tests) | at least 1 | at least 3 | at least 5 | at least 6 | all seven |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| seed 1 (14:46Z) | 110 | 50 | 43 | 18 | 14 | 13 | 9 | 5 |
| **seed 2** | 106 | 44 | 36 | **19** | 16 | 12 | 7 | **6** |

99 (seed 2): **at least 12 at one kernel and 3 at seven: holds**, 19 and 6. Seed 3 is training.

## Outcome, seed 3 and the three seeds, 2026-10-02 02:08Z

Seed 3 trained as the others (1,240 steps, final loss 0.0234), the Python first on the clean 200 once, graded
the same way. Complete specifications:

| | Python that passes its tests | a kept specification | answers (all pass tests) | at least 1 | at least 3 | at least 5 | at least 6 | all seven |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| seed 1 | 110 | 50 | 43 | 18 | 14 | 13 | 9 | 5 |
| seed 2 | 106 | 44 | 36 | 19 | 16 | 12 | 7 | 6 |
| seed 3 | 106 | 42 | 35 | 15 | 13 | 10 | 10 | 8 |
| **mean of three** | | | | **17.3** | | | | **6.3** |
| Phi-4-mini, prompted, 17 answers a problem | | | | 3 | 3 | 3 | 2 | 2 |

99. **Each new seed at least 12 at one kernel and 3 at seven: holds.** Seed 2: 19 and 6; seed 3: 15 and 8.
100. **The mean of the three at least 14 at one kernel: holds.** 17.3.

Every seed of the recipe proves on the clean 200, on complete specifications, five to six times what the
prompted reference proves with the same seventeen answers a problem, at one kernel and at seven. The seeds
spread from 15 to 19 at one kernel and 5 to 8 at seven. The first of section 1's two remaining conditions,
three seeds, is met. The second, the reference decoding under `t`'s grammar, is being generated on the lab
(about 600 of 3,400 answers at this writing) and the comparison is not called a win until it is graded.

Serving note, 2026-10-02 06:12Z (speed only): the desktop card is off the bus until it is power-cycled, so its
idle CPU helps until then: three one-slot llama-servers on the desktop, built from the lab's exact llama.cpp
commit (def4d406ae2c) and loading the same weights file (Ollama's blob, sha256 3c168af1...), take answer sets
from the far end of the list. A set another generator is writing is skipped (the generator's tag lock), so every
set is still written by one generator. The run was at 869 of 3,400 answers.

Serving note, 2026-10-02 09:15Z (time only): seven Phi answers under the grammar (problems 151, 385, 483, 571, 584,
656, 711) ran past the client's one-hour limit, which left no record, so each was asked again from the start on
the next pass and a set holding one could never reach 200. Every answer is capped at 3,072 tokens and ends on its
own, so the limit is now four hours; the decoding settings are unchanged, and llama-server cancels a request whose
client has gone (tools/server/server-queue.cpp, `server_response_reader::stop`). The run was at 1,133 of 3,400.

Serving note, 2026-10-02 09:21Z (speed only): at the lab's pace the remaining ~2,270 answers would take two more
days. When v2's training releases the desktop card (about 12:00Z), the rest is generated there: llama.cpp b11325,
the lab's exact commit (def4d406a), from its published CUDA build (checksums checked), the same weights file, the
same request settings, eight slots of the lab servers' 8,192-token context. The lab's generation pauses meanwhile
so no set is held by a slow worker, and the lab grades as registered once every set holds 200 answers. The k10
sets are sampled at 0.7, so a GPU's different rounding changes which sample is drawn, not how they are drawn; the
greedy set (s0) was completed on the lab's CPU.

Serving note, 2026-10-02 11:59Z (speed only): the desktop card fell off the bus again at 11:42Z, so the card's
share is postponed to the next power cycle. Meanwhile six more one-slot servers run on the lab (ports 8209 to 8214,
the same binary, weights and flags as the first eight; about 70 of its 120 cores are then this run's, the rest
free for others), fed by a second runner that shares sets through the same lock. The run was at 1,200 of 3,400.

Serving note, 2026-10-02 13:14Z (speed only): with one generator per answer set and one server per generator, the
two sets not yet begun would each have taken one server about eight hours while others sat idle. Every server (the
lab's fourteen, the desktop's three CPU helpers, and the desktop card when it returns) now sits behind one local
proxy that hands each request to a free server, and each set's generator keeps six requests in flight. Requests,
seeds and settings are unchanged; a request's answer does not depend on which of the same-build servers computes
it beyond floating-point rounding, as for the desktop helpers. The run was at about 1,460 of 3,400.

Serving note, 2026-10-03 04:58Z (speed only): the desktop card came back at 04:16Z and joined the pool; one eight-slot
server held it idle (llama-server samples under the grammar on one CPU thread a process), so it ran as three
one-slot servers at about 77 tokens a second each, until it fell off the bus again at 04:26Z. With the operator's
leave to use the lab freely, two one-slot servers now run on the lab's GPUs 2 and 3 in the memory the labmate's
fixed jobs leave free (about 1 GB spare on each after), the same llama.cpp build (b11325, its published CUDA build)
and the same weights file (sha256 3c168af1...), at about 52 tokens a second each. Requests and settings unchanged;
the proxy now sets aside a server that refuses connections and retries the request elsewhere. The run was at
about 2,320 of 3,400.

## Amendment, 2026-10-03 20:09Z, before any of the grammar sets is graded: answers that never arrive

3,346 of the 3,400 answers are in. Nine problems (656, 899, 584, 804, 658, 711, 846, 650, 914) are each missing from
one set and have been asked again for days; several of them ran past the old one-hour limit on 2026-10-02 too. A
server log shows why: on some outputs llama.cpp's grammar sampler slows to 0.01 to 0.3 tokens a second (server
8231, `n_gen = 885, tg = 0.31 t/s, tg_3s = 0.01 t/s`), against about 77 on a GPU and 4 on a CPU server for other
answers, so a 3,072-token answer would take days. This is the decoding engine with this grammar, not the model.

Rule: the remaining answers get one last pass with a one-hour limit a request (five times the slowest ordinary
answer, a 3,072-token answer on a CPU server). An answer that does not arrive within it is recorded as an empty
reply with `done_reason: "time limit"`, which the grading counts as an answer that fails. Every such record is
listed with the outcome. Nothing else about the run changes.

## Outcome of part 2, 2026-10-03 20:46Z: the reference under t's grammar, graded

All 3,400 answers (17 a problem: the greedy set and sixteen sampled sets), graded on the lab as the prompted
reference was. Answers recorded as empty under the 20:09Z rule: 0 [].

| clean 200, complete specifications | at least one kernel | all seven |
|---|---:|---:|
| Phi-4-mini under t's grammar, 17 answers a problem | 6 | 5 |
| Phi-4-mini under the grammar, the greedy answer alone | 3 | 1 |
| Phi-4-mini prompted, 17 answers a problem (before) | 3 | 2 |
| the student, seeds 1, 2, 3 (MBPP+'s references where they keep the problem's tests) | 18, 19, 17 | 5, 6, 8 |

The same with MBPP+'s references for Phi: 6 and 5. Under the grammar Phi proves 51, 86, 289, 334 and 814 by all
seven; the seeds prove 53, 169, 447, 672, 814 (seed 1), 53, 86, 447, 672, 814, 973 (seed 2) and 51, 53, 169, 447,
672, 675, 814, 973 (seed 3): one to two problems in common.

**Against AMBITION.md section 1's written bar** (beat Phi with three seeds, Phi given every advantage, then
double it; "6 clean against Phi's 3"): at one kernel every seed proves about three times what Phi does even
under the grammar (18, 19, 17 against 6). At all seven kernels, the column the bar calls clean, it is **not met**:
seed 1 ties Phi (5 against 5), seeds 2 and 3 beat it (6 and 8), and no seed doubles it. The grammar is the
advantage that closes the gap: it more than doubles Phi at all seven (2 to 5). So the student is not yet the
win section 1 asks for.

## Correction registered 2026-10-03 21:04Z, before any set is graded again: a v0 task returning bool

Reading why answers proved by one kernel stop short of seven: the student's answers to 51 and 334 (seeds 1 and
2) are `t 0` tasks returning `bool`, and the Verus and Rocq v0 lowerings emit them as `int` and `Z`, which is
malformed, while the other five kernels prove them. SPEC.md makes `bool` a v1 type ("New type: `bool`, usable as
a return or local type"), so these tasks are not well-formed v0; `t/check_wf.py` checked the v0 int-only rule on
parameters and not on the return. Among the graded answers, 17 of Phi's under the grammar, 12 of Phi's prompted
and 4 of the students' are `t 0` with a non-int return.

The rule, applied to every set alike: (1) the v0 int-only rule covers the return (one line in `check_wf`);
(2) every set is extracted with header promotion (a `t 0` task that uses a v1 form is the same program under
`t 1`, `spec_experiment.extract --promote-header`), which the students' sets always had and Phi's did not, so Phi
gets the same normalisation; (3) every changed task is graded again on the lab. Both numbers are reported, the
graded ones above and the corrected ones, and the section 1 judgement is made on the corrected numbers.

## The correction's result, and a second correction registered 2026-10-03 21:39Z before it runs: the instrument's noise

Graded with header promotion for every set and the v0 fix (21:37Z), clean 200, complete specifications, at least
one kernel / all seven, MBPP+'s references where they keep the problem's tests:

| | as graded before | corrected |
|---|---:|---:|
| Phi-4-mini under the grammar, 17 answers | 6 / 5 | 9 / 7 |
| Phi-4-mini prompted, 17 answers | 3 / 2 | 3 / 3 |
| seed 1 | 18 / 5 | 19 / 7 |
| seed 2 | 19 / 6 | 18 / 8 |
| seed 3 | 17 / 8 | 17 / 7 |

Of the students' changes, four are the fix (51 and 334 on seeds 1 and 2, from five kernels to seven: Verus and
Rocq now read verified / refuted). Six are not: 212, 454 (twice), 472, 629 and 675 changed level with no kernel
cell changing. They are the specification check's own noise. It draws 100 inputs a task from one generator shared
across the run, so a task's verdict depends on which tasks were checked before it (`t/spec_check.py` says so, and
names the remedy). Seed 3's 675 agreed on 100 draws in one run and met a counterexample, [3, 7, 10, 10], in the
other; 472 the reverse; 629's completeness sat at 0.601 and then 0.584 against the 0.6 threshold. A difference of
one or two problems between the student and Phi is inside that noise.

Second correction, for every compared set alike, before any result: the specification check runs again with each
task's own generator, seeded from the task's sha256 (`--per-task-seed`, the remedy `spec_check.py` names), and
1,000 draws instead of 100, so a verdict no longer depends on the run and a wrong answer is ten times likelier to
meet its counterexample. Section 1 is judged on those numbers. A counterexample is a proof that the answer is
wrong, so any answer that met one in any run is also listed.

## The second correction's result, 2026-10-03 21:41Z: section 1 judged

241 tasks, each with its own generator and 1,000 draws, MBPP+'s references where they keep the problem's tests
(MBPP's own give the same numbers except seed 3 at one kernel, 14). Clean 200, complete specifications:

| | at least one kernel | all seven |
|---|---:|---:|
| Phi-4-mini under t's grammar, 17 answers a problem | 9 | 7 |
| Phi-4-mini prompted, 17 answers a problem | 3 | 3 |
| the student (the 4B on v5), seed 1 | 18 | 7 |
| seed 2 | 18 | 8 |
| seed 3 | 15 | 7 |

**Section 1's written bar is not met.** Phi given every advantage (the grammar, and the same header normalisation
the student's sets had) proves 9 and 7. At one kernel two seeds double it exactly and the third does not; at all
seven, the column the bar names, two seeds tie it and one beats it by one. Against the prompted reference the
student is five to six times ahead at one kernel and more than twice ahead at seven, but that is not the
comparison section 1 set. The v5 recipe is also not the shipped one; the shipped recipe is measured the same way
next (`t/PREDICT-2026-10-03-shipped-recipe.md`).
