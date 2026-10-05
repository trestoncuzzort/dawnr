# Where the student's training rows come from, and what their licences allow: 2026-10-01 14:44Z

Rung R7 of the ladder (release the base, the adapters and the gate, usable by everyone) needs this
first. Licences below were read from each source's own repository (GitHub's licence field, fetched
today) or dataset card, not remembered.

## The v6 rows (3,887)

| rows | from | licence of the source |
|---:|---|---|
| 3,226 | proved answers, their Python, specifications, proof and debugging rows, all on MBPP, HumanEval and APPS problems | MBPP CC-BY-4.0; HumanEval MIT; APPS MIT |
| 185 | memory conversations written by this project | this repository's |
| 217 | specification-given rows from the vericoding benchmark's programs | MIT (github.com/Beneficial-AI-Foundation/vericoding) |
| 127 | specification-given rows from DafnyBench programs other than dafny-synthesis (collected from many GitHub repositories) | DafnyBench's repository: Apache-2.0 (github.com/sun-wendy/DafnyBench); the original repositories' own licences not checked one by one |
| 57 | specification-given rows from this project's own lifts of MBPP, HumanEval and APPS answers | as the first row |
| **44** | **specification-given rows from dafny-synthesis programs (MBPP-DFY), reached through DafnyBench** | **GPL-3.0 at the source (github.com/Mondego/dafny-synthesis)** |
| 16 | specification-given rows from HumanEval-Dafny | Apache-2.0 (github.com/JetBrains-Research/HumanEval-Dafny) |
| 15 | specification-given rows from Clover | MIT (github.com/ChuyueSun/Clover) |

**Correction, 2026-10-02:** reading the row names again, 4 of the specification-given rows come from ACSL by
Example (MIT, Fraunhofer FOKUS, github.com/fraunhoferfokus/acsl-by-example) and 5 from the Verus repository's
examples (MIT, The Verus Contributors, github.com/verus-lang/verus); the table above counted them under other
headings. Both are MIT, so nothing leaves the release, but their notices were missing from
`release/NOTICE-student` and are added there and to the published `student-v1` release.

52 rows in all name a dafny-synthesis program (the 44 above and 8 memory conversations that
reuse one).

**Correction, 2026-10-05:** "name" was the whole of the check. The vericoding benchmark carries the same MBPP-DFY
programs under its own ids, twice: DafnyBench's copy (`DD0643` and up, source-id `dafny-synthesis_task_id_N_Name`)
and Verus-Bench's translation (`DJ...`, source-id `proofsynthesis_task_id_N`; Verus-Bench's README says its 78 MBPP
tasks are "Translated from MBPP-DFY-153" and names github.com/Mondego/dafny-synthesis, read 2026-10-05). Counted in
the table above under "the vericoding benchmark's programs" (MIT), they stayed in every release: **48 of
`student-v1`'s 3,835 rows** (36 by DafnyBench's copy, 12 by the translation; 37 specification-given, 11 memory
conversations) and **61 of `student-v5`'s 5,095** (40 and 21). The sentence below, "The released adapters are
trained without the 52 rows", is true of those 52 and was read as "without dafny-synthesis", which is false. Both
model cards and both notices now say so, and the next release's rows pass `t/heldout_audit.py --refuse-gpl`, which
reads the benchmark's record and not the name. Found with the held-out audit of the same day
(`t/DECONTAMINATION-2026-10-05.md`); the six MBPP-DFY programs that are held-out problems are how it was found.

## Finding

The dafny-synthesis programs are GPL-3.0 where they were written. DafnyBench redistributes them
inside an Apache-2.0 repository; a redistribution does not change the original licence. This
repository's corpus file `t/out/loop/corpus-r12-headed.txt` carries 47 of them translated into `t`,
under this repository's Research Use License. The project already refused one share-alike corpus
for this reason (dafny-disco, CC-BY-SA-4.0, `t/LIFT-2026-09-26.md`).

## What the release does

The released adapters are trained without the 52 rows that name a dafny-synthesis program, and
the release states every source above. Whether the 47 translated programs stay in this repository
under its licence is the operator's decision; this note records the fact.

The 127 DafnyBench programs from other GitHub repositories are used under DafnyBench's own
Apache-2.0, as a published dataset is. They cannot be traced one by one: DafnyBench records each
program's file name with its repository's name and no owner (`test_file`, e.g.
`630-dafny_tmp_tmpz2kokaiq_Solution.dfy`, read from its dataset viewer today). The dafny-synthesis
programs are treated differently because their upstream licence is known and is share-alike.
