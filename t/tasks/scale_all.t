t 1
task scale_all(a: array, k: int) returns (n: int)
  modifies a
  ensures n == len(a)
  ensures len(a) == len(old(a))
  ensures forall j in [0, len(a)) . a[j] == old(a)[j] * k
{
  parallel for i in [0, len(a))
    invariant len(a) == len(old(a))
    invariant forall j in [0, i) . a[j] == old(a)[j] * k
    invariant forall j in [i, len(a)) . a[j] == old(a)[j]
  {
    a[i] := a[i] * k;
  }
  n := len(a);
}
