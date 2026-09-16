t 1
task r1_s6(v: seq) returns (i: int)
  requires len(v) > 0
  requires len(v) > 0
  ensures 0 <= i
  ensures i < len(v)
  ensures forall k in [0, len(v)) . v[i] >= v[k]
{
  var j: int := 1;
  i := 0;
  while j < len(v)
    invariant 0 <= j and j <= len(v)
    invariant 0 <= j and j <= len(v)
    invariant 0 <= i and i <= len(v)
    invariant forall k in [0, i) . v[i] > v[k]
    decreases len(v) - j
  {
    if v[j] > v[i] {
      i := j;
    } else {
    }
    j := j + 1;
  }
}
