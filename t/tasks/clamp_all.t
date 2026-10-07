t 1
task clamp_all(a: array, lo: int, hi: int) returns (n: int)
  modifies a
  requires lo <= hi
  ensures n == len(a)
  ensures len(a) == len(old(a))
  ensures forall k in [0, len(a)) . a[k] == min(max(old(a)[k], lo), hi)
{
  var i: int := 0;
  while i < len(a)
    invariant 0 <= i and i <= len(a)
    invariant len(a) == len(old(a))
    invariant forall k in [0, i) . a[k] == min(max(old(a)[k], lo), hi)
    invariant forall k in [i, len(a)) . a[k] == old(a)[k]
    decreases len(a) - i
  {
    a[i] := min(max(a[i], lo), hi);
    i := i + 1;
  }
  n := len(a);
}
