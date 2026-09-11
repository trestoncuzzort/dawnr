# The string library, member by member (nl/ census, 2026-09-11)

24748 problems read the way COVERAGE-nl.md reads them; 13266 use the library (tagged `string-lib`, the gap, or `string-lib-v1`, the burden, since the 2026-09-11 split); 169 with the gap `string-lib` as their only gap (92 function-shaped, the census's sole blockers, and 77 stdin-shaped, which also wait on a signature); 6 of those use no member this scan sees (an f-string-free `str()`-free tag the census gives for `sorted` on a string, or a method reached through a value). Run time 80.7s.

## Members, by problems using them

First read on 2026-09-11 before nl_census.py split the tag (13,266 tagged, 3,103 sole: 298 function-shaped, 2,805 stdin; the greedy order that fixed v1's members was taken over that sole set, ROADMAP 12.7). Since the split this table counts the gap and the burden together as library use, and the sole set is the narrowed gap's: the members v1 covers no longer keep anything out.

| member | problems (all string-lib) | of which function-shaped | among the sole blockers |
|---|---:|---:|---:|
| split | 11193 | 236 | 46 |
| join | 2039 | 452 | 30 |
| str() | 1740 | 360 | 13 |
| strip | 936 | 30 | 8 |
| count | 917 | 136 | 9 |
| rstrip | 654 | 16 | 7 |
| format | 393 | 107 | 58 |
| encode | 351 | 7 | 0 |
| replace | 211 | 100 | 8 |
| f-string | 159 | 69 | 24 |
| find | 159 | 29 | 1 |
| lower | 147 | 104 | 5 |
| int(x,base) | 116 | 32 | 34 |
| upper | 69 | 47 | 3 |
| isdigit | 59 | 37 | 1 |
| isalpha | 58 | 39 | 2 |
| isupper | 40 | 24 | 0 |
| splitlines | 34 | 3 | 3 |
| startswith | 30 | 17 | 0 |
| islower | 26 | 17 | 0 |
| zfill | 24 | 4 | 2 |
| endswith | 20 | 7 | 0 |
| capitalize | 19 | 16 | 9 |
| swapcase | 18 | 17 | 7 |
| center | 13 | 8 | 4 |
| rjust | 10 | 5 | 3 |
| lstrip | 9 | 6 | 0 |
| ljust | 7 | 4 | 1 |
| title | 6 | 6 | 3 |
| partition | 3 | 3 | 0 |

## The greedy order over the sole blockers

Each step adds the member that covers the most sole-blocked problems whose whole member set is then covered.

| step | member | newly unlocked | cumulative | of which function-shaped |
|---|---|---:|---:|---:|
| 1 | format | 32 | 32 | 25 |
| 2 | split | 17 | 49 | 32 |
| 3 | int(x,base) | 16 | 65 | 36 |
| 4 | f-string | 16 | 81 | 44 |
| 5 | join | 17 | 98 | 53 |
| 6 | str() | 7 | 105 | 58 |
| 7 | capitalize | 7 | 112 | 64 |
| 8 | swapcase | 6 | 118 | 69 |
| 9 | rstrip | 5 | 123 | 70 |
| 10 | count | 5 | 128 | 71 |
| 11 | replace | 6 | 134 | 74 |
| 12 | strip | 6 | 140 | 76 |
| 13 | splitlines | 3 | 143 | 76 |
| 14 | center | 3 | 146 | 78 |
| 15 | lower | 3 | 149 | 80 |
| 16 | upper | 3 | 152 | 81 |
| 17 | title | 3 | 155 | 84 |
| 18 | rjust | 2 | 157 | 85 |
| 19 | zfill | 2 | 159 | 86 |
| 20 | isalpha | 1 | 160 | 86 |
| 21 | isdigit | 1 | 161 | 86 |
| 22 | ljust | 1 | 162 | 86 |
| 23 | find | 1 | 163 | 86 |

## Argument forms (call sites, all string-lib problems / among sole blockers)

| form | calls | calls among sole blockers |
|---|---:|---:|
| split() | 16005 | 37 |
| str() | 2985 | 22 |
| lit.join | 2473 | 32 |
| strip() | 1343 | 2 |
| split(lit) | 1246 | 10 |
| count(expr) | 760 | 3 |
| count(lit) | 614 | 13 |
| rstrip() | 425 | 3 |
| rstrip(chars) | 410 | 4 |
| find(expr) | 401 | 0 |
| format(1) | 359 | 44 |
| encode(1) | 332 | 0 |
| f-string | 295 | 41 |
| replace(lit,n) | 281 | 11 |
| lower(0) | 224 | 10 |
| format(2) | 194 | 30 |
| int(x,base) | 148 | 44 |
| lit.join(other) | 118 | 3 |
| find(lit) | 81 | 1 |
| upper(0) | 78 | 5 |
| isdigit(0) | 74 | 1 |
| expr.join | 71 | 2 |
| isalpha(0) | 67 | 4 |
| split(lit-multi) | 61 | 7 |
| strip(chars) | 55 | 7 |
| replace(expr,n) | 51 | 0 |
| format(3) | 48 | 5 |
| isupper(0) | 43 | 0 |
| endswith(lit) | 40 | 0 |
| split(expr) | 35 | 1 |
| splitlines(0) | 34 | 3 |
| zfill(1) | 30 | 2 |
| islower(0) | 29 | 0 |
| encode(0) | 28 | 0 |
| startswith(lit) | 26 | 0 |
| find(expr,n) | 23 | 0 |
| capitalize(0) | 22 | 11 |
| swapcase(0) | 21 | 8 |
| startswith(expr) | 18 | 0 |
| format(4) | 18 | 10 |
| find(lit,n) | 15 | 0 |
| center(1) | 15 | 7 |
| lstrip(chars) | 9 | 0 |
| rjust(1) | 9 | 3 |
| isalpha(1) | 9 | 0 |
| ljust(1) | 8 | 2 |
| title(0) | 6 | 3 |
| endswith(expr) | 6 | 0 |
| rjust(2) | 6 | 2 |
| replace(expr) | 6 | 0 |
| center(2) | 5 | 1 |
| partition(1) | 5 | 0 |
| split(sep,max) | 5 | 0 |
| count(lit,n) | 4 | 0 |
| format(5) | 3 | 1 |
| ljust(2) | 3 | 0 |
| lstrip() | 3 | 0 |
| startswith(expr,n) | 1 | 0 |
| encode(2) | 1 | 0 |
| format(9) | 1 | 0 |
| lower(1) | 1 | 0 |
| format(6) | 1 | 0 |

## Method

Reuses nl_census.py's readers by tapping its `solution_tags`; a member is a call `x.m(..)` with m in STRING_METHODS, an f-string, `str(..)`, or `int(x, base)`; `sorted` on a string is not seen here. Forms: `split()` is Python's whitespace split (runs collapsed, no empties), `split(lit)` a one-code-point separator, `split(lit-multi)` a longer literal, `split(expr)` a non-literal; `lit.join` a literal separator among the four common ones; `strip()` whitespace against `strip(chars)`.

