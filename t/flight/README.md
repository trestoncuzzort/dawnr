# PX4 flight code in t

These tasks restate functions from [PX4-Autopilot](https://github.com/PX4/PX4-Autopilot), an open-source autopilot
for drones and other vehicles. PX4 is licensed under the BSD 3-Clause License; a copy is in `LICENSE-PX4`. Each body
follows PX4's code at commit `dd804e4b9c490aed051bb36f8d3fca1ee137be2a` statement by statement. PX4 ships no
formal contracts, so every `requires` and `ensures` here is this repository's, and `t/audit.py` reads zero survivors
on each: every one-edit change to a body is caught.

PX4's functions are C++ templates. The integer ones are stated over t's integers and compared at `int64_t`. The float
ones are stated over t's `float`, IEEE binary64, and compared at `double`; PX4 flies most of them at `float`, binary32.

| t task | PX4 function | file:line | instantiation compared |
|---|---|---|---|
| px4_constrain | `math::constrain` | src/lib/mathlib/math/Limits.hpp:111 | int64_t |
| px4_min | `math::min(a, b)` | src/lib/mathlib/math/Limits.hpp:69 | int64_t |
| px4_max | `math::max(a, b)` | src/lib/mathlib/math/Limits.hpp:90 | int64_t |
| px4_min3 | `math::min(a, b, c)` | src/lib/mathlib/math/Limits.hpp:84 | int64_t |
| px4_max3 | `math::max(a, b, c)` | src/lib/mathlib/math/Limits.hpp:105 | int64_t |
| px4_is_in_range | `math::isInRange` | src/lib/mathlib/math/Limits.hpp:133 | int64_t |
| px4_sign_no_zero | `math::signNoZero` | src/lib/mathlib/math/Functions.hpp:52 | int64_t |
| px4_sign | `matrix::sign` | src/lib/matrix/matrix/helper_functions.hpp:147 | int64_t |
| px4_sign_from_bool | `math::signFromBool` | src/lib/mathlib/math/Functions.hpp:63 | bool |
| px4_sq | `math::sq` | src/lib/mathlib/math/Functions.hpp:69 | int64_t |
| px4_negate_i16 | `math::negate<int16_t>` | src/lib/mathlib/math/Functions.hpp:258 | int16_t |
| px4_wrap_int | `matrix::wrap` (integer) | src/lib/matrix/matrix/helper_functions.hpp:83 | int64_t |
| px4_interp_index | the index search of `math::interpolateNXY` | src/lib/mathlib/math/Functions.hpp:201 | not compared (internal) |
| px4_constrain_f | `math::constrain` | src/lib/mathlib/math/Limits.hpp:111 | double |
| px4_lerp | `math::lerp` | src/lib/mathlib/math/Functions.hpp:245 | double |
| px4_interpolate | `math::interpolate` | src/lib/mathlib/math/Functions.hpp:152 | double |
| px4_slew_update | `SlewRate::update` | src/lib/slew_rate/SlewRate.hpp:79 | double, `dt` as PX4's `float` |
| px4_alpha_update | `AlphaFilter::updateCalculation` | src/lib/mathlib/math/filter/AlphaFilter.hpp:169 | double, `alpha` as PX4's `float` |
| px4_hysteresis_update | `systemlib::Hysteresis::update` | src/lib/hysteresis/hysteresis.cpp:75 | the class, `hrt_abstime` = uint64_t |
| px4_hysteresis_set | `systemlib::Hysteresis::set_state_and_update` | src/lib/hysteresis/hysteresis.cpp:60 | the class, `hrt_abstime` = uint64_t |
| px4_hysteresis_holds | a default `Hysteresis` driven by `set_state_and_update` over a sample sequence | src/lib/hysteresis/hysteresis.cpp:60 | the class |
| px4_hysteresis_switches | the same, with every request `true` | src/lib/hysteresis/hysteresis.cpp:60 | the class |
| px4_wrap_bin | `ObstacleMath::wrap_bin` | src/lib/collision_prevention/ObstacleMath.cpp:120 | int |
| px4_wrap_bin_72 | `ObstacleMath::wrap_bin(bin, BIN_COUNT)`, as `CollisionPrevention` calls it | src/lib/collision_prevention/ObstacleMath.cpp:120 | int, `BIN_COUNT` = 72 |
| px4_rb_space_available | `Ringbuffer::space_available` | src/lib/ringbuffer/Ringbuffer.cpp:65 | the class, `size_t` |
| px4_rb_push_back | `Ringbuffer::push_back`: its result and `_end` | src/lib/ringbuffer/Ringbuffer.cpp:87 | the class, `size_t` |
| px4_rb_pop_front | `Ringbuffer::pop_front`: its result and `_start` | src/lib/ringbuffer/Ringbuffer.cpp:134 | the class, `size_t` |

**Transcription notes.**
- `matrix::wrap`'s local `range` is named `rng` here; `range` is an Ada keyword, and the renamed form collides with
  SPARK's emitted package.
- `matrix::sign` and `math::signNoZero` subtract two C++ booleans; t has no boolean arithmetic, so each comparison
  sets an int to 1 or 0 first.
- The integer `wrap` uses C++'s truncating `/` and `%` where t's are Euclidean. The operands there are never
  negative (`low - x > 0` on the branch that divides, `x - low >= 0` after it), and on non-negative operands the
  two agree.
- `interpolateNXY` evaluates `value > x[index + 1]` before `index < N - 2`, as here; `x[index + 1]` is always
  defined because the loop keeps `index <= N - 2`.
- `px4_interpolate` requires `x_high - x_low >= 1` over inputs within ±1000. PX4 states neither, but t's floats are
  defined only when finite, and a small gap can overflow the slope `(y_high - y_low) / (x_high - x_low)`. The bound
  is what this proof covers; stating it is part of the finding.
- `SlewRate<double>::update` takes `dt` as `float`, and `AlphaFilter<double>` stores `alpha` as a `float` member, so
  PX4 narrows both to binary32 before use.
- `Hysteresis` is a class: `_state`, `_requested_state`, `_last_time_to_change_state` and the two hysteresis times are
  its fields. The step tasks take the fields as parameters and return `_state` afterwards, which is what
  `get_state()` reads; `set_state_and_update` calls `update` at its end, and the task inlines that call. The two
  trace tasks drive a default-constructed `Hysteresis` (`_state` false) through `set_state_and_update` once per
  sample, the way commander and the land detector call it. The loop is the driver, and its body is PX4's.
  The driver reads `holds`' requests from a seq of ints, nonzero for `true`, because `seq<bool>` is not
  lowered in five of the seven kernels yet; PX4's `set_state_and_update` receives a `bool` either way.
  `holds` says the state never turns true while every sample is within `time_from_false` of the first. `switches`
  says it is true at the end once a `true` request has held across `time_from_false`.
- `hrt_abstime` is `uint64_t`; the tasks require the times non-negative, as an unsigned type is. The harness reaches
  each step's starting fields through PX4's public methods alone (its comment says how). It never writes a private
  field.

- `Ringbuffer` is the byte queue under `VariableLengthRingbuffer`, which buffers MAVLink's outgoing messages
  (src/modules/mavlink/mavlink_main.h:687). Its state is `_start`, `_end` and `_size`, and the tasks take them as
  parameters. Their `requires` is the class invariant the methods keep: both indices in `[0, _size]`, with `_size`
  standing for 0 after a wrap, and at most `_size - 1` bytes in use. The tasks restate the index arithmetic. The
  `memcpy` calls move bytes and touch no index, so they are left out; `push_back`'s null check is too, since every
  caller here passes a buffer. Where PX4 returns early, the task does (`return`). Each task returns what PX4 returns,
  paired with the index PX4 updates. The harness builds PX4 with `private` defined as `public` (access only) to set a
  state and read the index back.
- `wrap_bin` returns `(bin + bin_count) % bin_count` on C++ `int`s, and C++'s `%` truncates toward zero: the
  remainder takes the dividend's sign. Under `px4_wrap_bin`'s `requires`, the dividend is non-negative, and there
  C++'s `%` and t's Euclidean `%` agree. `findings/px4_wrap_bin_any` drops that `requires`, so its body spells the
  truncation out: the remainder of a negative `s` is `-((-s) % bin_count)`. The `requires` keep `bin`, `bin_count`
  and their sum inside `int`'s range.

**Contracts PX4's callers do not establish** (`findings/`). A task there restates a PX4 function with the contract
it needs, minus a `requires` that a PX4 caller does not establish. The kernels refute it, and `px4_diff.py` runs
PX4's own code at the refuting input.

| t task | PX4 function | the `requires` dropped | what PX4 returns without it |
|---|---|---|---|
| px4_wrap_bin_any | `ObstacleMath::wrap_bin` | `bin >= -bin_count` | -1 at `bin` = -73, `bin_count` = 72 |
| px4_sumd_receive_any | `sumd_decode`'s storing of channel bytes (src/lib/rc/sumd.cpp:196) | `2 * length <= len(sumd_data) - 2`, one byte of headroom the frame-length check does not leave | a write one past the buffer: `sumd_data[64]` for a valid 32-channel frame |
| px4_request_event_any | `SendProtocol::handle_request_event`'s loop (src/modules/mavlink/mavlink_events.cpp:182) | a bound on the sequences handled | 41 lookups for events 0..40 against a 20-event buffer; up to 65535 for a wrapped range |
| px4_arm_param_any | `Commander::handle_command`, COMPONENT_ARM_DISARM (src/modules/commander/Commander.cpp:1101) | narrowing only a value that fits `int8_t` | `param1` = 257 accepted as arm |
| px4_stream_interval_any | `Mavlink::configure_stream` (src/modules/mavlink/mavlink_main.cpp:1415) | a clamp before the int conversion | a negative interval (`INT_MIN` on x86) for a requested interval of 2^31 us |
| px4_serial_control_any | `MavlinkReceiver::handle_message_serial_control`, the passthrough branch (src/modules/mavlink/mavlink_receiver.cpp:2114) | `count <= len(data)`, which the shell branch of the same handler checks (line 2137) | 71 bytes handed on from the 70-byte `data` field for `count` = 71 |
| px4_do_jump_index_any | `MavlinkMissionManager::parse_mavlink_mission_item`, DO_JUMP (src/modules/mavlink/mavlink_mission.cpp:1723) | an index that fits `int16_t` | `param1` = 65539 stored as a jump to item 3 |
| px4_set_mode_field_any | `Commander::handle_command`, DO_SET_MODE (src/modules/commander/Commander.cpp:931) | a mode field that fits `uint8_t` | base mode 264 accepted as mode 8 |
| px4_fusion_source_any | `EKF2::handleSensorFusionCommand`, ESTIMATOR_SENSOR_ENABLE (src/modules/ekf2/EKF2.cpp:1059, at df387bde) | a source that fits `uint8_t` | source 256 (and NaN, MAVLink's unused value) selects GPS |
| px4_obstacle_body_any | `CollisionPrevention::_addObstacleSensorData`, the body-frame branch (src/lib/collision_prevention/CollisionPrevention.cpp:281) | `j < BIN_COUNT`, which the global-frame branch above it has | 360 reads from the 72-element `distances` at a 1 degree increment |

`wrap_bin`'s result indexes the collision-prevention obstacle map. That map is four arrays of 72 bins:
`_obstacle_map_body_frame.distances`, `_data_timestamps`, `_data_maxranges` and `_data_fov`.
`CollisionPrevention::_addDistanceSensorData` (src/lib/collision_prevention/CollisionPrevention.cpp:404) wraps every
bin from `round((yaw_deg - degrees(h_fov / 2)) / 5)` upward. A distance sensor's horizontal field of view `h_fov`
reaches that line unbounded: the MAVLink receiver copies `horizontal_fov` as sent (src/modules/mavlink/mavlink_receiver.cpp:1160).
For a forward-facing sensor, a field of view above about 12.65 rad (4π is 12.57) makes the lowest bin -73, and
`wrap_bin` then returns -1. At 30, a field of view given in degrees where radians are expected, 99 of the indices are
negative. `px4_wrap_bin` proves the result is a valid bin, congruent to `bin`, for every `bin >= -bin_count`. The contract is
PX4's own: its test `ObstacleMathTest.WrapBin` (src/lib/collision_prevention/ObstacleMathTest.cpp:184) expects a
negative bin "wrapped back to the end" (-1 to 71), and checks no bin below -72.

**Proposed fixes** (`fixes/`), filed upstream as PX4 PR #29030 (`wrap_bin`) and #29031 (SUMD). A task there restates the change proposed to PX4 for a finding, with the finding's
contract and without the `requires` PX4's callers did not establish. `px4_diff.py --fixed-tree DIR` compiles the
patched PX4 checkout's own code and runs it against the task on every domain point.

| t task | the fix | PX4 call |
|---|---|---|
| px4_wrap_bin_fixed | `wrap_bin` shifts a negative remainder back into `[0, bin_count)` | `ObstacleMath::wrap_bin(bin, bin_count)` |
| px4_wrap_bin_fixed_72 | the same, at `CollisionPrevention`'s `BIN_COUNT` = 72 | `ObstacleMath::wrap_bin(bin, 72)` |
| px4_sumd_receive_fixed | channel byte k is stored at `sumd_data[k]`, not `k + 1` | `sumd_decode` (checked by sanitizer run, below) |
| px4_request_event_fixed | sequences beyond the buffer's capacity are answered by one error, then at most `capacity` are looked up | `SendProtocol::handle_request_event` (PX4 PR #29033) |
| px4_arm_param_fixed | only a value that fits `int8_t` is narrowed | `Commander::handle_command` (PR #29036) |
| px4_stream_interval_fixed | the interval is clamped to `INT32_MAX` before conversion | `Mavlink::configure_stream` (PR #29034) |
| px4_serial_control_fixed | a `count` larger than the `data` field is not handed on | `MavlinkReceiver::handle_message_serial_control` (PR #29032) |
| px4_do_jump_index_fixed | an index outside `[0, INT16_MAX]` is rejected | `MavlinkMissionManager::parse_mavlink_mission_item` (PR #29035) |
| px4_set_mode_field_fixed | a mode field outside `(-1, 256)` is rejected | `Commander::handle_command` (PR #29036) |
| px4_fusion_source_fixed | a source, instance or enable flag its integer cannot hold is denied | `EKF2::handleSensorFusionCommand` (PR #29039) |
| px4_obstacle_body_fixed | the body-frame loop stops at the 72 distances, as the global-frame loop does | `CollisionPrevention::_addObstacleSensorData` (PR #29037) |

The SUMD pair states `sumd_decode`'s storing loop over a packet buffer of any even size. PX4's buffer is
`SUMD_MAX_CHANNELS * 2` = 64 bytes and accepts `2 <= length <= 32`. The tasks take the buffer's length as given and
store each byte's position as its value, so the contract pins where every byte lands. The interpreter finds the
out-of-bounds store at the smallest buffer, and the kernels prove the fixed loop for every size. PX4's own
`sumd.cpp` was compiled with UBSan and fed a valid 32-channel frame. It reports the write and the read at index 64,
and channel 32 decodes from the CRC byte. With the fix there are no reports and channel 32 is correct, and PX4's
recorded stream (`test_data/sumd_data.txt`, 498 frames) decodes identically before and after.

The MAVLink and commander pairs state the integer the float parameter denotes (a request for 257.0 is 257).
Each C++ conversion gets its own semantics: GCC narrows a signed integer modulo 2^8, `uint16_t` sequence arithmetic
wraps modulo 2^16, and the float-to-`int` conversion past `INT_MAX` is undefined in C++. The stream-interval
finding uses x86's actual result for it (`INT_MIN`), the case PR #29034 describes; ARM's FPU saturates instead. The
stream-interval pair also leaves out the float round trip `1e6 / (1e6 / x)`.

DO_JUMP's index is a float stored into an `int16_t`. GCC converts through a 32-bit integer and keeps the low 16
bits, so 65539 becomes 3; the pair takes `param1` within 2^24, where a float carries every integer exactly. The
SERIAL_CONTROL pair states the copy `pushFromMavlink` makes of `count` bytes from `data`. The finding reads past
`data` exactly when `count > len(data)`, and the fix hands on nothing then.

**PX4's own statements, before and after.** These handlers need a running module, so `px4_diff.py` cannot call
them. `px4_stmt.py` cuts each handler's lines verbatim from PX4's source, twice: at the pinned commit, and at the
fix's commit on the pull request's branch. It compiles them with stand-ins for the surrounding names only: the
message struct with MAVLink's field types, the enum values, and a passthrough that records what it is handed. It
then runs every input of the t task, plus the real one, read at run time so the compiler cannot fold an out-of-range
conversion. The original lines agree with the finding, and the fixed lines with the fix, at every input, in all
fourteen comparisons (`t/PX4-STMT.md`). At the real inputs, PX4's original lines arm on 257, set mode 8 on 264,
select GPS for sensor source 256, look up 41 events against a 20-event buffer, jump to item 3 on 65539, give
`INT_MIN` for 2^31 us, and read past `data` at 71. The fixed lines reject, reject, deny, look up 20, reject, clamp,
and hand on nothing. REQUEST_EVENT's stand-in buffer holds no event, so every lookup misses, the case of a request
for sequences long gone.
The results are for x86-64. On ARM, a float-to-int conversion past `INT_MAX` saturates instead of giving
`INT_MIN`, so the original stream interval reads differently there (PR #29034 describes both). The other six
convert nothing outside the 32-bit range; the EKF2 source's ARM reading is in PR #29039.

`t/refute_at.py` refutes each finding at the real input in the table. The kernels' verdicts are in
`t/FLIGHT-FINDINGS.md`.

**Checked against PX4 itself.** `px4_diff.py` fetches PX4's headers at the pinned commit (the platform header is
replaced by a two-macro stub), compiles each function's own C++, and runs it on every domain point of its t task. It
compares each result with t's interpreter. The table is `t/PX4-DIFF.md`.
