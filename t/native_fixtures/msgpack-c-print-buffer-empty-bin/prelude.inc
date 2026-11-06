/* What msgpack_object_print_buffer needs besides its own text.
 *
 * The type definitions are lines 27-98 of include/msgpack/object.h of msgpack-c
 * (https://github.com/msgpack/msgpack-c) at the pinned revision, copied unchanged. That
 * file carries this notice:
 *
 * MessagePack for C dynamic typing routine
 *
 * Copyright (C) 2008-2009 FURUHASHI Sadayuki
 *
 *    Distributed under the Boost Software License, Version 1.0.
 *    (See accompanying file LICENSE_1_0.txt or copy at
 *    http://www.boost.org/LICENSE_1_0.txt)
 */
#include <ctype.h>
#include <inttypes.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* include/msgpack/object.h, lines 27-98 */
typedef enum {
    MSGPACK_OBJECT_NIL                  = 0x00,
    MSGPACK_OBJECT_BOOLEAN              = 0x01,
    MSGPACK_OBJECT_POSITIVE_INTEGER     = 0x02,
    MSGPACK_OBJECT_NEGATIVE_INTEGER     = 0x03,
    MSGPACK_OBJECT_FLOAT32              = 0x0a,
    MSGPACK_OBJECT_FLOAT64              = 0x04,
    MSGPACK_OBJECT_FLOAT                = 0x04,
#if defined(MSGPACK_USE_LEGACY_NAME_AS_FLOAT)
    MSGPACK_OBJECT_DOUBLE               = MSGPACK_OBJECT_FLOAT, /* obsolete */
#endif /* MSGPACK_USE_LEGACY_NAME_AS_FLOAT */
    MSGPACK_OBJECT_STR                  = 0x05,
    MSGPACK_OBJECT_ARRAY                = 0x06,
    MSGPACK_OBJECT_MAP                  = 0x07,
    MSGPACK_OBJECT_BIN                  = 0x08,
    MSGPACK_OBJECT_EXT                  = 0x09
} msgpack_object_type;


struct msgpack_object;
struct msgpack_object_kv;

typedef struct {
    uint32_t size;
    struct msgpack_object* ptr;
} msgpack_object_array;

typedef struct {
    uint32_t size;
    struct msgpack_object_kv* ptr;
} msgpack_object_map;

typedef struct {
    uint32_t size;
    const char* ptr;
} msgpack_object_str;

typedef struct {
    uint32_t size;
    const char* ptr;
} msgpack_object_bin;

typedef struct {
    int8_t type;
    uint32_t size;
    const char* ptr;
} msgpack_object_ext;

typedef union {
    bool boolean;
    uint64_t u64;
    int64_t  i64;
#if defined(MSGPACK_USE_LEGACY_NAME_AS_FLOAT)
    double   dec; /* obsolete*/
#endif /* MSGPACK_USE_LEGACY_NAME_AS_FLOAT */
    double   f64;
    msgpack_object_array array;
    msgpack_object_map map;
    msgpack_object_str str;
    msgpack_object_bin bin;
    msgpack_object_ext ext;
} msgpack_object_union;

typedef struct msgpack_object {
    msgpack_object_type type;
    msgpack_object_union via;
} msgpack_object;

typedef struct msgpack_object_kv {
    msgpack_object key;
    msgpack_object val;
} msgpack_object_kv;

#ifdef __CPROVER__
/* The model has no body for the __ctype_b_loc() of the C library header and no snprintf that
 * writes the text, so it reads isprint and snprintf as the functions below. The native replay
 * of a counterexample is compiled without __CPROVER__ and calls the C library.
 *
 * case_isprint is isprint in the C locale (C11 7.4.1.8).
 *
 * case_snprintf follows C11 7.21.6.5 for what the BIN and EXT branches pass: ordinary
 * characters and at most one of %i or %d with an int and %02x with an unsigned int. It takes
 * that one argument as a fixed parameter and does not read the others. It returns -1 for
 * every other directive, and msgpack_object_print_buffer then returns 0. The digits are
 * written without a loop, so that the unwinding bound of the case stays small. */
static int case_isprint(int c)
{
    return c >= 0x20 && c <= 0x7e;
}

static int case_put(char *s, size_t n, int at, char c)
{
    if (n != 0 && (size_t)at < n - 1) {
        s[at] = c;
    }
    return at + 1;
}

#define CASE_DECIMAL(power) \
    if (value >= power || power == 1u) at = case_put(s, n, at, digit[value / power % 10u])
#define CASE_HEX(shift) \
    if (value >> shift != 0u || shift <= 4) at = case_put(s, n, at, digit[value >> shift & 15u])

static int case_snprintf(char *s, size_t n, const char *format, long long argument, ...)
{
    static const char digit[] = "0123456789abcdef";
    unsigned int value;
    int at = 0, used = 0;

    for (; *format != '\0'; ++format) {
        if (*format != '%') {
            at = case_put(s, n, at, *format);
        } else if (used) {
            return -1;
        } else if (format[1] == 'i' || format[1] == 'd') {
            int number = (int)argument;
            value = number < 0 ? 0u - (unsigned int)number : (unsigned int)number;
            if (number < 0) {
                at = case_put(s, n, at, '-');
            }
            CASE_DECIMAL(1000000000u); CASE_DECIMAL(100000000u); CASE_DECIMAL(10000000u);
            CASE_DECIMAL(1000000u); CASE_DECIMAL(100000u); CASE_DECIMAL(10000u);
            CASE_DECIMAL(1000u); CASE_DECIMAL(100u); CASE_DECIMAL(10u); CASE_DECIMAL(1u);
            used = 1;
            format += 1;
        } else if (format[1] == '0' && format[2] == '2' && format[3] == 'x') {
            value = (unsigned int)argument;
            CASE_HEX(28); CASE_HEX(24); CASE_HEX(20); CASE_HEX(16);
            CASE_HEX(12); CASE_HEX(8); CASE_HEX(4); CASE_HEX(0);
            used = 1;
            format += 3;
        } else {
            return -1;
        }
    }
    if (n != 0) {
        s[(size_t)at < n ? (size_t)at : n - 1] = '\0';
    }
    return at;
}
#undef isprint
#define isprint(c) case_isprint(c)
#define snprintf(s, n, ...) case_snprintf(s, n, __VA_ARGS__, 0)
#endif
