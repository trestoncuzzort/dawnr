# Specification repair

For each task whose spec admits a survivor (`t/audit.py`), the clauses `t/contract_repair.py` adds: each holds for the real program at every domain point, and together they kill every survivor they can. **after** is the repaired task's own audit, from scratch.

- tasks with survivors: 6; repaired to zero survivors: 2
- refused because the real body never reads its parameters: 0
- dafny: repaired contract proved for the real body, twin refuted: 2 of 2

| task | survivors before | after | dafny real / twin | clauses added |
|---|---|---|---|---|
| humaneval_dafny_006_parse_nested_parens__parse_paren_group | 45 | 35 | unproved / refuted | `max_depth <= len(s)` |
| humaneval_dafny_010_is_palindrome__make_palindrome | 4 | 4 |  /  | (none found) |
| humaneval_dafny_031_is_prime__is_prime | 1 | 1 |  /  | (none found) |
| humaneval_dafny_135_can_arrange__can_arrange | 2 | 0 | verified / refuted | `-1 <= pos` |
| humaneval_dafny_146_specialfilter__specialFilter | 13 | 0 | verified / refuted | `forall t_rj in [0, len(s)) . (s[t_rj] > 10 and (exists k in [0, len(s)) . s[k] == s[t_rj])) and (first_digit(s[t_rj]) % 2 == 1 and last_digit(s[t_rj]) % 2 == 1) ==> (exists t_rm in [0, len(r)) . r[t_rm] == s[t_rj])` |
| humaneval_dafny_163_generate_integers__generate_integers | 25 | 25 |  /  | (none found) |
