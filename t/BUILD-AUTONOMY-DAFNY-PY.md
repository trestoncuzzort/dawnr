# Built and run: dafny-py

Each task's proven lowering, compiled with its own toolchain and run on up to 40 domain points; every result compared with t's interpreter (t/build.py).

- tasks: 25; built and run: 20; agree on every point: 20; agree on every point inside int32 and differ only beyond it: 0; disagree: 0; points run: 794

| task | status | points | first disagreement |
|---|---|---|---|
| aabb_overlap | agrees | 40 |  |
| all_in_range | agrees | 40 |  |
| arm_check | agrees | 40 |  |
| battery_level | agrees | 40 |  |
| clamp_cmd | not built: parameter type 'float' |  |  |
| crosstrack_side | agrees | 40 |  |
| debounce | agrees | 40 |  |
| first_fault | agrees | 40 |  |
| geofence_box | not built: parameter type 'float' |  |  |
| grid_cell | agrees | 34 |  |
| heading_diff | agrees | 40 |  |
| low_pass_step | agrees | 40 |  |
| mode_transition | agrees | 40 |  |
| nearest_index | agrees | 40 |  |
| peak_reading | agrees | 40 |  |
| pid_step | not built: parameter type 'float' |  |  |
| readings_in_band | agrees | 40 |  |
| sample_push | agrees | 40 |  |
| saturate_all | agrees | 40 |  |
| stop_distance_ok | agrees | 40 |  |
| throttle_limit | agrees | 40 |  |
| ttc_alert | not built: parameter type 'float' |  |  |
| vote3 | not built: parameter type 'float' |  |  |
| waypoint_advance | agrees | 40 |  |
| zero_fill | agrees | 40 |  |
