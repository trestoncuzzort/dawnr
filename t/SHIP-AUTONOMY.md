# Shipped at machine width

Each routine's C lowering proved with WP's machine-integer model and `-wp-rte`, so every signed operation owes a no-overflow proof (t/ship.py). Where an overflow guard is open for the full range, the largest bound ±2^k on every int input and sequence element (lengths at most 1000) under which every goal proves is the routine's proved operating envelope.

- ships for every int32 input: 16
- ships within an envelope: 5
- no envelope found: 2
- contract open at machine width: 1
- not shipped (the C lowering refuses it): 1

| task | status | goals at full width (before inference) | bounds inferred and proved (R4c) | open goals at full width |
|---|---|---|---|---|
| aabb_overlap | ships within ±2^29 | 13/17 |  | typed_aabb_overlap_t_assert_rte_signed_overflow_2, typed_aabb_overlap_t_assert_rte_signed_overflow_4, typed_aabb_overlap_t_assert_rte_signed_overflow_6, typed_aabb_overlap_t_assert_rte_signed_overflow_8 |
| all_in_range | ships for every int32 input | 17/17 |  |  |
| arm_check | ships for every int32 input | 5/5 |  |  |
| battery_level | ships for every int32 input | 11/11 |  |  |
| clamp_cmd | ships for every int32 input | 9/9 |  |  |
| crosstrack_side | ships within ±2^14 | 9/23 |  | typed_crosstrack_side_t_assert_rte_signed_overflow, typed_crosstrack_side_t_assert_rte_signed_overflow_10, typed_crosstrack_side_t_assert_rte_signed_overflow_11, typed_crosstrack_side_t_assert_rte_signed_overflow_12, typed_crosstrack_side_t_assert_rte_signed_overflow_13, typed_crosstrack_side_t_assert_rte_signed_overflow_14 |
| debounce | ships within ±2^30 | 9/10 |  | typed_debounce_t_assert_rte_signed_overflow |
| first_fault | ships for every int32 input | 20/20 |  |  |
| geofence_box | ships for every int32 input | 5/5 |  |  |
| grid_cell | no envelope found (open even at ±2^4) | 30/33 |  | typed_grid_cell_t_assert_rte_signed_overflow_10, typed_grid_cell_t_assert_rte_signed_overflow_20, typed_grid_cell_t_ensures |
| heading_diff | ships for every int32 input | 17/17 |  |  |
| low_pass_step | no envelope found (open even at ±2^4) | 20/28 |  | typed_low_pass_step_t_assert_rte_signed_overflow, typed_low_pass_step_t_assert_rte_signed_overflow_17, typed_low_pass_step_t_assert_rte_signed_overflow_18, typed_low_pass_step_t_assert_rte_signed_overflow_2, typed_low_pass_step_t_assert_rte_signed_overflow_3, typed_low_pass_step_t_assert_rte_signed_overflow_4 |
| mode_transition | ships for every int32 input | 11/11 |  |  |
| nearest_index | ships for every int32 input | 20/20 |  |  |
| peak_reading | ships for every int32 input | 22/22 |  |  |
| pid_step | not shipped: the contract is open at machine width | 12/15 |  | typed_pid_step_t_assert_3, typed_pid_step_t_ensures_2, typed_pid_step_t_ensures_3 |
| readings_in_band | not shipped: the C lowering refuses it |  |  |  |
| sample_push | ships for every int32 input | 12/12 |  |  |
| saturate_all | ships for every int32 input | 38/38 |  |  |
| stop_distance_ok | ships within ±2^14 | 7/10 |  | typed_stop_distance_ok_t_assert_rte_signed_overflow_2, typed_stop_distance_ok_t_assert_rte_signed_overflow_4, typed_stop_distance_ok_t_assert_rte_signed_overflow_6 |
| throttle_limit | ships within ±2^29 | 20/22 |  | typed_throttle_limit_t_assert_rte_signed_overflow, typed_throttle_limit_t_assert_rte_signed_overflow_6 |
| ttc_alert | ships for every int32 input | 7/7 |  |  |
| vote3 | ships for every int32 input | 11/11 |  |  |
| waypoint_advance | ships for every int32 input | 10/10 |  |  |
| zero_fill | ships for every int32 input | 20/20 |  |  |
