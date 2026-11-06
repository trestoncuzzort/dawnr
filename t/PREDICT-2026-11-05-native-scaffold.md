# Native gate: a case drafted from a function's signature, and a scan of a file, 2026-11-05

The cost of a native case is the step from a function to a harness. The research list of this date says the same, and the eight published
cases took hours each. `t/native_scaffold.py` drafts a case from a C file and a function name, and can do that for every function in a file.
It only checks safety: it knows nothing of what a function is for, so it cannot find the functional defects most of the published cases have.

## What it does

The file is preprocessed with `gcc -E`, with project headers expanded and system headers put back as includes, so the case needs no project header. The text is split into top-level items.
The target goes in `definitions`, and the prelude holds all the types and declarations, the functions the target reaches in the same file, and the globals
they use. Each parameter gets an input from its type: a scalar, a `string` for a `char *` with no length beside it, an `array` for a pointer with a length after it,
and one element for any other pointer to a scalar, recorded as a guess. A function taking a struct by pointer or by value, a function pointer, or a pointer to a
pointer is refused by name. C library models are linked when the code calls them, unless the file defines those names itself.

A scan runs the gate and `native_sample.py` on each draft, and lists a **candidate** when a witness is confirmed natively as `memory_error` or `undefined_behavior`, or the sampler gets a sanitizer report.

**A candidate is not a bug.** The harness has no idea of a caller's contract: a function may be right to assume `n > 0`, or that a buffer is larger than 4 bytes. A
person, or a careful reader, has to look at each one, and the published rule stands: reproduce it, read the project's own contract, and search upstream first. Nothing found here has been sent anywhere,
since the pull request campaign is paused.

Prior art: `goto-harness` in CBMC builds a harness from a signature, in goto form, with no native replay. `janislley/LSVerifier` (Apache-2.0, read) verifies one function at a time with a line-by-line parser,
which this does not lift: `gcc -E` and the gate's own `balance` are more robust. arXiv:2312.17677 (by abstract) accepts a drafted harness only once it compiles natively and reaches its end, which is
what the gate's coverage and replay already require here. INVENTED: the mapping from parameter to input, and the length heuristics, which S3 and S4 measure.

## Predictions, written before it was run

| # | prediction | falsified by |
|---|---|---|
| F1 | **A real known defect, with no harness written by hand:** a scan of lvgl's `lv_string_builtin.c` at the revision before the fix lists `lv_memcmp`, which reads out of bounds at length 0 | it is not listed |
| F2 | The same scan does not list `lv_memcmp` on the fixed file | it is still listed |
| F3 | Over 10 C files from 5 published projects, at least 30 percent of the functions have a signature it can draft | under 30 percent |
| F4 | Of those drafts, at least 70 percent reach a verdict: `complete`, `counterexample`, `vacuous` or `incomplete`, and not `tool_error` or `timeout`, at 60 s a stage | under 70 percent |
| F5 | Most candidates are false alarms from missing caller contracts: at most 1 in 3 of those read looks like a real defect worth a report | more than 1 in 3 |

## Results

Receipts: [`evidence/native-scaffold-2026-11-05/`](evidence/native-scaffold-2026-11-05/). `scan_files.py` there lists each file and include directory, with the machine's root replaced, so it does not run as it stands.
One reader read every candidate, and no maintainer has seen any of them.

| # | prediction | result | |
|---|---|---|---|
| F1 | a scan of lvgl's `lv_string_builtin.c` lists `lv_memcmp` before the fix | listed: gate `counterexample`, replay `memory_error`, sampler `sanitizer_report`, with a witness at length 0 | **holds** |
| F2 | it does not list `lv_memcmp` after the fix | gate `complete`, sampler `no_failure` | **holds** |
| F3 | at least 30 percent of functions draft, over 10 files from 5 projects | 70 of 199, or **35.2 percent**, over 19 files from 6 projects | **holds** |
| F4 | at least 70 percent of drafts reach a verdict | 61 of 70, or **87.1 percent**: 24 `complete`, 14 `counterexample`, 20 `incomplete`, 3 `vacuous`, against 7 `out_of_memory` and 2 `timeout`, at 60 s a stage and 2 GiB | **holds** |
| F5 | at most 1 in 3 candidates read looks real | 6 of 15, or **40 percent**. Two are one defect, which makes 5 of 14 distinct, or 36 percent | **falsified**, and in the better direction |

Refusals were 129 of 199: 115 take a pointer to a struct, 9 a pointer to a pointer, 2 a struct by value, 2 a void pointer with no length, and 1 a function pointer. `charset.c` and libevent's `strlcpy.c` count as files
with no functions, because this configuration compiles out everything in them. The share that draft moves a lot from file to file: 11 of 12 in `lv_math.c`, and 3 of 29 in `event_tagging.c`.

### The candidates

**F5 leans on one file.** Five of the six real ones are in `lv_math.c`, which is integer arithmetic, and that is the shape a signature describes best. Outside it, 1 of 9 candidates is real.

| function | read as | why |
|---|---|---|
| `lv_map` (lvgl) | **real** | `(x - min_in) * delta_out` overflows `int32_t` on ordinary values, and it reaches the public API. On lvgl itself, compiled under UBSan, on a 40 s timeline, `lv_anim_timeline_set_progress(at, 60000)` overflows, and `lv_anim_timeline_get_progress` then gives 0 |
| `lv_cubic_bezier`, `do_cubic_bezier` (lvgl) | real, minor, one defect | with `x1 = x2 = 0`, inside the documented ranges, Newton's method runs away and the next step overflows. 275 of 108,054,375 calls on a grid, in 3 of 4,225 `(x1, x2)` pairs. On a wrapping build, none of the 275 ended more than 32 of 1024 from the true curve, because bisection follows |
| `lv_sqrt32` (lvgl) | real, minor | takes `uint32_t`, but `xn * xn` overflows `int32_t` from 2147441940 up to the saturated branch. On a wrapping build, over every `uint32_t`, 41,708 inputs just below 2^31 give a root one too high. It is documented as approximate, and no caller in lvgl passes that much |
| `lv_pow` (lvgl) | real, minor | the last `base *= base` comes after its value stops mattering, so `lv_pow(10, 16)` and `lv_pow(3, 32)` overflow although the answer fits. No caller in lvgl passes that much |
| `msgpack_zone_new` (msgpack-c) | real, minor | `sizeof(chunk) + chunk_size` wraps, `malloc` succeeds with too little, and `chunk->next` is written out of bounds. Upstream has since merged a fix for exactly this, [msgpack-c#1206](https://github.com/msgpack/msgpack-c/pull/1206), by another author and after the revision scanned. That is the one reading here anyone else has confirmed |
| `lv_atan2`, `lv_bezier3`, `lv_pct_to_px` (lvgl) | false alarm, checked | each is `complete` once its contract is assumed |
| `filter`, `GetTitleGain` (flac), `encode_int_internal`, `encode_int64_internal` (libevent), `uv_wtf8_to_utf16`, `uv__get_surrogate_value` (libuv) | false alarm, by reading only | history behind the pointers; state from `InitGainAnalysis`; fixed-size buffers at each caller; a target sized by the caller; loops that stop at 0 |

Upstream was searched for each real one, and only `msgpack_zone_new` had a report. A search can miss one, so this is not a claim that the rest are new.

**A reading can be wrong, and checking it under the contract caught that.** I first read `lv_cubic_bezier` as a false alarm, since the header gives ranges and I assumed the draft had drawn outside them. Assuming those ranges, the gate timed out, and the sampler
then found `lv_cubic_bezier(31, 0, 1024, 0, 256)`. I had also first read `lv_atan2` as probably real, before finding the comment inside the function, and first written of `lv_sqrt32` that wrapping gives the right answer, which running every input disproved.
It took three attempts to write down what `LV_PCT` can produce: the first two allowed values it never makes, and gave two more counterexamples, which were mine and not lvgl's.

### What the first runs got wrong

- **A function whose name starts its line was not counted.** A regular expression chose the file's own functions, and needed a character before the name, so the GNU style of a return type on the line above gave libcoap and libevent 0 functions. They showed up as "0 functions, nothing refused", and looked like a clean result until the count looked odd. The choice now comes from the `gcc -E` line markers.
- **8 of the first 14 files never preprocessed**, because their trees were not configured. The first wide figures, 26 of 68 drafted, were from the other 6 files and are not in this table. Pointing at each build's generated headers fixed it, by hand for each project. **That step is still the largest practical cost of a scan.**
- **`malloc(0)` gives one readable byte under ASan**, so `lv_memcmp`'s witness at length 0 replayed clean at first. The replay now poisons that byte.
- **A preprocessed prelude conflicted with the includes in the replay**, so system headers go back to being includes. Then `size_t` read as a struct, since its typedef had gone with them, so types now come from the full expansion.
- **The length heuristic made false alarms, and three rules came out of reading them:** a pointer named as the end of the one before it makes one array (`s, se`), a length named after one pointer is that pointer's alone (`dst, src, dst_size`), and beside a writable pointer a `const char *` is a string. A length is now found past another scalar, so `lv_memset(dst, v, len)` drafts. These were added after seeing the candidates, so **the F5 figure is not from a heuristic fixed in advance**. The list before these rules had 3 of 11 real, or 27 percent, before `lv_cubic_bezier` was re-read.
- **The project's own `assert` counted as a candidate.** `coap_encode_var_safe` asserts `n <= length`, and the sampler's report of the abort listed it. A fired assert is more likely the contract than a defect, so it is now counted apart: 3 in this scan, one of which, `uv_wtf8_to_utf16`, is also a candidate for a memory error. A defect behind an assert would be missed by this.
- **A failed allocation could read as `tool_error`.** CBMC words it differently during propositional reduction, and that is now `out_of_memory`.
- **Time and memory verdicts move with the load.** Beside one other job, 5 rows timed out, against 2 when run alone. The table is from a run with nothing else running.

### A doubt that points at the guess

A candidate now carries a `doubt` when a memory error can be explained by what the draft guessed: a write past a writable `char *` it was given no size for, or a pointer guessed to hold one element, or by a null it did not pass. It stays listed. In this scan 3 of the 15 carry one, all 3 read as false alarms, and the 3 string functions below add 3 more. None of the real ones carry one, so among the 12 with no doubt, 6 are real. This rule was also written after seeing them. It has not been tested on a set it did not come from.

The string scan's other candidates, `lv_strcpy`, `lv_strcat` and `lv_strncat`, are false alarms, listed both before and after the fix: a function with no length for its destination leaves the room to its caller. All three carry the doubt. They are not in the F5 count, since F5 was about the wide scan.

### Safety

A scan runs each draft natively on arbitrary values, so a function that calls `kill`, `close`, `remove`, `system` and the like is refused, by name, unless a single case is drafted with `--allow-system` to read. That is a list and not a sandbox. These runs were done as an unprivileged user, and a scan of code you do not trust should be too, away from the network.

### What this does and does not show

It shows a function can get a case and a verdict with no harness written by hand, in about 4 minutes for 199 functions at 6 jobs, once the headers are found, and that this finds real defects in maintained projects. It does not give the gate's recall: nothing here says how many defects it misses, and 115 of 199 functions were refused for a struct pointer before anything looked at them. The next measurement is recall, from known fixes.
