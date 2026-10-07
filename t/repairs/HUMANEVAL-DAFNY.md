# Specification repairs, as dafny source

Each block names a source file and the lines to add to its method's contract and loops. Every repaired contract was proved by dafny for the program as written, its twin refuted, and the repaired task's audit reads zero survivors. `t_r*` and `t_i*` are fresh bound variables. A pair result's `.0` and `.1` are the method's first and second return values. Names are the lifted task's (the file under `t/`), which the lifter may have renamed from the source (a loop index `i` can read `i_v2`).

## humaneval_dafny_135_can_arrange.can_arrange.json

```
  ensures (-1 <= pos)
```

## humaneval_dafny_146_specialFilter.specialFilter.json

```
  ensures (forall t_rj: int :: (0 <= t_rj && t_rj < |s|) ==> ((((s[t_rj] > 10) && (s[t_rj] in s)) && (((first_digit(s[t_rj]) % 2) == 1) && ((last_digit(s[t_rj]) % 2) == 1))) ==> (s[t_rj] in r)))
  invariant (forall t_rj: int :: (0 <= t_rj && t_rj < i_v2) ==> ((((s[t_rj] > 10) && (s[t_rj] in s)) && (((first_digit(s[t_rj]) % 2) == 1) && ((last_digit(s[t_rj]) % 2) == 1))) ==> (s[t_rj] in r)))    // the loop `while (i_v2 < |s|)`
```

