# Specification repairs, as dafny source

Each block names a source file and the lines to add to its method's contract and loops. Every repaired contract was proved by dafny for the program as written, its twin refuted, and the repaired task's audit reads zero survivors. `t_r*` and `t_i*` are fresh bound variables. A pair result's `.0` and `.1` are the method's first and second return values. Names are the lifted task's (the file under `t/`), which the lifter may have renamed from the source (a loop index `i` can read `i_v2`).

## vericoding_DA0426.solve.json

```
  ensures (|result| == |input|)
```

## vericoding_DA0483.solve.json

```
  ensures ((result == [89, 101, 115]) || (result == [78, 111]))
```

## vericoding_DA0623.solve.json

```
  ensures ((result == [89, 69, 83]) || (result == [78, 79]))
```

## vericoding_DA0662.solve.json

```
  ensures (result == n)
```

## vericoding_DD0643.SharedElements.json

```
  ensures (forall t_rj: int :: (0 <= t_rj && t_rj < |a|) ==> ((inArray(a, a[t_rj]) && inArray(b, a[t_rj])) ==> (a[t_rj] in result)))
  invariant (forall t_rj: int :: (0 <= t_rj && t_rj < i_v4) ==> ((inArray(a, a[t_rj]) && inArray(b, a[t_rj])) ==> (a[t_rj] in result)))    // the loop `while (i_v4 < h)`
```

## vericoding_DJ0130.FindFirstOdd.json

```
  ensures (-1 <= index)
```

## vericoding_DJ0135.ArithmeticWeird.json

```
  ensures (result == 9)
```

## vericoding_DV0042.MaxStrength.json

```
  ensures (forall t_rk: int :: (0 <= t_rk && t_rk < |nums|) ==> (nums[t_rk] <= result))
  invariant (forall t_rk: int :: (0 <= t_rk && t_rk < i_v) ==> (nums[t_rk] <= result))    // the loop `while (i_v < |nums|)`
  invariant (exists t_ik: int :: (0 <= t_ik && t_ik < i_v) && (nums[t_ik] == result))    // the loop `while (i_v < |nums|)`
```

## vericoding_DV0117.FindFirstOccurrence.json

```
  ensures (-1 <= result)
```

