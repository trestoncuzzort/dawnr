# Specifications against the problems' own solutions, 2026-09-19

`python3 t/spec_check.py --pool v5 --n 100 --only clean`, seed 1. Each task's
`ensures` is evaluated with the problem's reference solution supplying the result, on random
arguments of the shapes the problem's own assertions use. A disagreement is a specification the
seven proof systems proved and the twin rule accepted that does not say what the problem asked.

- checked: 321
- agree on every draw: 288
- disagree: 5
- could not be checked: 28

- `qwen3.8-27b-fp8-v3/mbpp_179__is_num_keith`: ensures[0] false at `[3]`, the problem's solution answers `True`
- `qwen3.8-27b-fp8-v3/mbpp_195__first`: ensures[1] false at `[[-1, 4, 5, 7, 8], 5, 1]`, the problem's solution answers `-1`
- `qwen3.8-27b-fp8-v3-s2/mbpp_908__find_fixed_point`: ensures[1] false at `[[0, 40, 45, 47, 84], 0]`, the problem's solution answers `-1`
- `prover-train/mbpp_509__average_Odd`: ensures[0] false at `[16]`, the problem's solution answers `'Invalid Input'`
- `prover-train/mbpp_890__find_Extra`: ensures[0] false at `[[0, 4], [5], 3]`, the problem's solution answers `0`
