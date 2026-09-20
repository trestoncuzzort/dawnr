# The answers one kernel from clean, re-run alone, 2026-09-19 09:29Z

`t/recheck_near.py --only unproved --flake 1`. 26 cells, each the single
kernel that kept an otherwise-clean answer out, re-run by itself instead of beside 31 others.

- **changed their mind: 17** (now verified with the twin refuted)
- held their verdict: 9
- could not be run here: 0

## Changed their mind

| kernel | answer set | task | was | seconds alone |
|---|---|---|---|---|
| `lean` | qwen2.5-coder-14b-v3-s1 | `mbpp_557__toggle_string` | unproved / refuted | 0.0 |
| `lean` | qwen2.5-coder-14b-v3-s1 | `mbpp_852__remove_negs` | unproved / refuted | 0.0 |
| `lean` | qwen2.5-coder-14b-v3-s3 | `mbpp_557__toggle_string` | unproved / refuted | 0.0 |
| `lean` | qwen2.5-coder-14b-v3-s4 | `mbpp_412__remove_odd` | unproved / refuted | 0.0 |
| `lean` | qwen2.5-coder-14b-v3-s4 | `mbpp_41__filter_evennumbers` | unproved / refuted | 0.0 |
| `lean` | qwen2.5-coder-14b-v3-s4 | `mbpp_824__remove_even` | unproved / refuted | 12.1 |
| `lean` | qwen2.5-coder-14b-v3-s5 | `mbpp_412__remove_odd` | unproved / refuted | 16.6 |
| `lean` | qwen2.5-coder-14b-v3-s5 | `mbpp_557__toggle_string` | unproved / refuted | 2.7 |
| `lean` | qwen2.5-coder-14b-v3-s6 | `mbpp_825__access_elements` | unproved / refuted | 11.1 |
| `lean` | qwen2.5-coder-14b-v3-s7 | `mbpp_557__toggle_string` | unproved / refuted | 4.4 |
| `lean` | qwen2.5-coder-14b-v3-s8 | `mbpp_825__access_elements` | unproved / refuted | 11.1 |
| `lean` | qwen3.8-27b-fp8-v3 | `mbpp_557__toggle_string` | unproved / refuted | 7.0 |
| `lean` | qwen3.8-27b-fp8-v3 | `mbpp_62__smallest_num` | verified / unproved | 0.0 |
| `lean` | qwen3.8-27b-fp8-v3 | `mbpp_718__alternate_elements` | unproved / refuted | 3.2 |
| `lean` | qwen3.8-27b-fp8-v3 | `mbpp_825__access_elements` | unproved / refuted | 11.5 |
| `lean` | qwen3.8-27b-fp8-v3-s2 | `mbpp_226__odd_values_string` | unproved / refuted | 3.6 |
| `lean` | qwen3.8-27b-fp8-v3-s2 | `mbpp_825__access_elements` | unproved / refuted | 10.4 |

These 17 answers are clean: their tests pass and all seven now verify them
with the twin refuted. The flip is recorded in `t/out/recheck.json`, which `t/preflight.py`
reads; no kernels.md was edited.

## Held their verdict

| kernel | task | was | now | seconds |
|---|---|---|---|---|
| `lean` | `mbpp_913__end_num` | unproved / refuted | unproved / refuted | 0.0 |
| `lean` | `mbpp_913__end_num` | unproved / refuted | unproved / refuted | 0.0 |
| `lean` | `mbpp_913__end_num` | unproved / refuted | unproved / refuted | 0.0 |
| `lean` | `mbpp_913__end_num` | unproved / refuted | unproved / refuted | 0.0 |
| `lean` | `apps_2415__searchInsert` | verified / unproved | verified / unproved | 0.1 |
| `lean` | `mbpp_736__left_insertion` | unproved / unproved | unproved / unproved | 0.1 |
| `lean` | `mbpp_890__find_Extra` | verified / unproved | verified / unproved | 0.0 |
| `lean` | `mbpp_641__is_nonagonal` | unproved / refuted | unproved / refuted | 0.4 |
| `lean` | `mbpp_913__end_num` | unproved / refuted | unproved / refuted | 0.0 |

For these the outcome is a real cost, not a scheduling artifact.

