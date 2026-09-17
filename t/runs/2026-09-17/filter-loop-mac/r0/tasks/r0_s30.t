t 1
gate recursion
task r0_s30(a: seq) returns (m: int)
  requires len(a) > 0
  ensures forall k in [0, len(a)) . m <= a[k]
  ensures exists k_v in [0, len(a)) . m == a[k_v]
{
  m := a[0];
  var i: int := 1;
  m := 1;
  while i < len(a)
    invariant 0 <= i and i <= len(a)
    invariant forall k_v in [0, i) . m < len(a)
    invariant forall k_v in [0, i) . m < len(a)
    invariant forall k_v in [0, i) . m <= a[k_v]
    decreases len(a) - i
  {
    if a[i] > m {
      m := a[i];
    } else {
    }
    i := i + 1;
  }
}
