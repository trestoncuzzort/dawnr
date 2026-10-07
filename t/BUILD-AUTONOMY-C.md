# Built and run: c

Each task's proven lowering, compiled with its own toolchain and run on up to 40 domain points; every result compared with t's interpreter (t/build.py).

- tasks: 25; built and run: 24; agree on every point: 16; agree on every point inside int32 and differ only beyond it: 6; disagree: 2; points run: 954

| task | status | points | first disagreement |
|---|---|---|---|
| aabb_overlap | agrees | 40 |  |
| all_in_range | agrees within int32 | 40 | {"input": {"s": [0], "lo": 0, "hi": 2147483648}, "expected": "1", "got": "0"} |
| arm_check | agrees | 40 |  |
| battery_level | agrees within int32 | 40 | {"input": {"mv": 2147483648}, "expected": "3", "got": "0"} |
| clamp_cmd | agrees | 40 |  |
| crosstrack_side | agrees | 40 |  |
| debounce | agrees within int32 | 40 | {"input": {"count": 2147483647, "raw": true, "threshold": 2147483648}, "expected": "2147483648", "got": "-2147483648"} |
| first_fault | agrees within int32 | 40 | {"input": {"s": [1], "limit": 2147483648}, "expected": "1", "got": "0"} |
| geofence_box | agrees | 40 |  |
| grid_cell | agrees | 34 |  |
| heading_diff | agrees | 40 |  |
| low_pass_step | agrees | 40 |  |
| mode_transition | agrees | 40 |  |
| nearest_index | agrees | 40 |  |
| peak_reading | agrees | 40 |  |
| pid_step | agrees | 40 |  |
| readings_in_band | not built: the lowering refuses it |  |  |
| sample_push | agrees within int32 | 40 | {"input": {"buf": [0], "head": 0, "x": 2147483648}, "expected": "0 \| 2147483648", "got": "0 \| -2147483648"} |
| saturate_all | agrees within int32 | 40 | {"input": {"cmd": [65], "lim": 2147483648}, "expected": "1 \| 65", "got": "1 \| -2147483648"} |
| stop_distance_ok | DISAGREES | 40 | {"input": {"v": 3, "decel": 1000000, "dist": 1000000}, "expected": "1", "got": "0"} |
| throttle_limit | DISAGREES | 40 | {"input": {"cmd": -1, "prev": 0, "max_step": 2147483648}, "expected": "-1", "got": "-2147483648"} |
| ttc_alert | agrees | 40 |  |
| vote3 | agrees | 40 |  |
| waypoint_advance | agrees | 40 |  |
| zero_fill | agrees | 40 |  |
