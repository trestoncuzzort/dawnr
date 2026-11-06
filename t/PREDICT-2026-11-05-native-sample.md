# Native gate: running the harness itself over many inputs, 2026-11-05

A counterexample is replayed natively, so the real C library and the real compiler get a say. A `complete` verdict gets
no such check: if a library model is wrong, the model and the real code disagree in silence. CBMC's own `strtol` is wrong on 83 of 174
inputs (`t/PREDICT-2026-11-05-native-models.md`), so this can happen. Three published cases each wrote a `cross_check.py` that, among
other things, runs the harness natively over a large sample.

`t/native_sample.py` does that part for any case. It compiles the same prelude, definitions and harness natively under ASan and UBSan,
draws scalar inputs from a seeded generator, and runs the harness in one process. An assumption that rejects an input moves on to
the next one, and a failed assertion is counted and the input kept. A sanitizer report, or a stop, ends the run and names the input.

Prior art: the shape is a fuzzing harness, as in libFuzzer (llvm.org/docs/LibFuzzer.html). No coverage feedback is used here, since the point is a sample of the
stated domain and not a search for crashes. Boundary values follow the usual practice of testing the edges of a type.
INVENTED: the input mix. It is a guess, stated in the code, and it is what S2 measures.

## What this is not

Sampling is not proof. A sample that finds nothing says nothing about the inputs it did not draw. Its use is that it runs the
real code and the real C library, which is what the model cannot do. It does not replace a case's comparison of its own stand-ins
with the C library over every argument they can get.

## Predictions, written before it was run

| # | prediction | falsified by |
|---|---|---|
| S1 | 1,000,000 draws on all 8 published `fixed` variants and PX4: no failed assertion, no sanitizer report, no stop | any of them, which would be a disagreement between a `complete` model and the real code, and a finding |
| S2 | The same on the 8 `original` variants finds the defect natively on at least 4 of 8, without the solver's help | fewer than 4 |
| S3 | A harness asserting what CBMC's wrong `strtol` says, `strtol("12", &end, 2) == 4`, gets `complete` from the gate and a failed assertion from the sampler | the gate refuses it, or the sampler misses it |
| S4 | Under 60 s per case at 1,000,000 draws | a case above it |

## Results

GCC 13.3.0, glibc 2.39, seed 1, 1,000,000 draws per variant, `-O0` under ASan and UBSan. Receipts:
[`evidence/native-sample-2026-11-05/`](evidence/native-sample-2026-11-05/).

| # | outcome | measured |
|---|---|---|
| S1 | holds, weakly on some | no `fixed` variant fails, and all 8 published and PX4 agree with their `complete`. How much that says depends on how many draws reached the end of the harness, below |
| S2 | holds | 7 of 8 published `original` variants, with no help from the solver, and PX4. The first version of the generator found 5 |
| S3 | holds | a harness stating CBMC's wrong answer for `strtol("12", &end, 2)` is `complete` under the gate, and a failed assertion here. This is what it is for |
| S4 | holds | 28.4 s at most. 7.72 s by an outside clock for 30,000,000 draws of the rewritten libevent case, or about 250 ns per draw |

| case | reached the end, `fixed` | `original` found? | failed assertions, `original` |
|---|---:|---|---:|
| flac-metaflac-parse-uint32 | 1,000,000 | yes | 479,212 |
| libcoap-opt-parse-delta | 618,848 | yes | 4 |
| libevent-servname-port-range | 205,699 | **no** | 0 |
| betaflight-uvarint-encode | 139,163 | yes | 597 |
| inav-uvarint-encode | 139,163 | yes | 597 |
| libuv-utf8-decode1 | 134,410 | yes | 9 |
| msgpack-c-print-buffer-empty-bin | 7,353 | yes | 3,182 |
| open62541-datetime-parse-year | **534** | yes | 162 |
| px4-wrap-bin | **79** | yes | a sanitizer report: index -63 |

Read the second column before believing the first. PX4 draws `bin_count` and assumes it is 72, so nearly every draw is rejected, and 79 draws
of a 32-bit `bin` say little. open62541 needs 7 well-formed bytes at once. Rejected draws are also the slow ones, at about 15 s per
million, as against 0.2 s: each is a `longjmp`, which ASan handles slowly. A case's own harness decides this, and the tool cannot fix it.

Two things moved the numbers, and both are recorded because a reader will want them:

- **Whole draws that lean one way.** The first version drew each byte alone, which almost never satisfied a harness that needs several digits at
  once: it found 5 of 8, flac found nothing, and open62541 reached its end on 2 draws of 1,000,000. Letting a whole draw be digits, or text, or small values
  took it to 7 of 8, flac to 479,212 failures, and open62541 to 534 reaches.
- **Typed inputs.** The miss, libevent, has a `count` input of one byte, and a digit draw always breaks its assumption. The same case rewritten with a `string`
  input (`native_rewrite_check.py`) needs no rejection at all: all 1,000,000 draws reach the end, 4 of them fail, on the same two properties the solver found, and it takes 0.23 s
  instead of 27.95 s. So on these 8 cases, a harness written with typed inputs is found natively.

The generator found one bug of its own under test: at `-O1` the compiler removed a call whose result was unused, and with it the undefined behaviour under
test, so this compiles at `-O0`, as the replay does. Array inputs are never freed between draws, so a very large count grows without bound.

## What this bought

A check of `complete` that does not go through CBMC at all, in one command, for any case. It replaces the part of a `cross_check.py` that runs the harness.
It does not replace the part that compares a stand-in with the C library, and it has never proved anything.
