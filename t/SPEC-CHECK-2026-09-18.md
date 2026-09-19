# Specifications against the problems' own solutions, 2026-09-18

`python3 t/spec_check.py --pool v3 --n 200 --only clean`, seed 1. Each task's
`ensures` is evaluated with the problem's reference solution supplying the result, on random
arguments of the shapes the problem's own assertions use. A disagreement is a specification the
seven proof systems proved and the twin rule accepted that does not say what the problem asked.

- checked: 86
- agree on every draw: 67
- disagree: 8
- could not be checked: 11

- `qwen3.8-27b-fp8-v3/mbpp_179__is_num_keith`: ensures[0] false at `[19]`, the problem's solution answers `True`
- `qwen3.8-27b-fp8-v3/mbpp_195__first`: ensures[1] false at `[[-1, 0, 1, 6, 7, 8, 8], 0, 0]`, the problem's solution answers `-1`
- `phi4-mini-v3/mbpp_20__is_woodall`: ensures[0] false at `[7]`, the problem's solution answers `True`
- `qwen15b-base-v3/mbpp_768__check_Odd_Parity`: ensures[0] false at `[4]`, the problem's solution answers `True`
- `student-r4-v3/mbpp_768__check_Odd_Parity`: ensures[0] false at `[16]`, the problem's solution answers `True`
- `student-r5-v3/mbpp_768__check_Odd_Parity`: ensures[0] false at `[3]`, the problem's solution answers `False`
- `student-r6-v3/mbpp_768__check_Odd_Parity`: ensures[0] false at `[8]`, the problem's solution answers `True`
- `student-r6-g/mbpp_768__check_Odd_Parity`: ensures[0] false at `[26]`, the problem's solution answers `True`
