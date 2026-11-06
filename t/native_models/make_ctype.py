#!/usr/bin/env python3
"""Write ctype.c and ctype_strict.c: the tables glibc's <ctype.h> macros read, for the C locale.

    python3 t/native_models/make_ctype.py

glibc's isdigit is a macro over `(*__ctype_b_loc())[(int)(c)] & _ISdigit`, and CBMC 6.11.0 has no __ctype_b_loc, so
the macro cannot run under the model. The tables are written from the classes of C11 7.4.1 in the C locale, using the
bit layout of glibc's <ctype.h> on a little-endian machine. cross_check.py compares them with the C library.

`ctype` has the range glibc tolerates, -128 to 255. `ctype_strict` has C11 7.4's range, EOF and the values of unsigned
char, so that a negative char, which is undefined behaviour glibc tolerates, leaves the table and fails a property.

Source: the bit layout is _ISbit in glibc's ctype/ctype.h (sourceware.org/git/glibc.git).
"""
from pathlib import Path


def bit(index: int) -> int:
    return (1 << index) << 8 if index < 8 else (1 << index) >> 8


UPPER, LOWER, ALPHA, DIGIT, XDIGIT, SPACE, PRINT, GRAPH, BLANK, CNTRL, PUNCT, ALNUM = (bit(index) for index in range(12))


def classes(value: int) -> int:
    """The classes of an unsigned char value in the C locale. Nothing above 127 is in any class there."""
    if not 0 <= value <= 127:
        return 0
    char, flags = chr(value), 0
    if char.isupper():
        flags |= UPPER | ALPHA | ALNUM | PRINT | GRAPH
    if char.islower():
        flags |= LOWER | ALPHA | ALNUM | PRINT | GRAPH
    if char.isdigit():
        flags |= DIGIT | ALNUM | PRINT | GRAPH
    if char in "0123456789abcdefABCDEF":
        flags |= XDIGIT
    if char in " \t\n\v\f\r":
        flags |= SPACE
    if char in " \t":
        flags |= BLANK
    if value < 32 or value == 127:
        flags |= CNTRL
    if value == 32:
        flags |= PRINT
    if 33 <= value <= 126 and not char.isalnum():
        flags |= PUNCT | PRINT | GRAPH
    return flags


def lower(value: int) -> int:
    return value + 32 if 65 <= value <= 90 else value


def upper(value: int) -> int:
    return value - 32 if 97 <= value <= 122 else value


def rows(values: list[int]) -> str:
    return "".join("    " + ", ".join(str(value) for value in values[start:start + 16]) + ",\n" for start in range(0, len(values), 16))


def table(first: int) -> str:
    """The three tables, from `first` up to 255. Values below 0 other than EOF read as the same value plus 256."""
    indices = list(range(first, 256))
    # glibc gives the classes of c + 256 for a negative char: none in the C locale, and EOF has none either.
    flags = [classes(index) if index >= 0 else 0 for index in indices]
    # Its case tables also read c + 256 for a negative char, except that EOF stays EOF. Measured by cross_check.py.
    moved = lambda index, change: change(index) if index >= 0 else index if index == -1 else index + 256
    lowered = [moved(index, lower) for index in indices]
    raised = [moved(index, upper) for index in indices]
    offset = -first
    return (f"static const unsigned short dawnr_ctype_b[{len(indices)}] = {{\n{rows(flags)}}};\n"
            f"static const int dawnr_ctype_tolower[{len(indices)}] = {{\n{rows(lowered)}}};\n"
            f"static const int dawnr_ctype_toupper[{len(indices)}] = {{\n{rows(raised)}}};\n"
            f"static const unsigned short *dawnr_ctype_b_ptr = dawnr_ctype_b + {offset};\n"
            f"static const int *dawnr_ctype_tolower_ptr = dawnr_ctype_tolower + {offset};\n"
            f"static const int *dawnr_ctype_toupper_ptr = dawnr_ctype_toupper + {offset};\n\n"
            "const unsigned short **__ctype_b_loc(void)\n{\n    return &dawnr_ctype_b_ptr;\n}\n\n"
            "const int **__ctype_tolower_loc(void)\n{\n    return &dawnr_ctype_tolower_ptr;\n}\n\n"
            "const int **__ctype_toupper_loc(void)\n{\n    return &dawnr_ctype_toupper_ptr;\n}\n")


HEADER = """/* Written by make_ctype.py. Do not edit: run it again.
 *
 * The tables glibc's <ctype.h> macros read, in the C locale, for %s.
 * cross_check.py compares them with the C library.
 */
"""


def main() -> None:
    here = Path(__file__).resolve().parent
    (here / "ctype.c").write_bytes((HEADER % "-128 to 255, the range glibc tolerates" + table(-128)).encode())
    (here / "ctype_strict.c").write_bytes((HEADER % "EOF and the values of unsigned char, as in C11 7.4: a negative char leaves the table" + table(-1)).encode())


if __name__ == "__main__":
    main()
