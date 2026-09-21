# Specifications against the problems' own solutions, 2026-09-18

`python3 t/spec_check.py --pool v3 --n 100 --only clean`, seed 1. Each task's
`ensures` is evaluated with the problem's reference solution supplying the result, on random
arguments of the shapes the problem's own assertions use. A disagreement is a specification the
seven proof systems proved and the twin rule accepted that does not say what the problem asked.

- checked: 5
- agree on every draw: 5
- disagree: 0
- could not be checked: 0

