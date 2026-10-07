# Built and run: c64

Each task's proven lowering, compiled with its own toolchain and run on up to 40 domain points; every result compared with t's interpreter (t/build.py).

- tasks: 25; built and run: 24; agree on every point: 23; agree on every point inside int32 and differ only beyond it: 1; disagree: 0; points run: 954

| task | status | points | first disagreement |
|---|---|---|---|
| aabb_overlap | agrees | 40 |  |
| all_in_range | agrees | 40 |  |
| arm_check | agrees | 40 |  |
| battery_level | agrees | 40 |  |
| clamp_cmd | agrees | 40 |  |
| crosstrack_side | agrees | 40 |  |
| debounce | agrees | 40 |  |
| first_fault | agrees | 40 |  |
| geofence_box | agrees | 40 |  |
| grid_cell | agrees | 34 |  |
| heading_diff | agrees | 40 |  |
| low_pass_step | agrees | 40 |  |
| mode_transition | agrees | 40 |  |
| nearest_index | agrees | 40 |  |
| peak_reading | agrees | 40 |  |
| pid_step | agrees | 40 |  |
| readings_in_band | not built: the lowering refuses it |  |  |
| sample_push | agrees | 40 |  |
| saturate_all | agrees | 40 |  |
| stop_distance_ok | agrees within int32 | 40 | {"input": {"v": 0, "decel": 2147483648, "dist": 2147483648}, "expected": "1", "got": "0"} |
| throttle_limit | agrees | 40 |  |
| ttc_alert | agrees | 40 |  |
| vote3 | agrees | 40 |  |
| waypoint_advance | agrees | 40 |  |
| zero_fill | agrees | 40 |  |
