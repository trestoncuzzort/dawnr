"""Native cross-checks of the libevent parse_numeric_servname case with the C library, outside the gate.

  python3 cross_check.py OUT_DIR [DIRECTORY_OF_native_case.py]
  cd OUT_DIR
  gcc -std=gnu11 -O2 standin.c -o standin && ./standin 6 20000000
  gcc -std=gnu11 -O2 exhaust-original.c -o exhaust-original && ./exhaust-original 6 20000000
  gcc -std=gnu11 -O2 exhaust-fixed.c -o exhaust-fixed && ./exhaust-fixed 6 20000000
  gcc -std=gnu11 -O2 -DSTANDIN exhaust-original.c -o exhaust-original-standin && ./exhaust-original-standin 6 20000000
  gcc -std=gnu11 -O2 -DSTANDIN exhaust-fixed.c -o exhaust-fixed-standin && ./exhaust-fixed-standin 6 20000000

The model of the case reads strtol as the stand-in in prelude.inc, so the verdict for the fixed
source holds for the C library only as far as the stand-in matches it.

The input domain of the case is every string of 0 to 11 characters of 255 values, about 10^26
strings. The checks below run a stated part of it, in four groups. The first argument is the
longest length of the first group and the second the number of random strings.
  1. Every string of length 0 to 3 over all 255 non-zero bytes.
  2. Every string of length 0 to N (N is the first argument, 6 above) over 24 characters: the ten
     digits, the six white space characters, + and -, x, the two neighbours of the digit range
     (/ and :), and the bytes 0x01, 0x80 and 0xff.
  3. A structured set: 17 prefixes of white space and signs, 62 values around the powers of two,
     the port limits and the decimal digit counts (including 2^32+81 and 2^32), each with every
     number of leading zeros, and 13 suffixes, as long as the string has at most 11 characters.
  4. Random strings of 0 to 11 characters, half of them a prefix, digits and a suffix, half of
     them characters drawn from the 24 above or from all bytes.
The characters after the terminator are the digit 7, so a read past the terminator changes a result.

standin.c compares case_strtol with strtol for every string of these groups: the value and the
offset of the end pointer. It then compares the two for the saturation at LONG_MAX and LONG_MIN,
which the strings of the domain never reach: digit strings of 1 to 30 digits and the strings
around 2^63, each with no sign, + and -.

exhaust-VARIANT.c is the harness of the case as a native function, with the definitions that the
gate extracts for that variant, and runs it on the strings of these groups. It calls the C
library strtol, or the stand-in when it is compiled with -DSTANDIN. It prints the number of runs,
of runs that an assumption rejected, of runs with a failed assertion, and the failures per
assertion.

With GCC 13.3 and glibc 2.39 on x86-64, for the arguments 6 and 20000000: 236092794 strings. The
stand-in and strtol differ on none of them (value and end pointer), nor on 504 further
saturation strings. The original source fails the harness on 89 of the 236092794 strings
(servname.digits 54, servname.value 89, the other assertions none), all of them with 10 or 11
characters, and the fixed source on none, with the C library and with the stand-in alike. Built
with -fsanitize=undefined,address and run for the arguments 5 and 5000000 (29989818 strings), the
original fails on 78 strings and the fixed source on none.
"""
import json
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, sys.argv[2] if len(sys.argv) > 2 else str(root.parents[1]))
import native_case

out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
case = native_case.load(root)

ENUMERATION = r'''
static const unsigned char ALPHA[] = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ' ', '\t', '\n', '\v', '\f', '\r',
                                      '+', '-', 'x', '/', ':', 0x01, 0x80, 0xff};
static const char *const PREFIX[] = {"", " ", "\t", "  ", "\n\v", " +", " -", "+", "-", "  +", "\f-", "+ ", "- ", "\r\n-",
                                     "++", "--", "+-"};
static const char *const SUFFIX[] = {"", " ", "x", "0", "9", "\n", "+", "-", ".", "/", ":", " 1", "\x80"};
static const unsigned long long VALUE[] = {
    0ull, 1ull, 7ull, 8ull, 9ull, 10ull, 11ull, 79ull, 80ull, 81ull, 99ull, 100ull, 999ull, 1000ull, 9999ull, 10000ull,
    65534ull, 65535ull, 65536ull, 65537ull, 65591ull, 99999ull, 100000ull, 131071ull, 131072ull, 999999ull,
    1000000ull, 16777216ull, 2147483647ull, 2147483648ull, 2147483649ull, 4294967294ull, 4294967295ull,
    4294967296ull, 4294967297ull, 4294967376ull, 4294967377ull, 4294967378ull, 4294967296ull + 65535ull,
    4294967296ull + 65536ull, 4294967296ull + 65537ull, 8589934592ull, 8589934592ull + 81ull, 12884901888ull + 80ull,
    68719476736ull, 68719476736ull + 81ull, 281474976710656ull + 0ull, 99999999999ull, 10000000000ull,
    9999999999ull, 1000000000ull, 100000000ull, 21474836470ull, 42949672960ull, 42949672960ull + 81ull,
    98784247809ull, 98784247808ull, 98784247808ull + 65535ull, 98784247808ull + 65536ull, 4294967296ull * 3ull + 1ull,
    4294967296ull * 15ull + 65535ull, 4294967296ull * 15ull + 65536ull};
typedef void (*visit_fn)(const char *text, int length);
static char current[40];
static unsigned long long total;

static void put(visit_fn visit, const char *text, size_t length)
{
    if (length > 11) return;
    memcpy(current, text, length);
    current[length] = '\0';
    memset(current + length + 1, '7', sizeof current - length - 1);
    ++total;
    visit(current, (int)length);
}

static void recurse(visit_fn visit, char *text, int length, int most)
{
    put(visit, text, (size_t)length);
    if (length == most) return;
    for (size_t k = 0; k < sizeof ALPHA; ++k) {
        text[length] = (char)ALPHA[k];
        recurse(visit, text, length + 1, most);
    }
}

static void every_byte(visit_fn visit)
{
    char text[4];
    put(visit, text, 0);
    for (int a = 1; a <= 255; ++a) {
        text[0] = (char)a;
        put(visit, text, 1);
        for (int b = 1; b <= 255; ++b) {
            text[1] = (char)b;
            put(visit, text, 2);
            for (int c = 1; c <= 255; ++c) {
                text[2] = (char)c;
                put(visit, text, 3);
            }
        }
    }
}

static void structured(visit_fn visit)
{
    for (size_t p = 0; p < sizeof PREFIX / sizeof *PREFIX; ++p)
        for (size_t v = 0; v < sizeof VALUE / sizeof *VALUE; ++v)
            for (int zeros = 0; zeros <= 11; ++zeros)
                for (size_t s = 0; s < sizeof SUFFIX / sizeof *SUFFIX; ++s) {
                    char text[64];
                    int length = snprintf(text, sizeof text, "%s%.*s%llu%s", PREFIX[p], zeros, "00000000000", VALUE[v], SUFFIX[s]);
                    put(visit, text, (size_t)length);
                }
}

static unsigned long long state = 88172645463325252ull;
static unsigned long long next(void)
{
    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    return state;
}

static void randomly(visit_fn visit, unsigned long long samples)
{
    for (unsigned long long n = 0; n < samples; ++n) {
        char text[16];
        int length = 0;
        if (next() & 1) {
            int budget = (int)(next() % 12);
            while (budget > 0 && length < 11 && (next() & 3) == 0) {
                text[length++] = " \t\n\v\f\r"[next() % 6];
                --budget;
            }
            if (budget > 0 && length < 11 && (next() & 1)) {
                text[length++] = (next() & 1) ? '+' : '-';
            }
            int digits = (int)(next() % 12);
            while (digits-- > 0 && length < 11) text[length++] = (char)('0' + next() % 10);
            if ((next() & 3) == 0 && length < 11) text[length++] = (char)ALPHA[next() % sizeof ALPHA];
        } else {
            int want = (int)(next() % 12);
            while (length < want) {
                unsigned long long r = next();
                if (r & 1) text[length++] = (char)ALPHA[(r >> 1) % sizeof ALPHA];
                else if (r & 2) text[length++] = (char)('0' + (r >> 2) % 10);
                else text[length++] = (char)(1 + (r >> 2) % 255);
            }
        }
        put(visit, text, (size_t)length);
    }
}

static void enumerate(visit_fn visit, int most, unsigned long long samples)
{
    char text[16];
    every_byte(visit);
    recurse(visit, text, 0, most);
    structured(visit);
    randomly(visit, samples);
}
'''

standin = r'''#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define __CPROVER__ 1
''' + case["prelude"] + r'''
#undef strtol
''' + ENUMERATION + r'''
static unsigned long long compared, bad;
static void same(const char *text, int length)
{
    char *ea = NULL, *eb = NULL;
    long a = case_strtol(text, &ea, 10);
    long b = strtol(text, &eb, 10);
    (void)length;
    ++compared;
    if (a != b || ea - text != eb - text) {
        ++bad;
        if (bad < 10) printf("differs on length %d: %ld at %ld and %ld at %ld\n", length, a, (long)(ea - text), b, (long)(eb - text));
    }
}
static void deep(const char *text)
{
    char *ea = NULL, *eb = NULL;
    long a = case_strtol(text, &ea, 10);
    long b = strtol(text, &eb, 10);
    ++compared;
    if (a != b || ea - text != eb - text) {
        ++bad;
        if (bad < 10) printf("differs on %s: %ld at %ld and %ld at %ld\n", text, a, (long)(ea - text), b, (long)(eb - text));
    }
}
int main(int argc, char **argv)
{
    if (argc != 3) return 2;
    enumerate(same, atoi(argv[1]), strtoull(argv[2], NULL, 10));
    printf("strings of the domain %llu, compared %llu, differences %llu\n", total, compared, bad);
    unsigned long long before = compared;
    static const char *const SIGN[] = {"", "+", "-", " ", "\t-", " +"};
    for (size_t s = 0; s < sizeof SIGN / sizeof *SIGN; ++s) {
        char text[96];
        for (int digits = 1; digits <= 30; ++digits) {
            char run[40];
            memset(run, '9', (size_t)digits);
            run[digits] = '\0';
            snprintf(text, sizeof text, "%s%s", SIGN[s], run);
            deep(text);
            snprintf(text, sizeof text, "%s%sx", SIGN[s], run);
            deep(text);
        }
        static const unsigned long long EDGE[] = {9223372036854775805ull, 9223372036854775806ull, 9223372036854775807ull,
                                                  9223372036854775808ull, 9223372036854775809ull, 9223372036854775810ull,
                                                  18446744073709551614ull, 18446744073709551615ull};
        for (size_t e = 0; e < sizeof EDGE / sizeof *EDGE; ++e) {
            snprintf(text, sizeof text, "%s%llu", SIGN[s], EDGE[e]);
            deep(text);
            snprintf(text, sizeof text, "%s0000%llu", SIGN[s], EDGE[e]);
            deep(text);
            snprintf(text, sizeof text, "%s%llu0", SIGN[s], EDGE[e]);
            deep(text);
        }
    }
    printf("saturation strings %llu, total compared %llu, differences %llu\n", compared - before, compared, bad);
    return bad != 0;
}
'''
(out / "standin.c").write_text(standin)

names = case["assertions"]
inputs = ", ".join(f"{item['type']} {item['name']}" for item in case["inputs"])
arguments = ", ".join(
    ["(unsigned char)length"] + [f"(unsigned char)({k} < length ? text[{k}] : '7')" for k in range(11)])
for variant in ("original", "fixed"):
    texts, _ = native_case.definitions(case, variant, root)
    program = r'''#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef STANDIN
#define __CPROVER__ 1
#endif
''' + case["prelude"] + "".join(texts) + ENUMERATION + r'''
static const char *const names[] = {''' + ", ".join(json.dumps(name) for name in names) + r'''};
static unsigned long long runs, rejected, failed_runs, failures[sizeof names / sizeof names[0]];
static int failed_now;
static void fail(const char *name)
{
    for (unsigned k = 0; k < sizeof names / sizeof names[0]; ++k) if (strcmp(name, names[k]) == 0) ++failures[k];
    failed_now = 1;
}
#define __CPROVER_assume(c) do { if (!(c)) { ++rejected; return; } } while (0)
#define __CPROVER_assert(c, name) do { if (!(c)) fail(name); } while (0)
static void harness(''' + inputs + r''')
{
''' + case["harness"] + r'''}
static void run(const char *text, int length)
{
    failed_now = 0;
    ++runs;
    harness(''' + arguments + r''');
    if (failed_now) {
        ++failed_runs;
        if (failed_runs <= 3) printf("first failures: length %d text %s\n", length, text);
    }
}
int main(int argc, char **argv)
{
    if (argc != 3) return 2;
    enumerate(run, atoi(argv[1]), strtoull(argv[2], NULL, 10));
    printf("runs %llu rejected %llu failed %llu per_assertion", runs, rejected, failed_runs);
    for (unsigned k = 0; k < sizeof names / sizeof names[0]; ++k) printf(" %s=%llu", names[k], failures[k]);
    printf("\n");
    return 0;
}
'''
    (out / f"exhaust-{variant}.c").write_text(program)
