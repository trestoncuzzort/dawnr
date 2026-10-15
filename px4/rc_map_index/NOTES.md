# rc_map_index — RCUpdate::getChannelIndex array-bounds

PX4: `src/modules/rc_update/rc_update.cpp:190` `getChannelIndex()` maps an `RC_MAP_*` int parameter to an
index into 18-wide arrays (`_rc.channels[]`, `_parameters.min/trim/max/rev[]`, `RC_MAX_CHAN_COUNT == 18`).
Callers index those guarded ONLY by `index >= 0` (e.g. `getChannelValue`:
`return (index >= 0) ? _rc.channels[index] : 0.f;`), so memory safety depends on the contract
(`rc_update.h:150`: "return 0..RC_MAX_CHAN_COUNT-1 or -1"), enforced by:
`if (math::isInRange<int32_t>(map, 1, RC_MAX_CHAN_COUNT)) return map-1; else return -1;`.

`model.t` models exactly that. The proof: a valid index is always `0 <= i < 18`. The twin drops the upper
bound; SPARK refutes it at `ch=19` (index 18 — out of range). If a refactor weakens the `isInRange` bound,
`dawnr check cert.json` stops reproducing.
