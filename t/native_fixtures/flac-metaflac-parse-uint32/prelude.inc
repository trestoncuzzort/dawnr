/* What parse_uint32, parse_uint64 and parse_add_padding of src/metaflac/options.c of xiph/flac
 * (https://github.com/xiph/flac) need besides their own text.
 *
 * Copied unchanged from the same revision of the project:
 *   - include/FLAC/ordinals.h, lines 1-31 (the licence notice, below) and lines 38-53 (the integer types);
 *   - src/libFLAC/format.c, line 115 (the definition of FLAC__STREAM_METADATA_LENGTH_LEN);
 *   - src/metaflac/options.c, lines 116, 117 and 122 (the prototypes of the three functions).
 *
 * The notice below is that of include/FLAC/ordinals.h (BSD-3-Clause, Xiph.Org Foundation).
 * include/FLAC/assert.h and src/libFLAC/format.c carry the same notice. src/metaflac/options.c is
 * GPL-2.0-or-later; its notice is the head of original.c and fixed.c.
 */

/* libFLAC - Free Lossless Audio Codec library
 * Copyright (C) 2000-2009  Josh Coalson
 * Copyright (C) 2011-2025  Xiph.Org Foundation
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * - Redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer.
 *
 * - Redistributions in binary form must reproduce the above copyright
 * notice, this list of conditions and the following disclaimer in the
 * documentation and/or other materials provided with the distribution.
 *
 * - Neither the name of the Xiph.org Foundation nor the names of its
 * contributors may be used to endorse or promote products derived from
 * this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE FOUNDATION OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 * PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
 * LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
 * NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 * SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include <assert.h>
#include <limits.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

/* include/FLAC/ordinals.h, lines 38-53 */
#include <stdint.h>
#include <stdbool.h>

typedef int8_t FLAC__int8;
typedef uint8_t FLAC__uint8;

typedef int16_t FLAC__int16;
typedef int32_t FLAC__int32;
typedef int64_t FLAC__int64;
typedef uint16_t FLAC__uint16;
typedef uint32_t FLAC__uint32;
typedef uint64_t FLAC__uint64;

typedef int FLAC__bool;

typedef FLAC__uint8 FLAC__byte;

/* FLAC__ASSERT as include/FLAC/assert.h lines 41-44 define it for a build without NDEBUG and
 * without FUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION: the C library assert. */
#define FLAC__ASSERT(x) assert(x)

/* src/libFLAC/format.c, line 115. FLAC_API is empty in a static build (include/FLAC/export.h). */
#define FLAC_API
FLAC_API const uint32_t FLAC__STREAM_METADATA_LENGTH_LEN = 24; /* bits */

/* src/metaflac/options.c, lines 116, 117 and 122 */
static FLAC__bool parse_uint32(const char *src, FLAC__uint32 *dest);
static FLAC__bool parse_uint64(const char *src, FLAC__uint64 *dest);
static FLAC__bool parse_add_padding(const char *in, unsigned *out);

#ifdef __CPROVER__
/* The model has no body for strspn, strtoul and strtoull, and its strlen adds goals that the assumption
 * coverage stage of the gate counts. It reads the four functions as the ones below.
 * The native replay of a counterexample is compiled without __CPROVER__ and calls the C library.
 *
 * What the three functions of this case pass is a string of decimal digits: parse_uint32 and
 * parse_uint64 call strtoul and strtoull only after strspn has shown that every character is
 * a decimal digit and that there is at least one, and the harness calls parse_add_padding only
 * with such strings. The stand-ins cover that and no more.
 *
 * case_strtoull follows C11 7.22.1.4 (https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf)
 * for base 10 and a string that does not start with white space or a sign: the longest run of
 * decimal digits is the number, the end pointer is set after it (to the start when there is no
 * digit), and a number above ULLONG_MAX gives ULLONG_MAX. A string that starts with white
 * space or a sign fails the property case_strtoull.covered, and a base other than 10 fails the
 * property case_strtoull.base. unsigned long and unsigned long long have the same width on
 * LP64, so case_strtoul is case_strtoull.
 *
 * case_strspn is strspn (C11 7.24.5.6) for the accept set "0123456789" only; any other set
 * fails the property case_strspn.accept. case_strlen is strlen (C11 7.24.6.3). Every loop ends
 * at the NUL byte of the string. */
_Static_assert(sizeof(unsigned long) == sizeof(unsigned long long), "case_strtoul needs LP64");

static int case_digit(char c)
{
    return c >= '0' && c <= '9';
}

static size_t case_strlen(const char *s)
{
    size_t n = 0;
    while (s[n] != '\0') {
        ++n;
    }
    return n;
}

static size_t case_strspn(const char *s, const char *accept)
{
    size_t n = 0;
    __CPROVER_assert(accept[0] == '0' && accept[1] == '1' && accept[2] == '2' && accept[3] == '3' &&
                     accept[4] == '4' && accept[5] == '5' && accept[6] == '6' && accept[7] == '7' &&
                     accept[8] == '8' && accept[9] == '9' && accept[10] == '\0', "case_strspn.accept");
    while (case_digit(s[n])) {
        ++n;
    }
    return n;
}

static unsigned long long case_strtoull(const char *nptr, char **endptr, int base)
{
    unsigned long long value = 0;
    int saturated = 0;
    const char *p = nptr;

    __CPROVER_assert(base == 10, "case_strtoull.base");
    __CPROVER_assert(!(*nptr == ' ' || (*nptr >= '\t' && *nptr <= '\r') || *nptr == '+' || *nptr == '-'),
                     "case_strtoull.covered");
    while (case_digit(*p)) {
        unsigned int digit = (unsigned int)(*p - '0');
        if (saturated || value > ULLONG_MAX / 10u || (value == ULLONG_MAX / 10u && digit > ULLONG_MAX % 10u)) {
            saturated = 1;
            value = ULLONG_MAX;
        } else {
            value = value * 10u + digit;
        }
        ++p;
    }
    if (endptr != 0) {
        *endptr = (char *)p;
    }
    return value;
}

static unsigned long case_strtoul(const char *nptr, char **endptr, int base)
{
    return (unsigned long)case_strtoull(nptr, endptr, base);
}

#define strlen(s) case_strlen(s)
#define strspn(s, accept) case_strspn(s, accept)
#define strtoul(nptr, endptr, base) case_strtoul(nptr, endptr, base)
#define strtoull(nptr, endptr, base) case_strtoull(nptr, endptr, base)
#endif
