# Specifications against the problems' own solutions, 2026-09-18

`python3 t/spec_check.py --pool v4 --n 100 --only clean`, seed 1. Each task's
`ensures` is evaluated with the problem's reference solution supplying the result, on random
arguments of the shapes the problem's own assertions use. A disagreement is a specification the
seven proof systems proved and the twin rule accepted that does not say what the problem asked.

- checked: 243
- agree on every draw: 229
- disagree: 5
- could not be checked: 9

- `phi4-mini-v3/mbpp_20__is_woodall`: ensures[0] false at `[23]`, the problem's solution answers `True`
- `qwen15b-base-v3/mbpp_768__check_Odd_Parity`: ensures[0] false at `[22]`, the problem's solution answers `True`
- `qwen3.8-27b-fp8-v3/mbpp_179__is_num_keith`: ensures[0] false at `[9]`, the problem's solution answers `True`
- `qwen3.8-27b-fp8-v3/mbpp_195__first`: ensures[1] false at `[[-1, 0, 1, 2, 3, 4, 5, 8], 3, 0]`, the problem's solution answers `-1`
- `student-r4-v3/mbpp_768__check_Odd_Parity`: ensures[0] false at `[23]`, the problem's solution answers `False`
