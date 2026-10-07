t 1
task nearest_index(d: seq) returns (k: int)
  requires len(d) > 0
  ensures 0 <= k and k < len(d)
  ensures forall j in [0, len(d)) . d[k] <= d[j]
{
  k := 0;
  var i: int := 1;
  while i < len(d)
    invariant 1 <= i and i <= len(d)
    invariant 0 <= k and k < i
    invariant forall j in [0, i) . d[k] <= d[j]
    decreases len(d) - i
  {
    if d[i] < d[k] {
      k := i;
    }
    i := i + 1;
  }
}
