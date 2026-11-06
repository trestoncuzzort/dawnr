/* Compare the models with the C library over a stated domain. Built and run by cross_check.py.
 *
 * Every string of up to STRING_LENGTH bytes over a small alphabet that includes a byte above 127, against every set of up to
 * SET_LENGTH bytes; every int in the table range for <ctype.h>; every string of up to NUMBER_LENGTH bytes over an alphabet
 * chosen for number parsing, in valid and invalid bases, plus values on each side of each limit in each base.
 * For each call: the return value, the end pointer and errno, and for functions that write, the bytes they leave.
 * Prints each of the first differences, and a last line of JSON with the counts.
 */
#include <ctype.h>
#include <errno.h>
#include <gnu/libc-version.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* _GNU_SOURCE would turn strtol into the C2X one, which takes a 0b prefix, and the native replay does not define it. */
extern void *memrchr(const void *, int, size_t);
extern char *strchrnul(const char *, int);
extern size_t strnlen(const char *, size_t);
extern char *strsep(char **, const char *);
extern char *strtok_r(char *, const char *, char **);
extern char *strndup(const char *, size_t);

extern size_t model_strnlen(const char *, size_t);
extern size_t model_strspn(const char *, const char *);
extern size_t model_strcspn(const char *, const char *);
extern char *model_strpbrk(const char *, const char *);
extern char *model_strstr(const char *, const char *);
extern void *model_memchr(const void *, int, size_t);
extern void *model_memrchr(const void *, int, size_t);
extern char *model_strchrnul(const char *, int);
extern char *model_strsep(char **, const char *);
extern char *model_strtok_r(char *, const char *, char **);
extern char *model_strtok(char *, const char *);
extern char *model_strndup(const char *, size_t);
extern long model_strtol(const char *, char **, int);
extern long long model_strtoll(const char *, char **, int);
extern unsigned long model_strtoul(const char *, char **, int);
extern unsigned long long model_strtoull(const char *, char **, int);
extern int model_atoi(const char *);
extern long model_atol(const char *);
extern long long model_atoll(const char *);
extern const unsigned short **model_ctype_b_loc(void);
extern const int **model_ctype_tolower_loc(void);
extern const int **model_ctype_toupper_loc(void);
extern const unsigned short **strict_ctype_b_loc(void);
extern const int **strict_ctype_tolower_loc(void);
extern const int **strict_ctype_toupper_loc(void);

static long long compared, different;

#define CHECK(condition, ...) do { ++compared; if (!(condition)) { if (different++ < 40) { printf(__VA_ARGS__); printf("\n"); } } } while (0)

static const char *shown(const char *s)
{
    static char text[8][300];
    static int next;
    char *out = text[next = (next + 1) % 8], *p = out;
    for (; *s && p < out + 280; ++s) {
        p += (unsigned char)*s >= 32 && (unsigned char)*s < 127 ? sprintf(p, "%c", *s) : sprintf(p, "\\x%02x", (unsigned char)*s);
    }
    *p = 0;
    return out;
}

static long offset(const void *p, const void *base)
{
    return p ? (long)((const char *)p - (const char *)base) : -1;
}

/* Fill out with string number `code` of length `length` over alphabet. */
static void make(char *out, int length, long code, const char *alphabet, int size)
{
    for (int i = 0; i < length; ++i) {
        out[i] = alphabet[code % size];
        code /= size;
    }
    out[length] = 0;
}

static long power(int base, int exponent)
{
    long value = 1;
    while (exponent-- > 0) {
        value *= base;
    }
    return value;
}

static void check_sequences(const char *s, const char *set)
{
    /* Zeroed, since the bytes after the terminator are compared too: a function must not write there. */
    char a[16] = {0}, b[16] = {0}, *pa = a, *pb = b, *ra, *rb;
    strcpy(a, s);
    strcpy(b, s);
    do {
        ra = model_strsep(&pa, set);
        rb = strsep(&pb, set);
        CHECK(offset(ra, a) == offset(rb, b) && offset(pa, a) == offset(pb, b) && memcmp(a, b, sizeof a) == 0, "strsep \"%s\" \"%s\": %ld, %ld", shown(s), shown(set), offset(ra, a), offset(rb, b));
    } while (ra && rb);
    char c[16] = {0}, d[16] = {0}, *sa = 0, *sb = 0;
    strcpy(c, s);
    strcpy(d, s);
    ra = model_strtok_r(c, set, &sa);
    rb = strtok_r(d, set, &sb);
    for (;;) {
        CHECK(offset(ra, c) == offset(rb, d) && memcmp(c, d, sizeof c) == 0, "strtok_r \"%s\" \"%s\": %ld, %ld", shown(s), shown(set), offset(ra, c), offset(rb, d));
        if (!ra || !rb) {
            break;
        }
        ra = model_strtok_r(0, set, &sa);
        rb = strtok_r(0, set, &sb);
    }
    memset(c, 0, sizeof c);
    memset(d, 0, sizeof d);
    strcpy(c, s);
    strcpy(d, s);
    ra = model_strtok(c, set);
    rb = strtok(d, set);
    for (;;) {
        CHECK(offset(ra, c) == offset(rb, d) && memcmp(c, d, sizeof c) == 0, "strtok \"%s\" \"%s\": %ld, %ld", shown(s), shown(set), offset(ra, c), offset(rb, d));
        if (!ra || !rb) {
            break;
        }
        ra = model_strtok(0, set);
        rb = strtok(0, set);
    }
}

static void check_strings(int string_length, int set_length)
{
    static const char alphabet[] = {'a', 'b', 'c', (char)0xff};
    char s[16], set[16];
    for (int ls = 0; ls <= string_length; ++ls) {
        for (long cs = 0; cs < power(4, ls); ++cs) {
            make(s, ls, cs, alphabet, 4);
            for (int lt = 0; lt <= set_length; ++lt) {
                for (long ct = 0; ct < power(4, lt); ++ct) {
                    make(set, lt, ct, alphabet, 4);
                    CHECK(model_strspn(s, set) == strspn(s, set), "strspn \"%s\" \"%s\"", shown(s), shown(set));
                    CHECK(model_strcspn(s, set) == strcspn(s, set), "strcspn \"%s\" \"%s\"", shown(s), shown(set));
                    CHECK(model_strpbrk(s, set) == strpbrk(s, set), "strpbrk \"%s\" \"%s\"", shown(s), shown(set));
                    CHECK(model_strstr(s, set) == strstr(s, set), "strstr \"%s\" \"%s\": %ld, %ld", shown(s), shown(set), offset(model_strstr(s, set), s), offset(strstr(s, set), s));
                    check_sequences(s, set);
                }
            }
            static const int values[] = {'a', 'b', 'c', 0xff, -1, 0, 'a' + 256};
            for (size_t v = 0; v < sizeof values / sizeof *values; ++v) {
                CHECK(model_strchrnul(s, values[v]) == strchrnul(s, values[v]), "strchrnul \"%s\" %d", shown(s), values[v]);
                for (int n = 0; n <= ls + 1; ++n) {
                    CHECK(model_memchr(s, values[v], (size_t)n) == memchr(s, values[v], (size_t)n), "memchr \"%s\" %d %d", shown(s), values[v], n);
                    CHECK(model_memrchr(s, values[v], (size_t)n) == memrchr(s, values[v], (size_t)n), "memrchr \"%s\" %d %d", shown(s), values[v], n);
                }
            }
            for (int n = 0; n <= ls + 2; ++n) {
                CHECK(model_strnlen(s, (size_t)n) == strnlen(s, (size_t)n), "strnlen \"%s\" %d", shown(s), n);
                char *a = model_strndup(s, (size_t)n), *b = strndup(s, (size_t)n);
                CHECK(strcmp(a, b) == 0, "strndup \"%s\" %d", shown(s), n);
                free(a);
                free(b);
            }
        }
    }
}

static void check_number(const char *s)
{
    static const int bases[] = {0, 2, 8, 10, 16, 36, -1, 1, 37};
    for (size_t b = 0; b < sizeof bases / sizeof *bases; ++b) {
        int base = bases[b];
#define COMPARE(function, format) do { \
            char *end_model = (char *)1, *end_real = (char *)1; \
            errno = 0; \
            __typeof__(function(s, 0, base)) model = model_##function(s, &end_model, base); \
            int errno_model = errno; \
            errno = 0; \
            __typeof__(function(s, 0, base)) real = function(s, &end_real, base); \
            int errno_real = errno; \
            CHECK(model == real && end_model == end_real && errno_model == errno_real, \
                  #function " \"%s\" base %d: " format " end %ld errno %d, C library " format " end %ld errno %d", shown(s), base, model, \
                  end_model == (char *)1 ? -9L : offset(end_model, s), errno_model, real, end_real == (char *)1 ? -9L : offset(end_real, s), errno_real); \
            errno = 0; \
            CHECK(model_##function(s, 0, base) == function(s, 0, base), #function " without an end pointer \"%s\" base %d", shown(s), base); \
        } while (0)
        COMPARE(strtol, "%ld");
        COMPARE(strtoll, "%lld");
        COMPARE(strtoul, "%lu");
        COMPARE(strtoull, "%llu");
    }
    CHECK(model_atoi(s) == atoi(s), "atoi \"%s\"", shown(s));
    CHECK(model_atol(s) == atol(s), "atol \"%s\"", shown(s));
    CHECK(model_atoll(s) == atoll(s), "atoll \"%s\"", shown(s));
}

static void render(unsigned __int128 value, int base, char *out)
{
    char reversed[140];
    int n = 0;
    do {
        int digit = (int)(value % (unsigned)base);
        reversed[n++] = (char)(digit < 10 ? '0' + digit : 'a' + digit - 10);
        value /= (unsigned)base;
    } while (value);
    while (n) {
        *out++ = reversed[--n];
    }
    *out = 0;
}

static void check_numbers(int number_length)
{
    static const char alphabet[] = " \t+-0178" "9afgxXz\n";
    int size = (int)sizeof alphabet - 1;
    char s[64];
    for (int length = 0; length <= number_length; ++length) {
        for (long code = 0; code < power(size, length); ++code) {
            make(s, length, code, alphabet, size);
            check_number(s);
        }
    }
    /* Each side of each limit, in each base, with each sign and prefix, and with something after it. */
    static const int bases[] = {2, 8, 10, 16, 36};
    const unsigned __int128 limits[] = {(unsigned __int128)LONG_MAX, (unsigned __int128)LONG_MAX + 1, (unsigned __int128)LONG_MAX + 2, (unsigned __int128)ULONG_MAX,
                                        (unsigned __int128)ULONG_MAX + 1, (unsigned __int128)ULONG_MAX + 2, ((unsigned __int128)ULONG_MAX + 1) * 36};
    static const char *const before[] = {"", "+", "-", " ", "\t-", "0", "-0", "0x", "-0x", "0X", "000000000000000000000000000000000000000"};
    static const char *const after[] = {"", "z", " ", "0", "!"};
    char digits[140], text[260];
    for (size_t b = 0; b < sizeof bases / sizeof *bases; ++b) {
        for (size_t l = 0; l < sizeof limits / sizeof *limits; ++l) {
            render(limits[l], bases[b], digits);
            for (size_t p = 0; p < sizeof before / sizeof *before; ++p) {
                for (size_t a = 0; a < sizeof after / sizeof *after; ++a) {
                    snprintf(text, sizeof text, "%s%s%s", before[p], digits, after[a]);
                    /* check_number takes a short buffer only for its messages, so this is safe at this length. */
                    check_number(text);
                }
            }
        }
    }
}

static void check_table(const char *name, const unsigned short **(*b)(void), const int **(*lower)(void), const int **(*upper)(void), int first)
{
    const unsigned short *real_b = *__ctype_b_loc(), *model_b = *b();
    const int *real_lower = *__ctype_tolower_loc(), *model_lower = *lower();
    const int *real_upper = *__ctype_toupper_loc(), *model_upper = *upper();
    for (int c = first; c <= 255; ++c) {
        CHECK(model_b[c] == real_b[c], "%s class of %d: %#x, C library %#x", name, c, model_b[c], real_b[c]);
        CHECK(model_lower[c] == real_lower[c], "%s tolower of %d: %d, C library %d", name, c, model_lower[c], real_lower[c]);
        CHECK(model_upper[c] == real_upper[c], "%s toupper of %d: %d, C library %d", name, c, model_upper[c], real_upper[c]);
    }
}

int main(int argc, char **argv)
{
    if (argc != 4) {
        return 2;
    }
    setvbuf(stdout, 0, _IONBF, 0);
    check_table("ctype", model_ctype_b_loc, model_ctype_tolower_loc, model_ctype_toupper_loc, -128);
    check_table("ctype_strict", strict_ctype_b_loc, strict_ctype_tolower_loc, strict_ctype_toupper_loc, -1);
    long long table_calls = compared;
    check_strings(atoi(argv[1]), atoi(argv[2]));
    long long string_calls = compared - table_calls;
    check_numbers(atoi(argv[3]));
    long long number_calls = compared - table_calls - string_calls;
    printf("{\"compared\": %lld, \"different\": %lld, \"table\": %lld, \"strings\": %lld, \"numbers\": %lld, \"glibc\": \"%s\"}\n", compared, different, table_calls, string_calls, number_calls, gnu_get_libc_version());
    return different != 0;
}
