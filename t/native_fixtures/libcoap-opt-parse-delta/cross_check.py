"""Native run of the harness of the libcoap case over a large part of its input domain, outside the gate.

  DAWNR_NATIVE_T=/path/to/dawnr-native/t python3 cross_check.py OUT_DIR
  cd OUT_DIR
  gcc -std=gnu11 -O2 exhaust-original.c -o exhaust-original && ./exhaust-original
  gcc -std=gnu11 -O2 exhaust-fixed.c -o exhaust-fixed && ./exhaust-fixed

DAWNR_NATIVE_T is the directory with native_case.py; without it the script looks two levels up,
as when it stays in t/native_fixtures/NAME. It needs case.json, which make_case.py writes.

exhaust-VARIANT.c is the prelude, the definitions that the gate extracts for that variant and the
harness of the case as a native function, called with these inputs:

- every first byte h0 from 0 to 255;
- every value of the extra bytes that the header of h0 uses (h1 up to h4, none of them for a
  header without extra bytes), the other bytes being 0, with this exception: for h0 = 0xee,
  where four extra bytes are used, h1 and h2 take every value while h3 and h4 take 13 chosen
  values (0, 1, 2, 12, 13, 14, 15, 16, 127, 128, 253, 254, 255), and h1 in {0xfe, 0xff} with h2 in
  {0x00, 0x80, 0xf2, 0xf3, 0xff} take every value of h3 and h4;
- for each of these, the buffer lengths 0 to 6, the header size minus 1, the header size, the
  header size plus the value length minus 1, plus 0 and plus 1, 65808 and 65809.

The program prints the number of runs, of runs that an assumption rejected, of runs with a failed
assertion, of those whose inputs are not in the defect region (a delta nibble of 14 with
h1 = 0xfe and h2 >= 0xf3) and the failures per assertion, in the order of the case, and the
first failing input.

With GCC 13.3 and glibc 2.39 on x86-64 each program makes 660,705,976 runs, of which the
assumption rejects 65,546. The original source fails 547,177 runs, each of them on
opt.zero_exactly_when_invalid and opt.delta and all of them in the defect region. The fixed
source fails none.
"""
import json
import os
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, os.environ.get("DAWNR_NATIVE_T", str(root.parents[1])))
import native_case

out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
case = native_case.load(root)
names = case["assertions"]
inputs = ", ".join(f"{item['type']} {item['name']}" for item in case["inputs"])

for variant in ("original", "fixed"):
    texts, _ = native_case.definitions(case, variant, root)
    program = r'''#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
''' + case["prelude"] + "".join(texts) + r'''
static const char *const names[] = {''' + ", ".join(json.dumps(name) for name in names) + r'''};
static unsigned long long runs, rejected, failed_runs, outside, failures[sizeof names / sizeof names[0]];
static int failed_now, shown;
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
static void run(unsigned h0, unsigned h1, unsigned h2, unsigned h3, unsigned h4, unsigned room)
{
    failed_now = 0;
    ++runs;
    harness((unsigned char)h0, (unsigned char)h1, (unsigned char)h2, (unsigned char)h3, (unsigned char)h4, room);
    if (failed_now) {
        ++failed_runs;
        if (!((h0 >> 4) == 14 && h1 == 0xfe && h2 >= 0xf3)) ++outside;
        if (shown < 3) {
            ++shown;
            printf("failing input: %02x %02x %02x %02x %02x room %u\n", h0, h1, h2, h3, h4, room);
        }
    }
}
/* The buffer lengths that matter for one header; the header size and value length are those of the format. */
static void lengths(unsigned h0, unsigned h1, unsigned h2, unsigned h3, unsigned h4)
{
    unsigned char hb[5] = {(unsigned char)h0, (unsigned char)h1, (unsigned char)h2, (unsigned char)h3, (unsigned char)h4};
    unsigned dn = h0 >> 4, ln = h0 & 15, pos = 1, vlen = ln;
    if (dn == 13) pos += 1; else if (dn == 14) pos += 2;
    if (ln == 13) { vlen = 13u + hb[pos]; pos += 1; } else if (ln == 14) { vlen = 269u + 256u * hb[pos] + hb[pos + 1]; pos += 2; }
    unsigned list[] = {0, 1, 2, 3, 4, 5, 6, pos - 1, pos, pos + vlen - 1, pos + vlen, pos + vlen + 1, 65808, 65809};
    for (unsigned k = 0; k < sizeof list / sizeof list[0]; ++k) run(h0, h1, h2, h3, h4, list[k]);
}
int main(void)
{
    static const unsigned sample[] = {0, 1, 2, 12, 13, 14, 15, 16, 127, 128, 253, 254, 255};
    static const unsigned region[] = {0x00, 0x80, 0xf2, 0xf3, 0xff};
    for (unsigned h0 = 0; h0 <= 255; ++h0) {
        unsigned dn = h0 >> 4, ln = h0 & 15;
        unsigned used = (dn == 13 ? 1 : dn == 14 ? 2 : 0) + (ln == 13 ? 1 : ln == 14 ? 2 : 0);
        if (used == 0) lengths(h0, 0, 0, 0, 0);
        else if (used == 1) for (unsigned a = 0; a <= 255; ++a) lengths(h0, a, 0, 0, 0);
        else if (used == 2) for (unsigned a = 0; a <= 255; ++a) for (unsigned b = 0; b <= 255; ++b) lengths(h0, a, b, 0, 0);
        else if (used == 3) {
            for (unsigned a = 0; a <= 255; ++a) for (unsigned b = 0; b <= 255; ++b) for (unsigned c = 0; c <= 255; ++c) lengths(h0, a, b, c, 0);
        } else {
            for (unsigned a = 0; a <= 255; ++a) for (unsigned b = 0; b <= 255; ++b)
                for (unsigned c = 0; c < sizeof sample / sizeof sample[0]; ++c)
                    for (unsigned d = 0; d < sizeof sample / sizeof sample[0]; ++d) lengths(h0, a, b, sample[c], sample[d]);
            for (unsigned a = 0xfe; a <= 0xff; ++a)
                for (unsigned b = 0; b < sizeof region / sizeof region[0]; ++b)
                    for (unsigned c = 0; c <= 255; ++c) for (unsigned d = 0; d <= 255; ++d) lengths(h0, a, region[b], c, d);
        }
    }
    printf("runs %llu rejected %llu failed %llu outside_defect_region %llu per_assertion", runs, rejected, failed_runs, outside);
    for (unsigned k = 0; k < sizeof names / sizeof names[0]; ++k) printf(" %llu", failures[k]);
    printf("\n");
    return 0;
}
'''
    (out / f"exhaust-{variant}.c").write_text(program)
