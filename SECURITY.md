# Reporting something that looks wrong

Two kinds of report are welcome, and both go to the GitHub account that owns this repository
(https://github.com/trestoncuzzort), privately when the finding is a vulnerability.

**A wrong number.** If a table here disagrees with what the scripts produce on your machine, say which table,
which script and what you got. Every number in this repository names the script that measured it, so a
disagreement is a bug in one of the two and worth finding either way.

**A soundness hole.** A t task that all seven checkers accept although its specification does not hold, or a
twin that should be refuted and is not, is the most serious class of bug this project can have. Include the
task, the witness input if you have one, and the checker versions from `t/AGREEMENT.md`.

The verifiers themselves (Dafny, Verus, GNATprove, Frama-C, Lean, Rocq, F\*) are separate programs; report bugs
in them upstream.
