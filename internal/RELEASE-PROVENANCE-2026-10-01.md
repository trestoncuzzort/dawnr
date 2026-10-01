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

52 rows in all name a dafny-synthesis program (the 44 above and 8 memory conversations that
reuse one).

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

The 127 DafnyBench programs from other GitHub repositories carry the licences of those repositories,
which have not been checked one by one; that check comes before the release too.
