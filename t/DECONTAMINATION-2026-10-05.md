# The training rows held 18 of the clean 200 under other names, 2026-10-05

Found at 04:35Z on 2026-10-05, about forty minutes after `student-v5` was published with "26 of 200 held-out problems,
16 by all seven provers" at the top of the README. That sentence was wrong: 18 of those 200 problems had a
row in the training set that either came from the problem itself or held a program that behaves as its
reference solution does. On the 182 that remain the published model proves **18, 12 by all seven**, and
Phi-4-mini under the grammar proves 7 and 5. Every fine-tuned row of the scoreboard is restated below; so is
every prompted one, on the same 182, because the problems that left are easy ones and the untrained models
had been credited with them too.

The lists as data: `t/decontamination-rows-2026-10-05.json`. The tool: `t/heldout_audit.py`. The panel:
`t/score_levels.py --panel clean-182` (the default since this file).

## How it was found

Building the next round's rows needed the filter that keeps GPL-derived rows out of a release. The filter of
2026-10-01 matched the name `dafny-synthesis`. Reading the rows by the vericoding benchmark's own record of
where each task came from showed the same MBPP-DFY programs under names the filter never matched
(`vericoding_dd0736__replaceChars` is `dafny-synthesis_task_id_474_ReplaceChars`), and 474 is a held-out
problem. That was the licence question and the contamination question at once, because the task id in that
record is the MBPP task id.

## How they got in

Three routes, none of which the gates of 2026-09-21 and 2026-09-25 sat on.

1. **A second benchmark's names.** The corpus builder refuses a document named `mbpp_N` or
   `dafny_synthesis_task_id_N` when N is held out. The vericoding benchmark redistributes DafnyBench's copy of
   MBPP-DFY as `DD0643` to `DD0850` and Verus-Bench's translation of it as `DJ...` (Verus-Bench's README: its
   78 MBPP tasks are "Translated from MBPP-DFY-153"). The lift mapped a vericoding task to a problem only when
   its source was HumanEval (`t/lift_corpora.py head_for`), so nothing connected `vericoding_dj0091` to MBPP 447.
2. **A rechecked set the screen never saw.** The lift's twin gate did refuse `cubeElement` and `replaceChars`
   as twins of held-out 447 and 474 (`twin-decisions.jsonl` of the 2026-09-26 and 2026-09-27 lifts: 100 of 100
   draws agree). Rechecked copies of both then entered the r12 corpus through
   `t/out/lifted-tasks-2026-09-26-let-rechecked` and `-rechecked`: their metadata holds the lifter's
   equivalence check and no screen decision (no `twin-decisions.jsonl`, no `refused.jsonl`), and the corpus
   builder's own gates match names.
3. **Specification prompts for the teachers.** The teacher rounds were given vericoding specifications to
   write bodies for. Nothing mapped a prompt to the problem it came from, so the teachers answered MBPP 644 and
   804 and the rows were admitted.

The twin gate itself has two blind spots this audit closes: it asked for every test point to pass, so a
program whose `requires` excludes one point was never a candidate (`isPrime` requires n >= 2; MBPP 605 tests
-1010); and it compared arities, so a program that takes an array was never compared with a problem that takes
the array and its length (MBPP 804).

## The rule

> a training row is flagged for a gated problem (held-out or dev) when it names that problem's own
> formalisation (lineage), or holds a t program, in its answer or its prompt, that passes at least one of the
> problem's test points, fails none, and on 100 drawn inputs answers fewer than 10% of the inputs both answer
> differently from the problem's reference (twin; t/twin_draws.py), the problem's length argument left out
> where it has one

Applied to all 13 row files a measured model trained on (50,861 rows, 4,746 distinct t programs). Nothing is
read by hand and nothing is excused: the last column below is a reading for the reader, not a filter. Six of
the 18 are the problem itself, five more the same function from somewhere else, and seven are coincidences
or a degenerate reference, which the rule removes all the same. Removing a problem cannot favour a model; it
makes the panel smaller.

The rule was fixed before any model was scored on the result, with one exception stated here: the six
problems found by lineage were found first, and the published model's answers on those six were looked at
(it passes the tests of five) before the twin reading was run. The twin reading was then computed from the
rows alone, and every model was scored once, on the final list.

## The 18

| held-out problem | found by | rows in dawnr v5's 5,095 | reading |
|---:|---|---:|---|
| 78 | twin | 9 | `mbpp_509__average_Odd`: the average of the odd numbers up to an odd n is (n + 1) / 2, which is what MBPP 78's reference returns for odd n. A different task; the two coincide on odd inputs. |
| 86 | twin | 1 | The failing program a debug row shows for MBPP 59 (octagonal number) computes 3n(n - 1) + 1, the centered hexagonal number. A different task, and in a prompt, not an answer. |
| 224 | twin | 1 | `vericoding_da0140__minBacteria`, an APPS puzzle whose answer is the number of set bits. The same function. |
| 334 | twin | 5 | The failing program a debug row shows for MBPP 850 (a triangle from its angles) checks the triangle inequality on sides. The same function, in a prompt. |
| 436 | twin | 2 | `apps_3352__find_longest` (the number with the most digits) agrees with MBPP 436's reference, which returns the first negative number, on every drawn input. A different task. |
| 447 | lineage, twin | 1 | `vericoding_dj0091__cubeElement`, Verus-Bench's translation of MBPP-DFY 447. The problem itself. |
| 472 | lineage, twin | 9 | `vericoding_dd0735__containsConsecutiveNumbers`, MBPP-DFY 472, which formalises the text as "two neighbours somewhere" and fails the problem's tests; `apps_3514__validate_sequence` is a near twin. The problem's own text read by someone else. |
| 474 | lineage, twin | 1 | `vericoding_dd0736__replaceChars`, MBPP-DFY 474. The problem itself. |
| 605 | lineage | 1 | `vericoding_dd0763__isPrime`, MBPP-DFY 605, for n >= 2. The problem itself; the twin reading does not see it, because MBPP's reference is wrong on composites. |
| 644 | lineage | 1 | `vericoding_DJ0116`, a teacher's answer to Verus-Bench's translation of MBPP-DFY 644; the lifted specification does not reverse anything and fails the tests. The problem's own text. |
| 736 | twin | 8 | `vericoding_dd0050__binarySearch` and `vericoding_dv0068__searchInsert`: the lower bound in a sorted sequence, which is `bisect_left`. The same function. |
| 741 | twin | 20 | `he_48__is_palindrome`, `apps_3514__validate_sequence` and others answer drawn strings as "all characters the same" does (almost always false). Different tasks; this problem's tests were already listed as weak on 2026-09-21. |
| 798 | twin | 3 | `vericoding_dv0073__solution` sums an array. The same function. |
| 804 | lineage, twin | 2 | `vericoding_DD0806` and `vericoding_DJ0129`, teachers' answers to MBPP-DFY 804 by both routes; twins once the length argument is left out. The problem itself. |
| 822 | twin | 2 | `apps_3523__password`, a password check with other rules, agrees on every drawn input. A sibling task. |
| 899 | twin | 17 | MBPP 899's reference returns True on every input, so every program that returns `true` is its twin. Degenerate. |
| 908 | twin | 4 | `vericoding_DD0199` and `vericoding_DD0835` (the first zero of a slowly falling array) agree with "the fixed point" on the drawn inputs, the length argument left out. A different task. |
| 947 | twin | 1 | `vericoding_dd0663__smallestListLength` (MBPP 95, the shortest sublist) against the shortest word. The same function. |

Nine more held-out problems are matched by some row and were already out of the panel since 2026-09-21
(138, 269, 443, 518, 565, 566, 626, 687, 813); 80 of dawnr v5's 5,095 rows match one of the 18.

## The dev split

Five of the 100 dev problems have a twin among the rows, all of them answers to training problems that
compute the same function (MBPP has near-duplicate tasks, and the behavioural list of 2026-09-25 compared
held-out problems only). The dev panel is the other 95 from here on (`heldout_audit.dev_95()`).

| dev problem | rows in dawnr v5's 5,095 | twins |
|---:|---:|---|
| 113 | 40 | `apps_3514__validate_sequence`, `mbpp_913__end_num` |
| 508 | 12 | `mbpp_69__is_sublist` |
| 547 | 8 | `apps_3508__halving_sum` |
| 727 | 30 | `mbpp_173__remove_splchar`, `mbpp_676__remove_extra_char` |
| 874 | 6 | `apps_4464__feast` |

## Every published count again

Each row was first reproduced from its saved answer sets and specification verdicts on the 200 (all 24
reproduce exactly), then counted on the 182. At least one prover and all seven, as published
(`t/score_levels.py --min-completeness 0.6`).

| | on the 200, as published | on the 182 | flagged problems it had been credited with |
|---|---:|---:|---|
| the 4B on v5's rows, training seed 1 | 18 and 7 | **13** and **5** | 334, 447, 474, 804, 908 |
| the same, seed 2 | 18 and 8 | **13** and **5** | 86, 334, 447, 474, 908 |
| the same, seed 3 | 15 and 7 | **9** and **6** | 447, 474, 605, 741, 804, 908 |
| v3's rows, seed 1 | 17 and 10 | **12** and **7** | 86, 334, 447, 474, 741 |
| the same, seed 2 | 16 and 8 | **10** and **4** | 86, 334, 447, 741, 804, 899 |
| the same, seed 3 | 17 and 8 | **11** and **4** | 86, 334, 447, 474, 605, 741 |
| v3's rows plus 182 rows from a teacher's proved documents, seed 3 | 21 and 12 | **15** and **9** | 334, 447, 474, 605, 741, 947 |
| the same, seed 1 | 19 and 8 | **15** and **5** | 86, 447, 474, 908 |
| the same, seed 2 | 13 and 7 | **9** and **5** | 447, 474, 741, 908 |
| v3's rows plus 598 rows from every document admitted since, seed 1 | 23 and 13 | **16** and **10** | 334, 447, 474, 605, 741, 804, 908 |
| the same, seed 3 | 27 and 13 | **19** and **10** | 86, 334, 447, 474, 605, 741, 804, 908 |
| the same, seed 2 | 24 and 15 | **17** and **10** | 86, 447, 474, 605, 741, 804, 908 |
| the release-v4 candidate's rows plus round 3's 129 APPS documents, seed 2 | 27 and 15 | **18** and **10** | 86, 334, 447, 474, 605, 741, 804, 908, 947 |
| the same, seed 3 | 23 and 13 | **14** and **8** | 86, 334, 447, 474, 605, 741, 804, 908, 947 |
| the same, seed 1: **dawnr v5**, the published model | 26 and 16 | **18** and **12** | 86, 334, 447, 474, 605, 741, 804, 908 |
| the release-v4 candidate (the 598-row recipe without the 46 rows a name filter removed), seed 1 | 23 and 13 | **17** and **10** | 86, 334, 447, 474, 605, 741 |
| Qwen3.5-4B, dawnr's own starting weights, prompted, 17 answers a problem | 15 and 8 | **9** and **6** | 86, 334, 474, 605, 741, 908 |
| Qwen3.5-9B, prompted, 17 answers a problem | 18 and 7 | **15** and **6** | 334, 804, 908 |
| Qwen3.5-2B, prompted, 17 answers a problem | 4 and 3 | **2** and **2** | 334, 741 |
| a Qwen3.5-2B fine-tuned on the release-v4 candidate's rows, seed 1 | 8 and 6 | **4** and **3** | 86, 447, 474, 741 |
| Qwen3.5-0.8B, prompted, 17 answers a problem | 1 and 1 | **1** and **1** | none |
| Qwen3.5-27B (fp8), prompted, 17 answers a problem | 43 and 29 | **33** and **23** | 86, 334, 447, 474, 605, 736, 741, 804, 908, 947 |
| Phi-4-mini, prompted, 17 answers a problem | 3 and 3 | **2** and **2** | 334 |
| Phi-4-mini decoding under t's grammar, 17 answers a problem | 9 and 7 | **7** and **5** | 86, 334 |

## What it changes

- **The headline.** dawnr v5 proves 18 of 182, 12 by all seven; not 26 of 200 and 16.
- **The comparison of record.** Phi-4-mini under the grammar proves 7 and 5 on the 182. Every training seed of
  the published recipe is above both (18 and 12, 18 and 10, 14 and 8). Double Phi (14 and 10) is met by two
  seeds of three, as it was on the 200; the third has 8 by all seven.
- **What fine-tuning adds.** The same 4B before any fine-tuning proves 9 and 6 on the 182. The published model
  adds 9 problems and 6 by all seven. It was credited with two flagged problems its own base model was not
  (447 and 804, both the problem itself in its rows); the rest of what it lost the untrained models lost too.
- **The size curve.** The prompted 27B proves 33 and 23, the 9B 15 and 6, the 2B 2 and 2, the 0.8B 1 and 1.
- **The release gate of v5** still holds on the corrected panels: R3 asked for 17 and 9 and reads 18 and 12;
  R2 asked for 3 dev problems on complete specifications and reads 3 of the 95 (it read 4 of the 100, one of
  them dev 727, a twin); R1, 27 of 33 given specifications, is unchanged and qualified below.

## The 33 given specifications

The 33 held-out questions were checked for a row with the same name, text or specification
(`t/student_rows.py leaks_heldout`). They were never checked for behaviour, and the questions are small common
functions. Running every training program of the same type on each question's own input domain: **19 of the
33 have a program in the rows that answers at least 90% of the inputs as the held-out program does**, under
another name (`clover_abs__abs` is held out; three other `abs` are trained on). dawnr v5 proves 27 of the 33
by all seven: 17 of those 19, and **10 of the 14 with no such program**. "27 of 33 held-out specifications"
stays true as counted and says less than it sounds like; the 10 of 14 is the number for a specification
whose function the model has not seen.

## Licence: the same rows

The release notes say the adapters are trained without the dafny-synthesis rows. By lineage they are not:

| | rows | descend from MBPP-DFY (GPL-3.0 at the source) | by DafnyBench's copy | by Verus-Bench's translation |
|---|---:|---:|---:|---:|
| `student-v1`, published 2026-10-02 | 3,835 | 48 (37 specification-given, 11 memory conversations) | 36 | 12 |
| v3's rows | 4,027 | 50 | 40 | 10 |
| the release-v4 candidate | 4,579 | 61 | 40 | 21 |
| `student-v5`, published 2026-10-05 | 5,095 | 61 | 40 | 21 |

Verus-Bench is published under MIT by Microsoft and names github.com/Mondego/dafny-synthesis as the source of
its MBPP set; that repository's licence is GPL-3.0 (both read today, receipt b3750197e472). By the reading
this project already took on 2026-10-01, a redistribution or a translation does not change the licence of the
original. Whether an adapter trained on 1.2% such rows carries any obligation is not settled anywhere and is
not decided here. What is decided: the release notes are corrected to say what the rows are, and the next
release is trained without them (`t/heldout_audit.py --refuse-gpl`). Withdrawing `student-v1` and
`student-v5` in the meantime is the operator's decision.

## What the audit cannot see

- The same task under a signature that differs by more than a length argument (arguments in another order,
  a pair where the problem takes two values), when the benchmark records no lineage for it.
- A training row that teaches the held-out answer in English or Python only: it reads t programs and
  vericoding names. Rows for pool problems are covered by the lists of 2026-09-21 and 2026-09-25.
- A problem whose reference does not run or whose inputs cannot be drawn keeps every candidate, the
  conservative side. A wrong reference can clear a right program (MBPP 605's reference calls 4 a prime, which
  is why `isPrime` is found by lineage alone).
- Pretraining. Qwen3.5 and Phi-4-mini have very likely seen MBPP; that is true of every row and is why the
  comparison is between models under the same panel, not against zero.

## What is fixed

- `t/heldout_audit.py` reads the rows themselves, whatever route a row took, and is the last gate of a row
  build: `--panels` refuses a row that matches a problem still in a panel; `--refuse-gpl` refuses the lineage.
  18 tests (`t/test_heldout_audit.py`), each a case met here.
- `t/score_levels.py` and `t/score_heldout.py` score the clean 182 by default; `--panel clean-200` and
  `--clean-panel 200` reproduce what was published.
- The next round's rows are built through the gate. The three routes above are not each patched; the gate
  after them is what is relied on, because a fourth route would have the same shape.
