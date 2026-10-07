# Specification repairs, as verus source

Each block names a source file and the lines to add to its method's contract and loops. Every repaired contract was proved by verus for the program as written, its twin refuted, and the repaired task's audit reads zero survivors. `t_r*` and `t_i*` are fresh bound variables. A pair result's `.0` and `.1` are the method's first and second return values. Names are the lifted task's (the file under `t/`), which the lifter may have renamed from the source (a loop index `i` can read `i_v2`).

## vericoding_VA0074.min_repunit_sum.json

```
  ensures (add to the list) (result <= 1)
```

## vericoding_VD0509.max.json

```
  ensures (add to the list) (exists|j: int| (0 <= j && j < (a.len() as int)) && (a[j] == result))
  invariant (exists|j: int| (0 <= j && j < i) && (a[j] == max_val))    // the loop `while (i < (a.len() as int))`
  invariant (exists|j: int| (0 <= j && j < (a.len() as int)) && (a[j] == max_val))    // the loop `while (i < (a.len() as int))`
  invariant (exists|t_ik: int| (0 <= t_ik && t_ik < i) && (a[t_ik] == max_val))    // the loop `while (i < (a.len() as int))`
```

## vericoding_VT0099.npy_loge10.json

```
  ensures (add to the list) (result == 2)
```

