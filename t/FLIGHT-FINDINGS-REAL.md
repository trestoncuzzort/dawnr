# PX4 findings refuted at real inputs

Each finding's own body, at the input a real PX4 message or buffer carries (t/flight/findings/real_inputs.json), lowered with its refutation certificate in every kernel (t/refute_at.py). REFUTED means the kernel accepted the certificate.

| finding | input | kind | dafny | verus | spark | framac | lean | rocq | fstar | refuted |
|---|---|---|---|---|---|---|---|---|---|---|
| px4_wrap_bin_any | a bin one past a full turn below zero; PX4 returns -1 | value | refuted | refuted | refuted | refuted | refuted | refuted | refuted | 7/7 |
| px4_sumd_receive_any | PX4's 64-byte buffer and a valid 32-channel frame | undefined | refuted | refuted | refuted | refuted | refuted | refuted | refuted | 7/7 |
| px4_request_event_any | a request for events 0..40 against PX4's default 20-event buffer | value | refuted | refuted | refuted | refuted | refuted | refuted | refuted | 7/7 |
| px4_arm_param_any | COMPONENT_ARM_DISARM param1 = 257 | value | refuted | refuted | refuted | refuted | refuted | refuted | refuted | 7/7 |
| px4_stream_interval_any | a requested interval of 2^31 us, about 36 minutes | value | refuted | refuted | refuted | refuted | refuted | refuted | refuted | 7/7 |
| px4_serial_control_any | a SERIAL_CONTROL message whose count, 71, exceeds its 70-byte data field | undefined | refuted | refuted | refuted | refuted | refuted | refuted | refuted | 7/7 |
| px4_do_jump_index_any | a DO_JUMP item with param1 = 65539, stored as a jump to item 3 | value | refuted | refuted | refuted | refuted | refuted | refuted | refuted | 7/7 |
| px4_set_mode_field_any | a DO_SET_MODE base mode of 264, narrowed to mode 8 | value | refuted | refuted | refuted | refuted | refuted | refuted | refuted | 7/7 |
| px4_obstacle_body_any | a body-frame OBSTACLE_DISTANCE message at a 1 degree increment: 360 steps over 72 distances | undefined | timeout | refuted | refuted | refuted | unproved | refuted | refuted | 5/7 |
| px4_fusion_source_any | ESTIMATOR_SENSOR_ENABLE with source 256, narrowed to GPS | value | refuted | refuted | refuted | refuted | refuted | refuted | refuted | 7/7 |
