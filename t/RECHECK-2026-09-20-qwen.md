# The answers one kernel from clean, re-run alone, 2026-09-20 19:28Z

`t/recheck_near.py --only timeout --flake 3`. 24 cells, each the single
kernel that kept an otherwise-clean answer out, re-run by itself instead of beside 31 others.

- **changed their mind: 2** (now verified with the twin refuted)
- held their verdict: 22
- could not be run here: 0

## Changed their mind

| kernel | answer set | task | was | seconds alone |
|---|---|---|---|---|
| `framac` | qwen2.5-coder-14b-apps-s1 | `apps_2503__findLUSlength` | timeout / refuted | 16.5 |
| `lean` | qwen2.5-coder-14b-he-s4 | `he_42__incr_list` | verified / timeout | 1.6 |

These 2 answers are clean: their tests pass and all seven now verify them
with the twin refuted. The flip is recorded in `t/out/recheck.json`, which `t/preflight.py`
reads; no kernels.md was edited.

## Held their verdict

| kernel | task | was | now | seconds |
|---|---|---|---|---|
| `spark` | `mbpp_565__split` | verified / timeout | verified / timeout | 21.2 |
| `spark` | `apps_2705__generate_integers` | timeout / refuted | timeout / refuted | 20.4 |
| `spark` | `he_60__sum_to_n` | timeout / refuted | timeout / refuted | 4.7 |
| `framac` | `mbpp_503__add_consecutive_nums` | verified / timeout | verified / timeout | 5.6 |
| `lean` | `mbpp_578__interleave_lists` | timeout / timeout | timeout / timeout | 188.0 |
| `framac` | `mbpp_690__mul_consecutive_nums` | verified / timeout | verified / timeout | 6.0 |
| `framac` | `mbpp_865__ntimes_list` | verified / timeout | verified / timeout | 5.0 |
| `framac` | `mbpp_503__add_consecutive_nums` | verified / timeout | verified / timeout | 6.1 |
| `framac` | `mbpp_690__mul_consecutive_nums` | verified / timeout | verified / timeout | 6.7 |
| `lean` | `mbpp_824__remove_even` | timeout / refuted | timeout / refuted | 55.7 |
| `framac` | `mbpp_503__add_consecutive_nums` | verified / timeout | verified / timeout | 5.6 |
| `framac` | `mbpp_690__mul_consecutive_nums` | verified / timeout | verified / timeout | 5.3 |
| `framac` | `mbpp_690__mul_consecutive_nums` | verified / timeout | verified / timeout | 6.2 |
| `framac` | `mbpp_345__diff_consecutivenums` | verified / timeout | verified / timeout | 5.3 |
| `lean` | `mbpp_804__is_Product_Even` | verified / timeout | verified / timeout | 148.8 |
| `framac` | `mbpp_345__diff_consecutivenums` | verified / timeout | verified / timeout | 6.2 |
| `framac` | `mbpp_503__add_consecutive_nums` | verified / timeout | verified / timeout | 6.0 |
| `lean` | `mbpp_578__interleave_lists` | timeout / timeout | timeout / timeout | 190.3 |
| `spark` | `mbpp_935__series_sum` | timeout / refuted | timeout / refuted | 5.8 |
| `lean` | `mbpp_804__is_Product_Even` | verified / timeout | verified / timeout | 145.4 |
| `framac` | `mbpp_503__add_consecutive_nums` | verified / timeout | verified / timeout | 5.5 |
| `rocq` | `mbpp_680__increasing_trend` | timeout / refuted | timeout / refuted | 182.2 |

For these the outcome is a real cost, not a scheduling artifact.

