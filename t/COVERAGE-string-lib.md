# The string library, member by member (nl/ census, 2026-09-11)

24748 problems read the way COVERAGE-nl.md reads them; 13266 tagged `string-lib`; 3103 with `string-lib` as their only gap (298 function-shaped, the census's sole blockers, and 2805 stdin-shaped, which also wait on a signature); 6 of those use no member this scan sees (an f-string-free `str()`-free tag the census gives for `sorted` on a string, or a method reached through a value). Run time 50.8s.

## Members, by problems using them

| member | problems (all string-lib) | of which function-shaped | among the sole blockers |
|---|---:|---:|---:|
| split | 11193 | 236 | 2481 |
| join | 2039 | 452 | 276 |
| str() | 1740 | 360 | 308 |
| strip | 936 | 30 | 149 |
| count | 917 | 136 | 210 |
| rstrip | 654 | 16 | 29 |
| format | 393 | 107 | 58 |
| encode | 351 | 7 | 0 |
| replace | 211 | 100 | 57 |
| f-string | 159 | 69 | 24 |
| find | 159 | 29 | 25 |
| lower | 147 | 104 | 33 |
| int(x,base) | 116 | 32 | 34 |
| upper | 69 | 47 | 20 |
| isdigit | 59 | 37 | 18 |
| isalpha | 58 | 39 | 14 |
| isupper | 40 | 24 | 11 |
| splitlines | 34 | 3 | 3 |
| startswith | 30 | 17 | 7 |
| islower | 26 | 17 | 5 |
| zfill | 24 | 4 | 2 |
| endswith | 20 | 7 | 8 |
| capitalize | 19 | 16 | 9 |
| swapcase | 18 | 17 | 7 |
| center | 13 | 8 | 4 |
| rjust | 10 | 5 | 3 |
| lstrip | 9 | 6 | 1 |
| ljust | 7 | 4 | 1 |
| title | 6 | 6 | 3 |
| partition | 3 | 3 | 0 |

## The greedy order over the sole blockers

Each step adds the member that covers the most sole-blocked problems whose whole member set is then covered.

| step | member | newly unlocked | cumulative | of which function-shaped |
|---|---|---:|---:|---:|
| 1 | split | 2075 | 2075 | 22 |
| 2 | str() | 183 | 2258 | 57 |
| 3 | join | 202 | 2460 | 99 |
| 4 | count | 182 | 2642 | 135 |
| 5 | strip | 142 | 2784 | 139 |
| 6 | format | 53 | 2837 | 171 |
| 7 | replace | 44 | 2881 | 193 |
| 8 | int(x,base) | 29 | 2910 | 202 |
| 9 | rstrip | 25 | 2935 | 204 |
| 10 | find | 25 | 2960 | 214 |
| 11 | lower | 23 | 2983 | 230 |
| 12 | f-string | 22 | 3005 | 240 |
| 13 | upper | 14 | 3019 | 247 |
| 14 | isdigit | 12 | 3031 | 256 |
| 15 | isalpha | 11 | 3042 | 261 |
| 16 | capitalize | 9 | 3051 | 268 |
| 17 | isupper | 8 | 3059 | 271 |
| 18 | swapcase | 7 | 3066 | 277 |
| 19 | islower | 5 | 3071 | 280 |
| 20 | endswith | 4 | 3075 | 283 |
| 21 | startswith | 7 | 3082 | 285 |
| 22 | splitlines | 3 | 3085 | 285 |
| 23 | center | 3 | 3088 | 287 |
| 24 | title | 3 | 3091 | 290 |
| 25 | rjust | 2 | 3093 | 291 |
| 26 | zfill | 2 | 3095 | 292 |
| 27 | ljust | 1 | 3096 | 292 |
| 28 | lstrip | 1 | 3097 | 292 |

## Argument forms (call sites, all string-lib problems / among sole blockers)

| form | calls | calls among sole blockers |
|---|---:|---:|
| split() | 16005 | 3047 |
| str() | 2985 | 492 |
| lit.join | 2473 | 298 |
| strip() | 1343 | 209 |
| split(lit) | 1246 | 253 |
| count(expr) | 760 | 105 |
| count(lit) | 614 | 294 |
| rstrip() | 425 | 32 |
| rstrip(chars) | 410 | 4 |
| find(expr) | 401 | 4 |
| format(1) | 359 | 44 |
| encode(1) | 332 | 0 |
| f-string | 295 | 41 |
| replace(lit,n) | 281 | 66 |
| lower(0) | 224 | 75 |
| format(2) | 194 | 30 |
| int(x,base) | 148 | 44 |
| lit.join(other) | 118 | 19 |
| find(lit) | 81 | 20 |
| upper(0) | 78 | 23 |
| isdigit(0) | 74 | 21 |
| expr.join | 71 | 5 |
| isalpha(0) | 67 | 16 |
| split(lit-multi) | 61 | 7 |
| strip(chars) | 55 | 7 |
| replace(expr,n) | 51 | 10 |
| format(3) | 48 | 5 |
| isupper(0) | 43 | 12 |
| endswith(lit) | 40 | 21 |
| split(expr) | 35 | 1 |
| splitlines(0) | 34 | 3 |
| zfill(1) | 30 | 2 |
| islower(0) | 29 | 6 |
| encode(0) | 28 | 0 |
| startswith(lit) | 26 | 8 |
| find(expr,n) | 23 | 5 |
| capitalize(0) | 22 | 11 |
| swapcase(0) | 21 | 8 |
| startswith(expr) | 18 | 3 |
| format(4) | 18 | 10 |
| find(lit,n) | 15 | 5 |
| center(1) | 15 | 7 |
| lstrip(chars) | 9 | 0 |
| rjust(1) | 9 | 3 |
| isalpha(1) | 9 | 0 |
| ljust(1) | 8 | 2 |
| title(0) | 6 | 3 |
| endswith(expr) | 6 | 4 |
| rjust(2) | 6 | 2 |
| replace(expr) | 6 | 0 |
| center(2) | 5 | 1 |
| partition(1) | 5 | 0 |
| split(sep,max) | 5 | 0 |
| count(lit,n) | 4 | 3 |
| format(5) | 3 | 1 |
| ljust(2) | 3 | 0 |
| lstrip() | 3 | 3 |
| startswith(expr,n) | 1 | 0 |
| encode(2) | 1 | 0 |
| format(9) | 1 | 0 |
| lower(1) | 1 | 0 |
| format(6) | 1 | 0 |

## Method

Reuses nl_census.py's readers by tapping its `solution_tags`; a member is a call `x.m(..)` with m in STRING_METHODS, an f-string, `str(..)`, or `int(x, base)`; `sorted` on a string is not seen here. Forms: `split()` is Python's whitespace split (runs collapsed, no empties), `split(lit)` a one-code-point separator, `split(lit-multi)` a longer literal, `split(expr)` a non-literal; `lit.join` a literal separator among the four common ones; `strip()` whitespace against `strip(chars)`.

