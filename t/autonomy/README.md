# The autonomy suite

NORTH-STAR.md's target 2: routines of the kind a navigation, guidance and control stack is made of, each written
once in t with a contract a reviewer would accept, and checked the way every t task is. A kernel's cell counts only
when it proves the routine and refutes the routine's twin, a one-edit mutant, with a certificate at a measured
input. The table is `t/AUTONOMY.md`, regenerated from a clean clone like `t/AGREEMENT.md`.

The routines use what the language carries since 2026-10-07: IEEE doubles (SPEC.md "Floats (v1)"), arrays written in
place (SPEC.md "Heap (v1)") and parallel loops whose race freedom is checked by rule (SPEC.md "Concurrency (v1)").
A float routine can be proved where floats are lowered (SPARK, Frama-C); an array routine in Dafny and Frama-C natively
and in the other five by copy-in/copy-out (PREDICT T53); an integer routine in all seven kernels.

| routine | what it stands for | constructs |
|---|---|---|
| geofence_box | the vehicle inside an axis-aligned keep-in box | float |
| vote3 | 2-of-3 sensor voting: the median of three redundant readings | float |
| clamp_cmd | an actuator command clamped to its limits | float |
| ttc_alert | a time-to-collision warning from range and closing speed | float |
| pid_step | a PI controller's output, saturated to the actuator range | float |
| waypoint_advance | step to the next waypoint once inside the acceptance radius | int |
| debounce | a fault flag raised only after `threshold` consecutive bad samples | int, bool |
| battery_level | battery voltage to a coarse state of charge | int |
| readings_in_band | how many samples of a window are within limits | seq, comprehension |
| first_fault | the first sample over a limit (an early exit) | seq, break |
| sample_push | a ring buffer's write, wrapping the head | array |
| saturate_all | every command in a buffer saturated, in parallel | array, parallel for |
| heading_diff | the shortest signed turn between two headings, in (-180, 180] | int, mod |
| low_pass_step | a fixed-point first-order low-pass filter step, between the old value and the sample | int, div |
| aabb_overlap | two axis-aligned bounding boxes intersect (collision check) | int |
| peak_reading | the peak of a non-empty window | seq |
| all_in_range | every sample of a window within limits | seq |
| arm_check | the preflight arming condition | int, bool |
| mode_transition | a flight-mode state machine: forward one step, or abort | int |
| grid_cell | a position's cell in an occupancy grid | int, div |
| zero_fill | a buffer cleared, in parallel | array, parallel for |
| crosstrack_side | which side of a path segment a point is on (the cross product's sign) | int |
| stop_distance_ok | the vehicle can stop within the distance: v^2 <= 2 a d | int |
| nearest_index | the nearest obstacle in a range scan | seq |
| throttle_limit | a command rate-limited against the previous one | int |

The matrix (`t/tasks/`) holds three more float routines of the same kind: sat_scale, deadband and rate_limit.
