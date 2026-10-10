# PX4's own statements against the t findings and fixes

Each handler's lines, cut verbatim from PX4's source at the pinned commit (`original`) and at the fix's commit on the pull request's branch (`fixed`), compiled with stand-ins for the surrounding names only, and run at every input; t's interpreter runs the finding (original) or the fix at the same input (t/flight/px4_stmt.py). x86-64, GCC.

| PR | code | t task | commit | PX4 lines | inputs | agree | at the real input, PX4 gives |
|---|---|---|---|---|---|---|---|
| #29036 | original | px4_arm_param_any | dd804e4b9c49 | 1 | 89 | 89 | 1 at 257 |
| #29036 | fixed | px4_arm_param_fixed | 96d9bbbb1e9a | 3 | 89 | 89 | -1 at 257 |
| #29036 | original | px4_set_mode_field_any | dd804e4b9c49 | 1 | 92 | 92 | 8 at 264 |
| #29036 | fixed | px4_set_mode_field_fixed | 96d9bbbb1e9a | 15 | 92 | 92 | -1 at 264 |
| #29033 | original | px4_request_event_any | dd804e4b9c49 | 18 | 77 | 77 | 41 at (0, 40, 20) |
| #29033 | fixed | px4_request_event_fixed | 0e222f30c7f3 | 34 | 77 | 77 | 20 at (0, 40, 20) |
| #29039 | original | px4_fusion_source_any | df387bdec263 | 30 | 90 | 90 | 0 at 256 |
| #29039 | fixed | px4_fusion_source_fixed | 484d183bc959 | 42 | 90 | 90 | -1 at 256 |
| #29034 | original | px4_stream_interval_any | dd804e4b9c49 | 1 | 46 | 46 | -2147483648 at 2147483648 |
| #29034 | fixed | px4_stream_interval_fixed | 997da58b2d7b | 2 | 46 | 46 | 2147483647 at 2147483648 |
| #29035 | original | px4_do_jump_index_any | dd804e4b9c49 | 6 | 95 | 95 | 3 at 65539 |
| #29035 | fixed | px4_do_jump_index_fixed | 1ef387249e11 | 20 | 95 | 95 | -1 at 65539 |
| #29032 | original | px4_serial_control_any | dd804e4b9c49 | 7 | 256 | 256 | -1 at 71 |
| #29032 | fixed | px4_serial_control_fixed | 9106bf6b81cb | 7 | 256 | 256 | 0 at 71 |
