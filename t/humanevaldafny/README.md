# HumanEval-Dafny tasks in t (D8)

These 45 tasks restate verified solutions from [HumanEval-Dafny](https://github.com/JetBrains-Research/HumanEval-Dafny),
JetBrains Research's Dafny translation of the HumanEval problems with specifications. It is licensed under the
Apache License 2.0; a copy is in `LICENSE-HumanEval-Dafny`. dawnr's lifter (github.com/trestoncuzzort/dawnr,
`t/lift_corpora.py`) translated each solution whose constructs t states, in September 2026, after screening out every
problem held out from dawnr's training. The commit read was not recorded; the branch head on 2026-10-07 is
69c950c138d83ef13f92c59e00af472cd18f1f79.

`t/audit.py --kernel dafny` measures each specification; the table is `t/AUDIT-HUMANEVAL-DAFNY.md` (PREDICT T59).
