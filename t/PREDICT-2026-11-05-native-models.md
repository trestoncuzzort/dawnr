# Native gate: C library models shared between cases, 2026-11-05

Three of the eight published cases wrote stand-ins for C library functions by hand, 45 to 83 lines each, with a
`cross_check.py` of 131 to 335 lines to compare them with the C library. Each stand-in covers only what its own
case needs, so nothing carries over. This adds a small library of models, compared once with the C library over a
stated domain, and a `models` key that links them beside the checked unit.

## What was measured before this file was written

CBMC 6.11.0 has 529 models in `src/ansi-c/library`. Of the functions real C code calls most, it has none for
`strspn`, `strcspn`, `strpbrk`, `strstr`, `strnlen`, `memchr`, `memrchr`, `strtok`, `strtok_r`, `strsep`, `strndup`,
`strtoul`, `strtoll`, `strtoull` or `atoll`, and none for `__ctype_b_loc`, which glibc's `<ctype.h>` macros call in
place of the `isdigit` model it does have.

Its `strtol` model, compiled natively from the source at tag `cbmc-6.11.0` and compared with glibc 2.39 by
a throwaway script over 29 strings in 6 bases, differs on **83 of 174**:

| input | base | model | glibc and C11 7.22.1.4 |
|---|---|---|---|
| `+`, `-`, a space | any | end pointer past it | no digits, so the end pointer is the start |
| `12` | 2 | 4, end 2 | 1, end 1: 2 is not a digit in base 2 |
| `9` | 8 | 9, end 1 | 0, end 0 |
| `0x` | 16 | end 2 | end 1: the number is the `0` |
| a value out of range | any | end pointer never set | end pointer after the digits |

By inspection, not run: it also stops at 31 characters. So a `complete` on code that calls `strtol` could rest on
a wrong model. A report to the CBMC project should follow; none has been sent.

## Changes

`t/native_models/string.c`, `stdlib.c`, `ctype.c` and `ctype_strict.c` are plain C, written from C11 7.24, 7.22.1.4 and 7.4,
one byte at a time so a read past the end of an object fails a property. They use no CBMC intrinsics and hold
no assumptions, so they compile natively, where `t/native_models/cross_check.py` compares each one with the C library.
A case asks for them with `"models": ["string", "stdlib", "ctype"]`. They are linked in every stage, and the native
replay still calls the real C library, so a model that differs from it shows up as `not_reproduced`.

`ctype` matches glibc's table for -128 to 255. `ctype_strict` follows C11 7.4 instead: only `EOF` and the values of
`unsigned char` are in the table, so passing a negative `char` to `isdigit`, which is undefined behaviour glibc
tolerates, fails a property. Its witnesses replay as `not_reproduced` on glibc, by design.

No library of C models with a compatible licence and this comparison was found. Looked at: CBMC's own
(`src/ansi-c/library`, read), one of AWS's stubs (`awslabs/aws-c-common`, `verification/cbmc/stubs/memcpy_override.c`, read after these were written), and this
date's research list, searched for libc, musl, newlib and stand-ins. AWS states overlap and region checks as `__CPROVER_precondition` calls before a byte loop. These
leave that to the gate's pointer checks, because they have to compile natively, so nothing was taken from it.
INVENTED: the models themselves, from the C standard.

## Predictions, written before any of it was run

| # | prediction | falsified by |
|---|---|---|
| M1 | The models agree with glibc on the whole stated domain, return value, end pointer and `errno`, and run clean under ASan and UBSan. A first-run disagreement is recorded here | a disagreement left in the final run |
| M2 | Written from the standard, at least one model disagrees with glibc on the first run | none do, which would be a reason to doubt the domain |
| M3 | The flac case with a `string` input and `models` in place of its 83 lines of stand-ins: the same verdicts and no new failing property | another verdict, or a new failure |
| M4 | The libevent case the same way, in place of its 45 lines | another verdict, or a new failure |
| M5 | Each takes at most 3 times the rewritten case with its own stand-ins (`t/native_rewrite_check.py`) | more than 3 times |

## Results

GCC 13.3.0, glibc 2.39, CBMC 6.11.0. Receipts: [`evidence/native-models-2026-11-05/`](evidence/native-models-2026-11-05/), and the table above comes from `native_models/cbmc_strtol_gap.py`.

| # | outcome | measured |
|---|---|---|
| M1 | holds, after one fix | 85,702,150 comparisons with no difference, and 2,143,750 under ASan and UBSan with no difference and no report: 1,923 on the tables, 1,669,777 on strings, and 84,030,450 on numbers |
| M2 | holds | the first run disagreed: glibc's case tables read `c + 256` for a negative `char`, and these read `c`. Fixed in `make_ctype.py` |
| M3 | holds | flac: same verdicts, same failing properties, on both solvers. Prelude 166 lines to 82 |
| M4 | holds | libevent: the same. Prelude 65 lines to 19 |
| M5 | **half falsified** | libevent 0.87 and 0.67. Flac 1.91 under CaDiCaL, but **5.96 under MiniSat**, past the limit of 3: 962 s against 161 s |

| case | solver | `fixed` s, own stand-ins | `fixed` s, shared models | ratio | properties |
|---|---|---:|---:|---:|---|
| flac | MiniSat | 161.41 | 962.12 | 5.96 | 526 to 779 |
| flac | CaDiCaL | 8.93 | 17.10 | 1.91 | 526 to 779 |
| libevent | MiniSat | 11.23 | 9.76 | 0.87 | 239 to 311 |
| libevent | CaDiCaL | 21.47 | 14.28 | 0.67 | 239 to 311 |

So the guide says to use `--solver cadical` with the models. A general model is larger than a stand-in that covers one case: a stand-in for `strspn` that takes only the digits needs no inner loop.

Three things went wrong on the way, and each is kept here because the same mistake is easy to make again:

- **A division in the first `stdlib.c`.** It tested overflow with `(limit - digit) / base`, as C code usually does. A 64-bit division is a very large circuit, once per digit, and flac under MiniSat was still running at 807 s when stopped.
  CBMC's own `strtol` uses `__builtin_mul_overflow`, which should have been read first. The comparison with glibc did not change.
- **The driver compared uninitialized bytes.** 545,360 "differences" on the first full run were bytes after the terminator in two buffers that were never zeroed. The report showed equal offsets, which gave it away.
- **ASan replaces `strtol`.** Under ASan an invalid base sets the end pointer, where glibc leaves it alone, so that run compared the model with the sanitizer. `replace_str=0` keeps the sanitizer on the model.

## Limits

The comparison covers the domain in `cross_check.c`: strings of at most 5 bytes over 4 letters against sets of at most 3, numbers of at most 5 bytes over 16 characters, in 9 bases, and each side of each limit. Longer inputs are not compared, on glibc 2.39 in the C locale, x86-64.
`--32` has not been compared with a 32-bit C library, since the machine has none. `strtok`'s saved pointer is one static variable, as in the C library, so two threads are not modelled. There is no `snprintf` or `sscanf`: `va_arg` does not work in a model here, so a case that calls them still needs a stand-in.

## What this bought

Two published cases lose most of their stand-ins, with the same verdicts. Any new case gets them for nothing, and they are compared with the C library once and not once per case. A `complete` on code that calls `strtol` no longer has to rest on CBMC's model, which is wrong on many inputs. That wrong model is also worth reporting to its authors.
