"""Native cross-checks of the xiph/flac metaflac case with the C library, outside the gate.

  DAWNR_T=/path/to/dawnr/t python3 cross_check.py OUT_DIR
  cd OUT_DIR
  gcc -std=gnu11 -O1 -fsanitize=undefined -fsanitize=address -fno-sanitize-recover=all standin.c -o standin && ./standin
  gcc -std=gnu11 -O2 exhaust-original.c -o exhaust-original && ./exhaust-original
  gcc -std=gnu11 -O2 exhaust-fixed.c -o exhaust-fixed && ./exhaust-fixed
  gcc -std=gnu11 -O1 -fsanitize=undefined -fsanitize=address -fno-sanitize-recover=all exhaust-fixed.c -o exhaust-fixed-san && ./exhaust-fixed-san quick

DAWNR_T names the directory with native_case.py; it defaults to two levels above this script.

The model of the case reads strlen, strspn, strtoul and strtoull as the stand-ins in prelude.inc, so
the verdict for the fixed source holds for the C library only as far as the stand-ins match it.

standin.c compares the stand-ins (strlen, strspn, strtoul, strtoull) with the C library. The input domain of the stand-ins (strings
of any length) is too large to list, so it uses these sets, which it prints:
  1. every string of 0 to 2 characters, each any byte except NUL;
  2. every string of 3 characters over 24 characters (the ten digits, the six white space
     characters of the C locale, +, -, a, x, ., 0x7f, 0x80, 0xff);
  3. every string of 1 to 7 decimal digits, with and without the suffix "x";
  4. the decimal strings of the integers within 300 of 10^k, 2^k and 2^k - 1 for every k
     up to 64, and of all multiples of 2^32 up to 2^64 with the same offsets, with and without
     the suffix "x" (these reach and pass ULLONG_MAX, where the result saturates), and the
     strings of 20 to 25 nines;
  5. 20 million random strings of 0 to 25 characters, seven in eight of them digits.
For a string that starts with white space or a sign the stand-in must fail case_strtoull.covered;
for every other string it must fail nothing and return the value, the end pointer and the span
that the C library returns. A base other than 10 must fail case_strtoull.base; an accept set
other than the ten digits must fail case_strspn.accept.

exhaust-VARIANT.c is the harness of the case as a native function, with the definitions that the
gate extracts for that variant and no stand-in. It calls the harness for these sets of strings
of 0 to 11 characters (the bytes after the first NUL byte are 0):
  1. every string of 0 to 6 decimal digits;
  2. every string of 0 to 3 characters, each any byte except NUL;
  3. every string of 0 to 11 characters over the six characters 0, 4, 9, +, space and a
     (the argument quick skips this set);
  4. every decimal string of the integers within 300 of 10^k for k = 0 to 10, within 70000 of
     2^32, of j * 2^32 + r for j = 0 to 23 and r = 0 to 300 or 2^32 - 300 to 2^32 - 1, and within
     300 of 2^24, with and without a trailing "x" when the string has at most 10 characters;
  5. 100 million (10 million with quick) random strings of 0 to 11 characters, seven in eight of
     the characters digits, and 10 million (1 million) random values from 0 to 99999999999.
It prints the number of runs, of runs with a failed assertion and of those per assertion, and
the number of runs in which the string was a number of one or more digits and in which that
number was at most 2^32 - 1.

With GCC 13.3 and glibc 2.39 on x86-64: standin makes 126,717,664 comparisons (126,635,639 with
a start that the stand-ins cover, 82,025 with white space or a sign) and finds no difference.
Each exhaust program makes 563,422,433 runs; in 57,655,755 of them the string is a number, and
in 44,544,793 of those the number is at most 2^32 - 1. The original source fails 13,110,962 runs,
which is every number above 2^32 - 1 (uint32.result and uint32.value in each of them,
padding.result and padding.value in 133,673), and the fixed source fails none. Built with the
sanitizers and run with the argument quick, the fixed source fails none of 29,065,966 runs.
"""
import json
import os
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, os.environ.get("DAWNR_T", str(root.parents[1])))
import native_case

out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
case = native_case.load(root)

standin = r'''#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned long long refused_covered, refused_base, refused_accept;
static void refuse(int ok, const char *name)
{
    if (ok) return;
    if (strcmp(name, "case_strtoull.covered") == 0) ++refused_covered;
    else if (strcmp(name, "case_strtoull.base") == 0) ++refused_base;
    else if (strcmp(name, "case_strspn.accept") == 0) ++refused_accept;
    else { printf("unknown property %s\n", name); exit(2); }
}
#define __CPROVER_assert(c, name) refuse((c) != 0, name)
#define __CPROVER__ 1
''' + case["prelude"] + r'''
#undef strlen
#undef strspn
#undef strtoul
#undef strtoull
static unsigned long long runs, covered_runs, refusals, bad;
static unsigned long long state = 88172645463325252ull;
static unsigned long long next(void)
{
    state ^= state << 13; state ^= state >> 7; state ^= state << 17;
    return state;
}
static void one(const char *s)
{
    char *ea, *eb, *ec;
    unsigned long long before = refused_covered;
    unsigned long long va = case_strtoull(s, &ea, 10);
    unsigned long vb = case_strtoul(s, &eb, 10);
    size_t span = case_strspn(s, "0123456789"), length = case_strlen(s);
    int starts = s[0] == ' ' || (s[0] >= '\t' && s[0] <= '\r') || s[0] == '+' || s[0] == '-';
    ++runs;
    if (starts) {
        ++refusals;
        if (refused_covered != before + 2) { ++bad; if (bad < 10) printf("no refusal for %02x\n", (unsigned char)s[0]); }
        return;
    }
    ++covered_runs;
    if (refused_covered != before) { ++bad; if (bad < 10) printf("refused: %s\n", s); return; }
    unsigned long long vc = strtoull(s, &ec, 10);
    unsigned long vd = strtoul(s, &ec, 10);
    size_t sp = strspn(s, "0123456789"), ln = strlen(s);
    if (va != vc || vb != vd || ea != ec || eb != ec || span != sp || length != ln) {
        ++bad;
        if (bad < 10) printf("differs: %s: %llu %llu, %lu %lu, ends %td %td %td, span %zu %zu\n", s, va, vc, vb, vd,
                             ea - s, eb - s, ec - s, span, sp);
    }
}
static void number(__int128 signed_n, int suffix)
{
    char text[64];
    int at = 0;
    char digits[48];
    int count = 0;
    unsigned __int128 n;
    if (signed_n < 0) return;
    n = (unsigned __int128)signed_n;
    if (n == 0) digits[count++] = '0';
    while (n != 0) { digits[count++] = (char)('0' + (int)(n % 10)); n /= 10; }
    while (count > 0) text[at++] = digits[--count];
    if (suffix) text[at++] = 'x';
    text[at] = '\0';
    one(text);
}
int main(void)
{
    char text[40];
    unsigned char alphabet[24] = "0123456789 \t\n\v\f\r+-ax.\x7f\x80\xff";
    /* 1 */
    one("");
    for (int a = 1; a < 256; ++a) {
        text[0] = (char)a; text[1] = '\0'; one(text);
        for (int b = 1; b < 256; ++b) { text[1] = (char)b; text[2] = '\0'; one(text); }
    }
    /* 2 */
    for (int a = 0; a < 24; ++a) for (int b = 0; b < 24; ++b) for (int c = 0; c < 24; ++c) {
        text[0] = (char)alphabet[a]; text[1] = (char)alphabet[b]; text[2] = (char)alphabet[c]; text[3] = '\0';
        one(text);
    }
    /* 3 */
    for (int length = 1; length <= 7; ++length) {
        unsigned long limit = 1;
        for (int i = 0; i < length; ++i) limit *= 10;
        for (unsigned long v = 0; v < limit; ++v) {
            unsigned long w = v;
            for (int i = length - 1; i >= 0; --i) { text[i] = (char)('0' + w % 10); w /= 10; }
            text[length] = '\0'; one(text);
            text[length] = 'x'; text[length + 1] = '\0'; one(text);
        }
    }
    /* 4 */
    for (int suffix = 0; suffix < 2; ++suffix) {
        for (int k = 0; k <= 64; ++k) {
            __int128 two = (__int128)1 << k, ten = 1;
            for (int i = 0; i < k && i < 25; ++i) ten *= 10;
            for (int d = -300; d <= 300; ++d) {
                number(two + d, suffix);
                number(two - 1 + d, suffix);
                if (k <= 25) number(ten + d, suffix);
            }
        }
        for (__int128 j = 0; j <= ((__int128)1 << 32); j += (j < 70000 ? 1 : j / 7 + 1)) {
            __int128 base = j << 32;
            for (int d = -300; d <= 300; ++d) number(base + d, suffix);
        }
        for (int nines = 20; nines <= 25; ++nines) {
            for (int i = 0; i < nines; ++i) text[i] = '9';
            text[nines] = suffix ? 'x' : '\0'; text[nines + 1] = '\0';
            one(text);
        }
    }
    /* 5 */
    for (unsigned long long i = 0; i < 20000000ull; ++i) {
        int length = (int)(next() % 26);
        for (int k = 0; k < length; ++k) {
            unsigned long long r = next();
            text[k] = (r & 7) ? (char)('0' + (r >> 3) % 10) : (char)(1 + (r >> 3) % 255);
        }
        text[length] = '\0';
        one(text);
    }
    one("x");
    printf("stand-in comparisons %llu; %llu with a start that the stand-in covers, %llu with white space or a sign;"
           " differences %llu\n", runs, covered_runs, refusals, bad);
    /* a base other than 10 and another accept set must be refused */
    unsigned long long base_before = refused_base, accept_before = refused_accept;
    (void)case_strtoull("12", 0, 16);
    (void)case_strspn("12", "01234567");
    printf("base 16 refused %llu, other accept set refused %llu (both expected 1)\n", refused_base - base_before,
           refused_accept - accept_before);
    return bad != 0 || refused_base - base_before != 1 || refused_accept - accept_before != 1;
}
'''
(out / "standin.c").write_text(standin)

names = case["assertions"]
inputs = ", ".join(f"{item['type']} {item['name']}" for item in case["inputs"])
call = ", ".join(f"b[{i}]" for i in range(len(case["inputs"])))
for variant in ("original", "fixed"):
    texts, _ = native_case.definitions(case, variant, root)
    program = r'''#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
''' + case["prelude"] + "".join(texts) + r'''
static const char *const names[] = {''' + ", ".join(json.dumps(name) for name in names) + r'''};
static unsigned long long runs, failed_runs, numbers, in_range, failures[sizeof names / sizeof names[0]];
static int failed_now, current_number, current_in_range;
static void fail(const char *name)
{
    for (unsigned k = 0; k < sizeof names / sizeof names[0]; ++k) if (strcmp(name, names[k]) == 0) ++failures[k];
    failed_now = 1;
}
#define __CPROVER_assert(c, name) do { if (!(c)) fail(name); } while (0)
static void harness(''' + inputs + r''')
{
''' + case["harness"] + r'''    current_number = length > 0 && digits;
    current_in_range = fits;
}
static void run(const unsigned char *b)
{
    failed_now = 0;
    ++runs;
    harness(''' + call + r''');
    numbers += current_number;
    in_range += current_in_range;
    if (failed_now) ++failed_runs;
}
static unsigned long long state = 1234567890123456789ull;
static unsigned long long next(void)
{
    state ^= state << 13; state ^= state >> 7; state ^= state << 17;
    return state;
}
static void text(const char *s)
{
    unsigned char b[11] = {0};
    size_t n = strlen(s);
    if (n > 11) return;
    memcpy(b, s, n);
    run(b);
}
static void value(unsigned long long n, int suffix)
{
    char s[24];
    int at = 0, count = 0;
    char digits[24];
    if (n == 0) digits[count++] = '0';
    while (n != 0) { digits[count++] = (char)('0' + n % 10); n /= 10; }
    while (count > 0) s[at++] = digits[--count];
    if (suffix) s[at++] = 'x';
    s[at] = '\0';
    text(s);
}
int main(int argc, char **argv)
{
    int quick = argc > 1 && strcmp(argv[1], "quick") == 0;
    unsigned char b[11];
    /* 1 */
    for (int length = 0; length <= 6; ++length) {
        unsigned long limit = 1;
        for (int i = 0; i < length; ++i) limit *= 10;
        for (unsigned long v = 0; v < limit; ++v) {
            unsigned long w = v;
            memset(b, 0, sizeof b);
            for (int i = length - 1; i >= 0; --i) { b[i] = (unsigned char)('0' + w % 10); w /= 10; }
            run(b);
        }
    }
    /* 2 */
    memset(b, 0, sizeof b);
    run(b);
    for (int x = 1; x < 256; ++x) {
        memset(b, 0, sizeof b); b[0] = (unsigned char)x; run(b);
        for (int y = 1; y < 256; ++y) {
            memset(b, 0, sizeof b); b[0] = (unsigned char)x; b[1] = (unsigned char)y; run(b);
            for (int z = 1; z < 256; ++z) { b[2] = (unsigned char)z; run(b); }
        }
    }
    /* 3 */
    if (!quick) {
        const unsigned char alphabet[6] = {'0', '4', '9', '+', ' ', 'a'};
        for (int length = 0; length <= 11; ++length) {
            unsigned long total = 1;
            for (int i = 0; i < length; ++i) total *= 6;
            for (unsigned long v = 0; v < total; ++v) {
                unsigned long w = v;
                memset(b, 0, sizeof b);
                for (int i = 0; i < length; ++i) { b[i] = alphabet[w % 6]; w /= 6; }
                run(b);
            }
        }
    }
    /* 4 */
    for (int suffix = 0; suffix < 2; ++suffix) {
        unsigned long long ten = 1;
        for (int k = 0; k <= 10; ++k, ten *= 10)
            for (long long d = -300; d <= 300; ++d) if ((long long)ten + d >= 0) value((unsigned long long)((long long)ten + d), suffix);
        for (long long d = -70000; d <= 70000; ++d) value((unsigned long long)((1ll << 32) + d), suffix);
        for (unsigned long long j = 0; j <= 23; ++j)
            for (unsigned long long r = 0; r <= 300; ++r) {
                value((j << 32) + r, suffix);
                value(((j + 1) << 32) - 1 - r, suffix);
            }
        for (long long d = -300; d <= 300; ++d) value((unsigned long long)((1ll << 24) + d), suffix);
    }
    /* 5 */
    for (unsigned long long i = 0; i < (quick ? 10000000ull : 100000000ull); ++i) {
        int length = (int)(next() % 12);
        memset(b, 0, sizeof b);
        for (int k = 0; k < length; ++k) {
            unsigned long long r = next();
            b[k] = (r & 7) ? (unsigned char)('0' + (r >> 3) % 10) : (unsigned char)(1 + (r >> 3) % 255);
        }
        run(b);
    }
    for (unsigned long long i = 0; i < (quick ? 1000000ull : 10000000ull); ++i) value(next() % 100000000000ull, 0);
    printf("runs %llu failed %llu numbers %llu in_range %llu per_assertion", runs, failed_runs, numbers, in_range);
    for (unsigned k = 0; k < sizeof names / sizeof names[0]; ++k) printf(" %s=%llu", names[k], failures[k]);
    printf("\n");
    return 0;
}
'''
    (out / f"exhaust-{variant}.c").write_text(program)
