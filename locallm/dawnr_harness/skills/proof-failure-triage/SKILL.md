---
name: proof-failure-triage
description: Read a t grading table, one real/twin cell per kernel (verified, refuted, unproved, timeout, malformed, vacuous, abstain, no-twin), and say what a failing cell means. Use after grade.py or run_par.py, when a kernel is not verified/refuted.
license: the repository's LICENSE
---

# Triaging a t verdict table

Every cell is `real outcome / twin outcome`. Only `verified / refuted`, and
not flaked, counts (t/GRADER.md, "What counts"). Each outcome has one meaning
and, just as important, things it never means:

- **VERIFIED**: a positive, checked proof of the task's obligations. Never
  means the specification asked the right question; that is `spec_check.py`
  and the twin's job, not this outcome's.
- **REFUTED**: the kernel accepted a certificate proving the obligation
  fails at one measured witness. Never minted from a bare failing exit code
  or "could not prove".
- **UNPROVED**: the kernel stopped without a proof or a countermodel. Never
  means the property is false, and never means it is true; this budget, on
  this kernel, settled nothing.
- **TIMEOUT**: a deterministic resource budget ran out. A subset of "not
  knowledge", never REFUTED and never VERIFIED.
- **MALFORMED**: the file did not even parse, or a positive-evidence check
  failed outright. Never a proof failure; the kernel never saw the
  obligation. If the REAL cell reads this, the program's own syntax or that
  kernel's lowering is broken, not the specification.
- **VACUOUS**: accepted, but for the wrong reason (an unsatisfiable or
  content-free `requires`/`ensures`). The theorem proved is not the one that
  was supposed to matter.
- **ABSTAIN** / **no-twin**: the lowering has no honest translation for
  something the task uses, or the twin ladder found nothing measurable.
  Neither kernel was really asked; neither is evidence for or against the
  task.
- **(FLAKED)**: repeated runs of the same file disagreed. Never trust the
  last-observed outcome; rerun before triaging further.

What to do, by which side is failing:

1. REAL is MALFORMED, or a lowering error: a bug in the program's syntax or
   in that kernel's lowering, not in the proof. Fix the program
   (`t-spec-writing`, `t-repair`) or name the lowering gap; do not touch the
   specification to work around it.
2. REAL is UNPROVED or TIMEOUT: the property may still be true. Strengthen
   what the kernel can see (a tighter loop invariant, a clearer `decreases`)
   before assuming the task is unprovable.
3. REAL is VACUOUS: rewrite `requires`/`ensures`, not the body; the body was
   never the problem.
4. REAL is VERIFIED but TWIN is not REFUTED (VERIFIED, UNPROVED, or
   no-twin): the specification may have no teeth on this kernel. Do not
   report the task as counting; it needs a twin mutation this kernel
   actually refutes.

Never call a cell clean, or say it counts, unless it reads `verified /
refuted` and was not flaked. Reporting anything else as a pass is the false
verdict AGENTS.md rule 2 refuses.
