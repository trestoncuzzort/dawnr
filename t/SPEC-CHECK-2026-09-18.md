# Specifications against the problems' own solutions, 2026-09-18

`python3 t/spec_check.py --pool v5 --n 200 --only clean`, seed 1. Each task's
`ensures` is evaluated with the problem's reference solution supplying the result, on random
arguments of the shapes the problem's own assertions use. A disagreement is a specification the
seven proof systems proved and the twin rule accepted that does not say what the problem asked.

- checked: 358
- agree on every draw: 327
- disagree: 13
- could not be checked: 18

- `deepseek-coder-v2-16b-v4-s2/mbpp_908__find_fixed_point`: ensures[1] false at `[[0, 4, 7, 9, 46, 54, 91], 0]`, the problem's solution answers `-1`
- `qwen15b-base-v3/mbpp_768__check_Odd_Parity`: ensures[0] false at `[2]`, the problem's solution answers `True`
- `qwen2.5-coder-1.5b-r0hf/mbpp_58__opposite_Signs`: ensures[0] false at `[0, -2]`, the problem's solution answers `True`
- `qwen2.5-coder-1.5b-r0hf-v3/mbpp_58__opposite_Signs`: ensures[0] false at `[0, -4]`, the problem's solution answers `True`
- `qwen2.5-coder-1.5b-r0hf-v3/mbpp_768__check_Odd_Parity`: ensures[0] false at `[14]`, the problem's solution answers `True`
- `qwen2.5-coder-1.5b-r0hf-v3/mbpp_855__check_Even_Parity`: ensures[0] false at `[8]`, the problem's solution answers `False`
- `qwen3.8-27b-fp8-v3/mbpp_179__is_num_keith`: ensures[0] false at `[0]`, the problem's solution answers `True`
- `qwen3.8-27b-fp8-v3/mbpp_195__first`: ensures[1] false at `[[-1, 0, 0, 2, 2, 3, 5, 8, 8], 3, 0]`, the problem's solution answers `-1`
- `qwen3.8-27b-fp8-v3-s2/mbpp_908__find_fixed_point`: ensures[1] false at `[[-10, -6, 2, 7, 14, 84, 96, 100], 2]`, the problem's solution answers `-1`
- `student-r4-v3/mbpp_768__check_Odd_Parity`: ensures[0] false at `[23]`, the problem's solution answers `False`
- `student-r5-v3/mbpp_768__check_Odd_Parity`: ensures[0] false at `[17]`, the problem's solution answers `False`
- `student-r6-g/mbpp_768__check_Odd_Parity`: ensures[0] false at `[26]`, the problem's solution answers `True`
- `student-r6-v3/mbpp_768__check_Odd_Parity`: ensures[0] false at `[3]`, the problem's solution answers `False`
