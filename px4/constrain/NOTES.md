# constrain — math::constrain saturation

PX4 clamps control/PWM/actuator outputs with `math::constrain(value, min, max)` throughout (e.g. mixer and
output-limit paths in `src/lib/mixer_module/`). The safety property of any saturation: the result is always
within `[min,max]`, and unchanged when the input is already in range.

`model.t` is the integer model of that contract. The proof: result always in `[lo,hi]` and identity in range.
The twin drops the upper clamp (`else { r := x; }`); SPARK refutes it at `x=100, lo=0, hi=10` (returns 100 >
hi). A regression that breaks a clamp's upper bound would fail `dawnr check cert.json`.
