t 1
task r1_s492(a: seq) returns (m: int)
  requires len(a) > 0
  ensures forall i in [0, len(a)) . m <= a[i]
  ensures exists i_v in [0, len(a)) . m == a[i_v]
  ensures forall i_v in [0, len(a)) . m <= a[i_v]
{
  var n: int := 0;
  m := a[0];
  while n != len(a)
    invariant 1 <= n and n <= len(a)
    invariant exists i_v in [0, len(a)) . m == a[i_v]
    invariant forall i_v in [0, n) . m <= a[i_v]
    invariant exists i_v in [0, len(a)) . m == a[i_v]
    decreases if n <= len(a) then len(a) - len(a) - n else n - len(a)
  {
    if a[n] < m {
      m := a[n];
    } else {
    }
    n := n + 1;
  }
}
