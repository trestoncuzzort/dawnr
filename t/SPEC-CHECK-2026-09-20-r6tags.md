# Specifications against the problems' own solutions, 2026-09-18

`python3 t/spec_check.py --pool v5 --n 100 --only clean`, seed 1. Each task's
`ensures` is evaluated with the problem's reference solution supplying the result, on random
arguments of the shapes the problem's own assertions use. A disagreement is a specification the
seven proof systems proved and the twin rule accepted that does not say what the problem asked.

- checked: 290
- agree on every draw: 262
- disagree: 3
- could not be checked: 25

- `qwen3.8-27b-fp8-v3/mbpp_179__is_num_keith`: ensures[0] false at `[4]`, the problem's solution answers `True`
- `qwen3.8-27b-fp8-v3/mbpp_195__first`: ensures[1] false at `[[0, 1, 2], 0, 0]`, the problem's solution answers `-1`
- `qwen3.8-27b-fp8-v3-s2/mbpp_908__find_fixed_point`: ensures[1] false at `[[0, 10, 11, 13, 13, 41, 43, 49, 59, 61, 62], 0]`, the problem's solution answers `-1`
