# PX4's code against its t transcription

PX4-Autopilot at dd804e4b9c490aed051bb36f8d3fca1ee137be2a: each routine's own C++ (the call below) compiled and run on every domain point of its t task (at most 400), each result compared with t's interpreter (t/flight/px4_diff.py).

- routines compared: 26; agree on every point: 25; points: 7060

| t task | PX4 call | status | points | first difference |
|---|---|---|---|---|
| px4_alpha_update | `[&]{ AlphaFilter<double> f; f.setAlpha((float)alpha); f.reset(state); return f.update(sample); }()` | agrees once PX4's float narrowing of alpha is applied | 400 |  |
| px4_constrain | `math::constrain<int64_t>(val, min_val, max_val)` | agrees | 400 |  |
| px4_constrain_f | `math::constrain<double>(val, min_val, max_val)` | agrees | 400 |  |
| px4_hysteresis_holds | `[&]{ systemlib::Hysteresis h; h.set_hysteresis_time_from(true, (hrt_abstime)time_from_true); h.set_hysteresis_time_from(false, (hrt_abstime)time_from_false); for (size_t i = 0; i < times.size(); i++) h.set_state_and_update(news[i] != 0, (hrt_abstime)times[i]); return h.get_state(); }()` | agrees | 255 |  |
| px4_hysteresis_set | `[&]{ systemlib::Hysteresis h(state); h.set_hysteresis_time_from(state, (hrt_abstime)INT64_MAX); h.set_state_and_update(requested, (hrt_abstime)last); h.set_hysteresis_time_from(true, (hrt_abstime)time_from_true); h.set_hysteresis_time_from(false, (hrt_abstime)time_from_false); h.set_state_and_update(new_state, (hrt_abstime)now); return h.get_state(); }()` | agrees | 400 |  |
| px4_hysteresis_switches | `[&]{ systemlib::Hysteresis h; h.set_hysteresis_time_from(true, (hrt_abstime)time_from_true); h.set_hysteresis_time_from(false, (hrt_abstime)time_from_false); for (size_t i = 0; i < times.size(); i++) h.set_state_and_update(true, (hrt_abstime)times[i]); return h.get_state(); }()` | agrees | 66 |  |
| px4_hysteresis_update | `[&]{ systemlib::Hysteresis h(state); h.set_hysteresis_time_from(state, (hrt_abstime)INT64_MAX); h.set_state_and_update(requested, (hrt_abstime)last); h.set_hysteresis_time_from(true, (hrt_abstime)time_from_true); h.set_hysteresis_time_from(false, (hrt_abstime)time_from_false); h.update((hrt_abstime)now); return h.get_state(); }()` | agrees | 324 |  |
| px4_interp_index | `` | not diffed: the index is internal to interpolateNXY, which returns only the interpolated value |  |  |
| px4_interpolate | `math::interpolate<double>(value, x_low, x_high, y_low, y_high)` | agrees | 400 |  |
| px4_is_in_range | `math::isInRange<int64_t>(val, min_val, max_val)` | agrees | 400 |  |
| px4_lerp | `math::lerp<double>(a, b, s)` | agrees | 400 |  |
| px4_max | `math::max<int64_t>(a, b)` | agrees | 400 |  |
| px4_max3 | `math::max<int64_t>(a, b, c)` | agrees | 400 |  |
| px4_min | `math::min<int64_t>(a, b)` | agrees | 400 |  |
| px4_min3 | `math::min<int64_t>(a, b, c)` | agrees | 400 |  |
| px4_negate_i16 | `math::negate<int16_t>((int16_t)value)` | agrees | 85 |  |
| px4_rb_pop_front | `[&]{ Ringbuffer b; b.allocate((size_t)size); b._start = (size_t)start; b._end = (size_t)end; std::vector<uint8_t> dst((size_t)buf_max_len + 1); size_t n = b.pop_front(dst.data(), (size_t)buf_max_len); return std::make_pair((long long)n, (long long)b._start); }()` | agrees | 104 |  |
| px4_rb_push_back | `[&]{ Ringbuffer b; b.allocate((size_t)size); b._start = (size_t)start; b._end = (size_t)end; std::vector<uint8_t> src((size_t)buf_len + 1); bool ok = b.push_back(src.data(), (size_t)buf_len); return std::make_pair((long long)ok, (long long)b._end); }()` | agrees | 104 |  |
| px4_rb_space_available | `[&]{ Ringbuffer b; b.allocate((size_t)size); b._start = (size_t)start; b._end = (size_t)end; return b.space_available(); }()` | agrees | 175 |  |
| px4_sign | `matrix::sign<int64_t>(val)` | agrees | 86 |  |
| px4_sign_from_bool | `math::signFromBool(positive)` | agrees | 2 |  |
| px4_sign_no_zero | `math::signNoZero<int64_t>(val)` | agrees | 86 |  |
| px4_slew_update | `[&]{ SlewRate<double> sr(value); sr.setSlewRate(slew_rate); return sr.update(new_value, (float)dt); }()` | agrees | 400 |  |
| px4_sq | `math::sq<int64_t>(val)` | agrees | 86 |  |
| px4_wrap_bin | `ObstacleMath::wrap_bin((int)bin, (int)bin_count)` | agrees | 400 |  |
| px4_wrap_bin_72 | `ObstacleMath::wrap_bin((int)bin, 72)` | agrees | 87 |  |
| px4_wrap_int | `matrix::wrap<int64_t>(x, low, high)` | agrees | 400 |  |

## Contracts PX4's code breaks

Each task under `t/flight/findings/` restates a PX4 function with its contract and without the `requires` its callers do not establish. The input below is where the kernels' refutation certificates point (or a probe); PX4's own code is run there.

| t task | PX4 call | input | t | PX4 | breaks the contract | status |
|---|---|---|---|---|---|---|
| px4_wrap_bin_any | `ObstacleMath::wrap_bin((int)bin, (int)bin_count)` | {"bin": -2147483648, "bin_count": 2147483647} | -1 | -1 | True | PX4 breaks the contract here, as t's body does |
| px4_wrap_bin_any | `ObstacleMath::wrap_bin((int)bin, (int)bin_count)` | {"bin": -73, "bin_count": 72} | -1 | -1 | True | PX4 breaks the contract here, as t's body does |
