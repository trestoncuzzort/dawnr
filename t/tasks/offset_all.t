t 1
task offset_all(a: array, b: array) returns (n: int)
  modifies a
  requires len(a) == len(b)
  ensures n == len(a)
  ensures len(a) == len(old(a))
  ensures forall j in [0, len(a)) . a[j] == old(a)[j] - b[j]
{
  parallel for i in [0, len(a))
    invariant len(a) == len(old(a))
    invariant forall j in [0, i) . a[j] == old(a)[j] - b[j]
    invariant forall j in [i, len(a)) . a[j] == old(a)[j]
  {
    a[i] := a[i] - b[i];
  }
  n := len(a);
}
