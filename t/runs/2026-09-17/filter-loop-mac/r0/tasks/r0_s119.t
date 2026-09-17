t 1
gate loops
task r0_s119(a: seq) returns (m: int)
  requires len(a) > 0
  ensures forall k in [0, len(a)) . m <= a[k]
  ensures exists k_v in [0, len(a)) . m == a[k_v]
  ensures forall k_v in [0, len(a)) . m <= a[k_v]
{
  m := a[0];
  var i: int := 1;
  m := a[0];
  while i < len(a)
    invariant 0 <= i and i <= len(a)
    invariant forall k in [0, i) . m < len(a)
    invariant exists k_v in [0, i) . m == a[k_v]
    invariant forall k_v in [0, i) . m <= a[k_v]
    invariant i >= 0
    decreases len(a) - i
  {
    if a[i] > a[m] {
      m := a[i];
    } else {
      m := a[i];
    }
    i := i + 1;
  }
}
