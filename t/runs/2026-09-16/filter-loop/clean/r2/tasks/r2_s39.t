t 1
gate loops
task r2_s39(v: seq) returns (i: int)
  requires len(v) > 0
  ensures 0 <= i
  ensures i < len(v)
  ensures forall k in [0, len(v)) . v[i] >= v[k]
  ensures forall k in [0, len(v)) . v[i] >= v[k]
{
  var j: int := 1;
  i := 0;
  while j < len(v)
    invariant 0 <= j and j <= len(v)
    invariant 0 <= j and j <= len(v)
    invariant forall k_v in [0, j) . v[i] >= v[k_v]
    decreases len(v) - j
  {
    if v[j] > v[i] {
      i := j;
    } else {
    }
    j := j + 1;
  }
}
