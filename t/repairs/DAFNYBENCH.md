# Specification repairs, as dafny source

Each block names a source file and the lines to add to its method's contract and loops. Every repaired contract was proved by dafny for the program as written, its twin refuted, and the repaired task's audit reads zero survivors. `t_r*` and `t_i*` are fresh bound variables. A pair result's `.0` and `.1` are the method's first and second return values. Names are the lifted task's (the file under `t/`), which the lifter may have renamed from the source (a loop index `i` can read `i_v2`).

## bbfny_tmp_tmpw4m0jvl0_enjoying.MultipleReturns.json

```
  ensures (r.1 == (x + (-y)))
```

## cmsc433_tmp_tmpe3ob3a0o_dafny_project1_p1-assignment-2.PlusOne.json

```
  ensures (y == (x + 1))
```

## cs245-verification_tmp_tmp0h_nxhqp_A8_Q2.A8Q1.json

```
  ensures (((m == x) || (m == y)) || (m == z))
```

## dafny-learn_tmp_tmpn94ir40q_R01_assertions.Max.json

```
  ensures ((c == a) || (c == b))
```

## Dafny_Programs_tmp_tmp99966ew4_mymax.Max.json

```
  ensures ((c == a) || (c == b))
```

## dafny-synthesis_task_id_145.MaxDifference.json

```
  ensures (exists i: int :: (0 <= i && i < |a|) && (exists j: int :: (0 <= j && j < |a|) && ((a[i] - a[j]) == diff)))
  invariant (exists t_ik: int :: (0 <= t_ik && t_ik < i_v) && (a[t_ik] == maxVal))    // the loop `while (i_v < h)`
  invariant (exists t_ik: int :: (0 <= t_ik && t_ik < i_v) && (a[t_ik] == minVal))    // the loop `while (i_v < h)`
```

## dafny-synthesis_task_id_161.RemoveElements.json

```
  ensures (forall t_rj: int :: (0 <= t_rj && t_rj < |a|) ==> ((inArray(a, a[t_rj]) && (!inArray(b, a[t_rj]))) ==> (a[t_rj] in result)))
  invariant (forall t_rj: int :: (0 <= t_rj && t_rj < i_v2) ==> ((inArray(a, a[t_rj]) && (!inArray(b, a[t_rj]))) ==> (a[t_rj] in res)))    // the loop `while (i_v2 < h)`
```

## dafny-synthesis_task_id_249.Intersection.json

```
  ensures (forall t_rj: int :: (0 <= t_rj && t_rj < |a|) ==> ((inArray(a, a[t_rj]) && inArray(b, a[t_rj])) ==> (a[t_rj] in result)))
  invariant (forall t_rj: int :: (0 <= t_rj && t_rj < i_v2) ==> ((inArray(a, a[t_rj]) && inArray(b, a[t_rj])) ==> (a[t_rj] in res)))    // the loop `while (i_v2 < h)`
```

## dafny-synthesis_task_id_2.SharedElements.json

```
  ensures (forall t_rj: int :: (0 <= t_rj && t_rj < |a|) ==> ((inArray(a, a[t_rj]) && inArray(b, a[t_rj])) ==> (a[t_rj] in result)))
  invariant (forall t_rj: int :: (0 <= t_rj && t_rj < i_v2) ==> ((inArray(a, a[t_rj]) && inArray(b, a[t_rj])) ==> (a[t_rj] in res)))    // the loop `while (i_v2 < h)`
```

## Dafny_tmp_tmp0wu8wmfr_tests_F1a.F.json

```
  ensures (r == 0)
```

## Dafny_tmp_tmpmvs2dmry_examples1.MultiReturn.json

```
  ensures (r.1 == (x + (-y)))
  ensures (r.0 == (x + y))
```

## Dafny_Verify_tmp_tmphq7j0row_dataset_C_convert_examples_11.main.json

```
  ensures (r.1 == x)
```

## Dafny_Verify_tmp_tmphq7j0row_dataset_C_convert_examples_15.main.json

```
  ensures (k_out == ((-n) + k))
```

## Dafny_Verify_tmp_tmphq7j0row_Fine_Tune_Examples_error_data_completion_11.main.json

```
  ensures (r.1 == x)
```

## Dafny_Verify_tmp_tmphq7j0row_Generated_Code_15.main.json

```
  ensures (k_out == ((-n) + k))
```

## Dafny_Verify_tmp_tmphq7j0row_Test_Cases_Index.ReconstructFromMaxSum.json

```
  ensures (r.0 == m)
```

## Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula2.m4.json

```
  ensures (z == (x == y))
```

## Software-building-and-verification-Projects_tmp_tmp5tm1srrn_CVS-projeto_aula2.max.json

```
  ensures (a <= z)
  ensures (b <= z)
  ensures ((z == a) || (z == b))
```

## stunning-palm-tree_tmp_tmpr84c2iwh_ch1.ReconstructFromMaxSum.json

```
  ensures (r.0 == m)
```

