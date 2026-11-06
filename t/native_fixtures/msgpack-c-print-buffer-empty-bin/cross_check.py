"""Native cross-checks of the msgpack-c case with the C library, outside the gate.

  python3 cross_check.py OUT_DIR
  cd OUT_DIR
  gcc -std=gnu11 -O1 -fsanitize=undefined -fsanitize=address -fno-sanitize-recover=all standin.c -o standin && ./standin
  gcc -std=gnu11 -O2 exhaust-original.c -o exhaust-original && ./exhaust-original 0 0 0 && ./exhaust-original 1 -128 127
  gcc -std=gnu11 -O2 exhaust-fixed.c -o exhaust-fixed && ./exhaust-fixed 0 0 0 && ./exhaust-fixed 1 -128 127

The model of the case reads snprintf and isprint as the stand-ins in prelude.inc, so the
verdict for the fixed source holds for the C library only as far as the stand-ins match it.

standin.c compares case_snprintf with snprintf for every format, argument and buffer size
that the BIN and EXT branches can pass, and case_isprint with isprint for every byte.

exhaust-VARIANT.c is the harness of the case as a native function, with the definitions
that the gate extracts for that variant and no stand-in. Its arguments are the kind (0 BIN,
1 EXT) and the first and last EXT type; it calls the harness for every input of the declared
domain in that part and prints the number of runs, of runs that an assumption rejected, of
runs with a failed assertion, of those with one or two bytes, and the failures per assertion.

With GCC 13.3 and glibc 2.39 on x86-64: 19506 stand-in comparisons, no difference. Of the
422720025 inputs, the original source fails print.result and print.text for 3184, all of
them objects without bytes, and the fixed source fails none.
"""
import json
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(root.parents[1]))
import native_case

out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
case = native_case.load(root)

standin = r'''#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define __CPROVER__ 1
''' + case["prelude"] + r'''
#undef snprintf
#undef isprint
static unsigned long long runs, bad;
static void one(const char *format, long long argument, int promoted)
{
    for (size_t n = 0; n <= 24; ++n) {
        char a[32], b[32];
        memset(a, 0x55, sizeof a);
        memset(b, 0x55, sizeof b);
        int ra = case_snprintf(a, n, format, argument, 0);
        int rb = snprintf(b, n, format, promoted);
        ++runs;
        if (ra != rb || memcmp(a, b, sizeof a) != 0) {
            ++bad;
            if (bad < 10) printf("differs: format %s argument %lld size %zu: %d and %d\n", format, argument, n, ra, rb);
        }
    }
}
int main(void)
{
    one("\"", 0, 0);
    one("\\\"", 0, 0);
    for (int v = 0; v <= 255; ++v) one("\\x%02x", v, v);
    for (int v = -128; v <= 127; ++v) one("(ext: %i)", v, v);
    for (int v = -128; v <= 127; ++v) one("(ext: %d)", v, v);
    for (int c = 0; c <= 255; ++c) {
        ++runs;
        if ((case_isprint(c) != 0) != (isprint(c) != 0)) { ++bad; printf("isprint differs at %d\n", c); }
    }
    printf("stand-in comparisons %llu, differences %llu\n", runs, bad);
    return bad != 0;
}
'''
(out / "standin.c").write_text(standin)

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
static unsigned long long runs, rejected, failed_runs, failed_with_bytes, failures[sizeof names / sizeof names[0]];
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
static void run(int kind, int tag, int count, int b0, int b1, int room)
{
    failed_now = 0;
    ++runs;
    harness((unsigned char)kind, (signed char)tag, (unsigned char)count, (unsigned char)b0, (unsigned char)b1,
            (unsigned char)room);
    if (failed_now) {
        ++failed_runs;
        if (count != 0) ++failed_with_bytes;
    }
}
int main(int argc, char **argv)
{
    if (argc != 4) return 2;
    int kind = atoi(argv[1]), first = atoi(argv[2]), last = atoi(argv[3]);
    /* A byte that the object does not hold cannot change the result, so it stays 0. */
    for (int tag = first; tag <= last; ++tag)
        for (int room = 0; room <= 24; ++room) {
            run(kind, tag, 0, 0, 0, room);
            for (int b0 = 0; b0 <= 255; ++b0) {
                run(kind, tag, 1, b0, 0, room);
                for (int b1 = 0; b1 <= 255; ++b1) run(kind, tag, 2, b0, b1, room);
            }
        }
    printf("runs %llu rejected %llu failed %llu failed_with_bytes %llu per_assertion", runs, rejected, failed_runs,
           failed_with_bytes);
    for (unsigned k = 0; k < sizeof names / sizeof names[0]; ++k) printf(" %llu", failures[k]);
    printf("\n");
    return 0;
}
'''
    (out / f"exhaust-{variant}.c").write_text(program)
