t 1
task reverse_in_place(a: array) returns (n: int)
  modifies a
  ensures n == len(a)
  ensures a == rev(old(a))
{
  var i: int := 0;
  while i < len(a) / 2
    invariant 0 <= i and i <= len(a) / 2
    invariant forall k in [0, i) . a[k] == old(a)[len(a) - 1 - k] and a[len(a) - 1 - k] == old(a)[k]
    invariant forall k in [i, len(a) - i) . a[k] == old(a)[k]
    decreases len(a) / 2 - i
  {
    var tmp: int := a[i];
    a[i] := a[len(a) - 1 - i];
    a[len(a) - 1 - i] := tmp;
    i := i + 1;
  }
  n := len(a);
}
