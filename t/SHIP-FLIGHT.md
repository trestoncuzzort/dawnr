# Shipped at machine width

Each routine's C lowering proved with WP's machine-integer model and `-wp-rte`, so every signed operation owes a no-overflow proof (t/ship.py). Where an overflow guard is open for the full range, the largest bound ±2^k on every int input and sequence element (lengths at most 1000) under which every goal proves is the routine's proved operating envelope.

- ships for every int32 input: 18
- ships within an envelope: 4
- no envelope found: 1
- contract open at machine width: 4
- not shipped (the C lowering refuses it): 0

| task | status | goals at full width (before inference) | bounds inferred and proved (R4c) | open goals at full width |
|---|---|---|---|---|
| px4_alpha_update | ships for every int32 input | 11/11 |  |  |
| px4_constrain | ships for every int32 input | 9/9 |  |  |
| px4_constrain_f | ships for every int32 input | 9/9 |  |  |
| px4_hysteresis_holds | ships within ±2^21 | 22/23 | -(i * 2097152) <= last_change; -(last_change * 2097152) <= i; -(news_n * 2097152) <= i; -(news_n * 2097152) <= last_change; -(time_from_false * 2097152) <= i; -(time_from_false * 2097152) <= last_change; -(time_from_true * 2097152) <= i; -(time_from_true * 2097152) <= last_change; -(times_n * 2097152) <= i; -(times_n * 2097152) <= last_change; 0 <= i; 0 <= last_change; i <= news_n; i <= news_n * 2097152; i <= time_from_false * 2097152; i <= times_n; i <= times_n * 2097152; last_change <= i * 2097152; last_change <= news_n * 2097152; last_change <= time_from_false * 2097152; last_change <= times_n * 2097152 | typed_px4_hysteresis_holds_t_assert_rte_signed_overflow_4 |
| px4_hysteresis_set | ships within ±2^29 | 19/21 |  | typed_px4_hysteresis_set_t_assert_rte_signed_overflow_2, typed_px4_hysteresis_set_t_assert_rte_signed_overflow_4 |
| px4_hysteresis_switches | ships for every int32 input | 23/23 |  |  |
| px4_hysteresis_update | ships within ±2^29 | 12/14 |  | typed_px4_hysteresis_update_t_assert_rte_signed_overflow_2, typed_px4_hysteresis_update_t_assert_rte_signed_overflow_4 |
| px4_interp_index | ships for every int32 input | 20/20 |  |  |
| px4_interpolate | not shipped: the contract is open at machine width | 19/23 |  | typed_px4_interpolate_t_assert_5, typed_px4_interpolate_t_assert_6, typed_px4_interpolate_t_assert_7, typed_px4_interpolate_t_assert_8 |
| px4_is_in_range | ships for every int32 input | 7/7 |  |  |
| px4_lerp | not shipped: the contract is open at machine width | 12/14 |  | typed_px4_lerp_t_assert_2, typed_px4_lerp_t_assert_4 |
| px4_max | ships for every int32 input | 6/6 |  |  |
| px4_max3 | ships for every int32 input | 8/8 |  |  |
| px4_min | ships for every int32 input | 6/6 |  |  |
| px4_min3 | ships for every int32 input | 8/8 |  |  |
| px4_negate_i16 | ships for every int32 input | 10/10 |  |  |
| px4_rb_pop_front | ships for every int32 input | 37/37 |  |  |
| px4_rb_push_back | ships for every int32 input | 37/37 |  |  |
| px4_rb_space_available | ships for every int32 input | 14/14 |  |  |
| px4_sign | ships for every int32 input | 10/10 |  |  |
| px4_sign_from_bool | ships for every int32 input | 6/6 |  |  |
| px4_sign_no_zero | ships for every int32 input | 9/9 |  |  |
| px4_slew_update | not shipped: the contract is open at machine width | 15/16 |  | typed_px4_slew_update_t_assert_3 |
| px4_sq | ships within ±2^15 | 6/7 |  | typed_px4_sq_t_assert_rte_signed_overflow_2 |
| px4_wrap_bin | not shipped: the contract is open at machine width | 23/24 |  | typed_px4_wrap_bin_t_ensures_2 |
| px4_wrap_bin_72 | ships for every int32 input | 24/24 |  |  |
| px4_wrap_int | no envelope found (open even at ±2^4) | 43/50 |  | typed_px4_wrap_int_t_assert_rte_signed_overflow_15, typed_px4_wrap_int_t_assert_rte_signed_overflow_17, typed_px4_wrap_int_t_assert_rte_signed_overflow_2, typed_px4_wrap_int_t_assert_rte_signed_overflow_21, typed_px4_wrap_int_t_assert_rte_signed_overflow_4, typed_px4_wrap_int_t_ensures |
