# The 5 Dafny-proved survivors in HumanEval-Dafny, read by hand

In `t/AUDIT-HUMANEVAL-DAFNY.md`, Dafny proves the real solution and a one-edit program that computes something different at a ground input, against the same specification, in 5 tasks (2026-10-07):

- **gap** (5): the specification admits a result that is wrong for the task;
- **no spec** (0): the contract is a tautology;
- **latitude** (0): the specification deliberately allows several answers (ties, a sentinel, a value that does not matter).

| class | task | why | the proved survivor: change at input |
|---|---|---|---|
| gap | humaneval_dafny_006_parse_nested_parens__parse_paren_group | `max_depth >= 0` only | collapse-if: `if c == 40 {` -> `depth := depth + 1;` at s=[41] -> real 0, twin 1 |
| gap | humaneval_dafny_010_is_palindrome__make_palindrome | any palindrome starting with s up to twice its length; the shortest is not required | wrong-var#5: `var reversed: seq := humaneval_dafny_010_is_palindrome__reverse(prefix_to_reverse);` -> `var reversed: seq := humaneval_dafny_010_is_palindrome__reverse(s);` at s=[0] -> real [0], twin [0, 0] |
| gap | humaneval_dafny_135_can_arrange__can_arrange | no `pos >= -1`: a constant -2 satisfies every clause on every input | off-by-one#2: `pos := -(1);` -> `pos := -(2);` at arr=[0] -> real -1, twin -2 |
| gap | humaneval_dafny_146_specialfilter__specialFilter | only `result within the filter`, never the converse | off-by-one#3: `while i_v2 < len(s)` -> `while i_v2 < len(s) + -1` at s=[11] -> real [11], twin [] |
| gap | humaneval_dafny_163_generate_integers__generate_integers | only `result within the even digits`, never the converse | compare-flip: `while i_v2 <= upper` -> `while i_v2 < upper` at a=0, b=2 -> real [2], twin [] |
