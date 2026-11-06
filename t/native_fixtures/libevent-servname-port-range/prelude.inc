/* What parse_numeric_servname needs besides its own text: strtol and NULL.
 *
 * CBMC 6.11.0 has a built-in strtol, but it is not exact. For "+ " (a sign and then no digit) it
 * sets the end pointer after the sign, where C11 7.22.1.4 paragraph 7 puts it at the start of the
 * string. parse_numeric_servname would then return 0 for "+" in the model and -1 with the C
 * library. So the model reads strtol as the stand-in below. The native replay of a counterexample
 * is compiled without __CPROVER__ and calls the C library.
 *
 * case_strtol follows C11 7.22.1.4 for base 10: white space as isspace in the C locale (space
 * and \t \n \v \f \r), an optional sign, decimal digits, the end pointer at the first character
 * that is not part of the number or at the start of the string when there is no digit, and
 * saturation at LONG_MAX and LONG_MIN. The base is a fixed parameter; for any other base it
 * converts nothing. It does not set errno (parse_numeric_servname does not read it). Its loops
 * stop at the terminator, so the unwinding bound of the case covers strings of up to 11
 * characters and the unwinding assertions say so. */
#include <limits.h>
#include <stddef.h>
#include <stdlib.h>

#ifdef __CPROVER__
static long case_strtol(const char *nptr, char **endptr, int base)
{
    const char *p = nptr;
    unsigned long limit, acc = 0;
    int negative = 0, any = 0, over = 0;

    if (base != 10) {
        if (endptr != NULL) {
            *endptr = (char *)nptr;
        }
        return 0;
    }
    while (*p == ' ' || (*p >= '\t' && *p <= '\r')) {
        ++p;
    }
    if (*p == '-' || *p == '+') {
        negative = *p == '-';
        ++p;
    }
    limit = negative ? (unsigned long)LONG_MAX + 1ul : (unsigned long)LONG_MAX;
    while (*p >= '0' && *p <= '9') {
        unsigned long digit = (unsigned long)(*p - '0');
        if (!over) {
            if (acc > (limit - digit) / 10ul) {
                over = 1;
            } else {
                acc = acc * 10ul + digit;
            }
        }
        any = 1;
        ++p;
    }
    if (endptr != NULL) {
        *endptr = (char *)(any ? p : nptr);
    }
    if (over) {
        return negative ? LONG_MIN : LONG_MAX;
    }
    if (negative) {
        return acc == (unsigned long)LONG_MAX + 1ul ? LONG_MIN : -(long)acc;
    }
    return (long)acc;
}
#define strtol(nptr, endptr, base) case_strtol(nptr, endptr, base)
#endif
