# framac: building nested sequences, executable lower, a pair with a seq component

Design written 2026-09-12 for the builder of the next framac wave, from the
lowering's own notes (lower_framac.py: THE ENCODING for seq returns, the
seq<seq> PARAMETER encoding, CAPACITY mode, the seq equality loop of
wave K). It closes, in order: fz_p_nest_empty, fz_p_str_splitempty,
fz_p_str_tab (nested returns and locals), fz_p_str_lowernonletter (an
executable lower), fz_p_pair_seq and dafny_synthesis 262 splitArray (a
pair whose component is a seq), and the sweep rows 240 replaceLastElement
and 586 splitAndAppend whose concat shapes fall out of the same bounds.
Every item is measured cell by cell; a step that does not land is named
with WP's message, as before.

## 1. The representation is the one a parameter already has

A seq<seq> PARAMETER is `int *m_data, int *m_off, int m_n` (row count
`m_n`, row `k` is `m_data[m_off[k] .. m_off[k+1])`, total `m_off[m_n]`).
A seq<seq> RETURN is the same triple appended to the signature as OUTPUT
parameters, writable and `\separated` from every other buffer, exactly
as a plain seq return is the plain pair `int *r, int r_n`. A seq<seq>
LOCAL is the same triple as extra caller-provided scratch parameters
(the t contract never sees them; WP does): no VLA, no malloc, the same
move a return makes, so `stmts()`'s `var` case stops refusing nested
locals. ACSL reads a built row set exactly as it reads a parameter, so
`_seq_len_render`, `_seq_at_render`, `defs()` and `at_asserts` need no
new rendering for reads: `len(r)` is the row count, `len(at(r,k))` is
`r_off[k+1] - r_off[k]`, `at(at(r,k),j)` is `r_data[r_off[k] + j]`.

## 2. Two capacities instead of one, both from params

CAPACITY mode today pins ONE buffer size from an `ensures`-stated bound
(`_ret_capacity`). A row set needs two: ROWS (the offsets array holds
ROWS + 1 entries) and DATA (the flat buffer). `_seq_len_track` gains a
nested case returning a pair of t Exprs over params, closed forms, never
a copy:

| expression | rows bound | data bound |
|---|---|---|
| `[]` | 0 | 0 |
| a nested literal | its row count | the sum of its rows' lengths |
| `m` (a seq<seq> param) | `len(m)` | `total(m)`, rendered `m_off[m_n]` |
| `update(m, i, row)` | `len(m)` | `total(m) + len(row)` |
| `m + [row]` | `rows(m) + 1` | `data(m) + len(row)` |
| `split(s, sep)`, `split_ws(s)` | `len(s) + 1` | `len(s)` |
| a loop appending one row per iteration over `i < E` | `rows(init) + E` | `data(init) + E * rowbound` when every appended row is a slice of one param (bound `len(s)`), else refuse by name |

A bound that has no closed form over params is refused by name, as the
plain seq case already does. The C function returns the ROW COUNT as
`\result` and leaves the total in `r_off[\result]`; `requires` pins
`\valid(r_off + (0 .. ROWS))` and `\valid(r_data + (0 .. DATA - 1))`.
`ensures` renders `len(r)` as `\result` in this mode, the way CAPACITY
mode renders a plain seq return's length.

## 3. Building in C

- `r := []`: `r_off[0] = 0; rows = 0;`.
- `r := r + [row]` where `row` renders as a (pointer, length) view (a
  param row `at(m,k)`, a slice, a literal): a copy loop into
  `r_data + r_off[rows]` with invariant `r_data[r_off[rows] + t] ==
  row[t]` for `t` below the counter, then `r_off[rows+1] = r_off[rows] +
  len(row); rows += 1`. The loop invariant also carries the monotone
  offsets fact and `r_off[rows] <= DATA`, both from the bounds above.
- `update(m, i, row)` into a fresh row set: copy rows `0..i`, append
  `row`, copy rows `i+1..len(m)`; three append loops, no new mechanism.
- `split_ws(s)` and `split(s, sep)`: a scanning loop over `s` that
  appends a row at each separator. The ACSL side: the string library's
  own logic definition of split (the recursive definitions wave G added
  for count and find are the pattern; add one for split if only an
  axiomatic model exists) and the invariant "rows appended so far equal
  the split of `s[0 .. i]`". This is the riskiest step: measure
  fz_p_str_splitempty first (an empty separator, one row per character
  or one row of the whole string, read SPEC.md's rule), and if WP does
  not close the invariant, land the nested return machinery on
  fz_p_nest_empty and fz_p_str_tab alone and name split's goal.

## 4. An executable lower and upper

`r := lower(s)`: length `len(s)` (a param expression, so plain CAPACITY
mode, no new bound), one loop mapping each cell through the same C
expression the ACSL logic `lower_c` states, invariant `r[t] == lower_c(
s[t])` for `t` below the counter; `upper` the same. The ACSL definition
of `lower_c` already exists for the spec side; the C body is the case
split on the letter range that definition states.

## 5. A pair with a seq component

A pair is a C99 compound literal today (both components scalar). With a
seq component, the pair's seq is a caller-provided buffer (data, length)
like any seq return, and the scalar component is `\result` or a second
out parameter; ACSL renders `fst(r)` and `snd(r)` as the buffer view or
the scalar, so `defs()` and the certificate see ordinary seq and int
terms. `_check_pair_types`'s refusal narrows to a pair of two seqs (two
buffers, the same trick twice) only if that shape appears; today no task
has it.

## 6. What must not change

The plain seq CAPACITY mode, the seq<seq> parameter encoding, the
certificate functions (another builder's territory when both run), and
the 34 committed tasks' framac column cell for cell. The regression bar
of the wave applies: the framac conformance column with no PASS lost,
the sweep's framac cells that read verified / refuted unmoved.
