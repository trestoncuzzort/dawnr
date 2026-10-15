# pwm_minmax — MixingOutput::updateParams min/max ordering

PX4: `src/lib/mixer_module/mixer_module.cpp:186` (inside `MixingOutput::updateParams`) restores the invariant
`_min_value[i] <= _max_value[i]` by SWAPPING them when a user sets min > max. Downstream clamping assumes
min <= max, so this fixup is load-bearing.

model.t models the swap; the proof: `min <= max` always holds afterward (and unchanged when already ordered).
The twin drops the swap; SPARK refutes it at `mn=10, mx=5` (min > max survives). source.json binds drift to
the enclosing `updateParams` (function-level hash; over-sensitive by design — any change to updateParams
prompts a re-review of this small sub-block).
