/* Models of the number parsing in <stdlib.h>.
 *
 * CBMC 6.11.0 has no strtoul, strtoll, strtoull or atoll, and its strtol differs from C11 on many inputs: it takes 2 as a
 * digit in base 2, moves the end pointer past a lone sign, and leaves it unset on overflow (t/PREDICT-2026-11-05-native-models.md).
 * This follows C11 7.22.1.4. Where the standard leaves a choice this does what glibc does, since the native replay runs
 * glibc: an invalid base sets errno to EINVAL and leaves the end pointer alone, and no digits leaves errno alone.
 * Without the C2X `0b` prefix, as in C11. errno comes from glibc's __errno_location, whose values these are on Linux.
 * No assumptions and no CBMC intrinsics: cross_check.py compares every function with the C library.
 */
int *__errno_location(void);
#define DAWNR_EINVAL 22
#define DAWNR_ERANGE 34

static int dawnr_digit(char c)
{
    if (c >= '0' && c <= '9') {
        return c - '0';
    }
    if (c >= 'a' && c <= 'z') {
        return c - 'a' + 10;
    }
    if (c >= 'A' && c <= 'Z') {
        return c - 'A' + 10;
    }
    return 99;
}

/* Reads the number, sets the end pointer, and returns its magnitude, or above the limit after an overflow. */
static unsigned long long dawnr_scan(const char *nptr, char **endptr, int base, unsigned long long positive, unsigned long long negative, int *is_negative, int *overflow)
{
    const char *s = nptr;
    *is_negative = 0;
    *overflow = 0;
    if (base < 0 || base == 1 || base > 36) {
        *__errno_location() = DAWNR_EINVAL;
        return 0;
    }
    while (*s == ' ' || (*s >= '\t' && *s <= '\r')) {
        ++s;
    }
    if (*s == '+' || *s == '-') {
        *is_negative = *s == '-';
        ++s;
    }
    /* A 0x prefix counts only when a hex digit follows it. Otherwise the number is the 0, and it ends at the x. */
    if ((base == 0 || base == 16) && s[0] == '0' && (s[1] == 'x' || s[1] == 'X') && dawnr_digit(s[2]) < 16) {
        s += 2;
        base = 16;
    } else if (base == 0) {
        base = s[0] == '0' ? 8 : 10;
    }
    unsigned long long limit = *is_negative ? negative : positive, value = 0;
    const char *first = s;
    for (; dawnr_digit(*s) < base; ++s) {
        /* The builtins and not a division: a 64-bit division is a very large circuit for a SAT solver, once per digit.
           A first version divided, and flac took more than 5 times as long as with its own stand-ins. */
        unsigned long long next;
        if (__builtin_mul_overflow(value, (unsigned long long)base, &next) || __builtin_add_overflow(next, (unsigned long long)dawnr_digit(*s), &next) || next > limit) {
            *overflow = 1;
        } else {
            value = next;
        }
    }
    if (endptr != 0) {
        *endptr = (char *)(s == first ? nptr : s);
    }
    if (*overflow) {
        *__errno_location() = DAWNR_ERANGE;
    }
    return value;
}

long strtol(const char *nptr, char **endptr, int base)
{
    int is_negative, overflow;
    unsigned long long value = dawnr_scan(nptr, endptr, base, (unsigned long long)__LONG_MAX__, (unsigned long long)__LONG_MAX__ + 1, &is_negative, &overflow);
    if (overflow) {
        return is_negative ? -__LONG_MAX__ - 1L : __LONG_MAX__;
    }
    return is_negative ? (long)(0 - (unsigned long)value) : (long)value;
}

long long strtoll(const char *nptr, char **endptr, int base)
{
    int is_negative, overflow;
    unsigned long long value = dawnr_scan(nptr, endptr, base, (unsigned long long)__LONG_LONG_MAX__, (unsigned long long)__LONG_LONG_MAX__ + 1, &is_negative, &overflow);
    if (overflow) {
        return is_negative ? -__LONG_LONG_MAX__ - 1LL : __LONG_LONG_MAX__;
    }
    return is_negative ? (long long)(0 - value) : (long long)value;
}

unsigned long strtoul(const char *nptr, char **endptr, int base)
{
    int is_negative, overflow;
    unsigned long long largest = (unsigned long long)__LONG_MAX__ * 2 + 1;
    unsigned long long value = dawnr_scan(nptr, endptr, base, largest, largest, &is_negative, &overflow);
    if (overflow) {
        return (unsigned long)largest;
    }
    return is_negative ? 0 - (unsigned long)value : (unsigned long)value;
}

unsigned long long strtoull(const char *nptr, char **endptr, int base)
{
    int is_negative, overflow;
    unsigned long long largest = (unsigned long long)__LONG_LONG_MAX__ * 2 + 1;
    unsigned long long value = dawnr_scan(nptr, endptr, base, largest, largest, &is_negative, &overflow);
    if (overflow) {
        return largest;
    }
    return is_negative ? 0 - value : value;
}

int atoi(const char *nptr)
{
    return (int)strtol(nptr, 0, 10);
}

long atol(const char *nptr)
{
    return strtol(nptr, 0, 10);
}

long long atoll(const char *nptr)
{
    return strtoll(nptr, 0, 10);
}
