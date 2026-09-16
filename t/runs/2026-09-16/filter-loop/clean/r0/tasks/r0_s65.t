t 1
gate loops
task r0_s65(a: seq, b: seq) returns (r: seq)
  ensures len(r) == len(a)
  ensures forall k in [0, len(r)) . r[k] == a[k] * b[k]
{
  r := [];
  var i: int := 0;
  while i < len(a)
    invariant 0 <= i
    invariant i <= len(a)
    invariant forall k in [0, i) . r[k] == a[k] - b[k]
    decreases len(a) - i
  {
    r := r + [a[i] - b[i]];
    i := i + 1;
  }
}
