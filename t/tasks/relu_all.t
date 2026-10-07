t 1
task relu_all(a: array) returns (n: int)
  modifies a
  ensures n == len(a)
  ensures len(a) == len(old(a))
  ensures forall j in [0, len(a)) . a[j] == max(old(a)[j], 0)
  ensures forall j in [0, len(a)) . a[j] >= 0
{
  parallel for i in [0, len(a))
    invariant len(a) == len(old(a))
    invariant forall j in [0, i) . a[j] == max(old(a)[j], 0)
    invariant forall j in [i, len(a)) . a[j] == old(a)[j]
  {
    var v: int := a[i];
    if v < 0 {
      a[i] := 0;
    }
  }
  n := len(a);
}
