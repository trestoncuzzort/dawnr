# is_in_range — math::isInRange (Limits.hpp)

PX4: `src/lib/mathlib/math/isInRange` — the range predicate `getChannelIndex` trusts to keep the rc_map index
in bounds, so its correctness underpins the rc_map_index gate. Contract: returns exactly `lo <= x <= hi`.
The twin drops the upper bound (`r := lo <= x`); SPARK refutes it at `x=100, lo=0, hi=10` (claims in-range).
