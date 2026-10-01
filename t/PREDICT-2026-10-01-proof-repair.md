# Proof repair with Dafny's own message: registered 2026-10-01 07:59Z, before the student that will do it exists

## Why, and what it stands on

SAFE's second kind of training example is a wrong proof, the verifier's error and the correct
proof, and at inference a failed proof goes back to the model with that error
(arXiv:2410.15756, 3.3 and 4.2, read from the HTML): with one debugging step its 1.3B model reads
27.3 where one answer reads 21.6, and at ten answers 57.6 where ten read 40.3.

This project tried the same thing with a message that named nothing. Its debugging rows said, of
a failed proof, one generic line a kernel, and a second try trained on 788 of them repaired 1
answer of 91 (`t/PREDICT-2026-10-01-several-answers.md`, prediction 22; `CORRECTIONS.md` records
the same for a prompted 14B in September). Dafny's diagnostics name the clause that failed
(`t/dafny_feedback.py`): of the 484 proof-repair rows in the v5 training set, 260 now carry
them. The student trained on those rows is the first here that has seen a real verifier message.

## Two measurements, both with `t/proof_repair.py`

Dafny is the judge inside the loop and nothing else: what it verifies is carried over, what it
does not goes back with its lines, one greedy repair and two sampled a round, two rounds; a
repair reaches Dafny only if it parses, is well formed, passes the problem's tests and keeps a
given specification. The answer set that comes out goes to all seven kernels, the twins and the
reference check, and only that verdict is counted.

**On dev.** The 4B on v5's test-passing answers among its greedy answer and ten samples (one a
problem, the first set that has one), repaired, then through the gate; counted pooled with the
eleven sets it started from, as the specification-first arm was.

33. Repair adds at least 1 dev problem proved by at least one kernel with the reference check
    agreeing, beyond the eleven answers. Falsified by none.
34. Of the answers sent back in the first round, at least 1 in 10 is repaired (Dafny verifies a
    repair). Falsified below 10%.

**On the training side (a second round of the proof round).** The first round left 156 training
problems with a right specification and a test-passing program that no kernel proves or that a
kernel refutes (`t/PREDICT-2026-10-01-proof-round.md`). Each goes back with Dafny's message.

35. At least 15 of them are admitted to the pool after repair. Falsified below 15.

What would make all three fail for a reason that is not the idea: 260 rows is very little to
learn to act on a message from, and the message quotes the clause in Dafny's spelling, not
`t`'s.
