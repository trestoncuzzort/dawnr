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

**Checked against PX4 itself.** `px4_diff.py` fetches PX4's headers at the pinned commit (the platform header is
replaced by a two-macro stub), compiles each function's own C++, and runs it on every domain point of its t task. It
compares each result with t's interpreter. The table is `t/PX4-DIFF.md`.
