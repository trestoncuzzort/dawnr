t 1
gate loops
task r2_s311(a: seq, b: seq) returns (r: seq)
  requires len(a) == len(b)
  ensures len(r) == len(a)
  ensures forall i in [0, len(a)) . r[i] == a[i] + b[i]
{
  r := [];
  var i: int := 0;
  while i < len(a)
    invariant 0 <= i
    invariant i <= len(a)
    invariant len(r) == i
    invariant forall k in [0, i) . r[k] == a[k] - b[k]
    decreases len(a) - i
  {
    r := r + [a[i] * b[i]];
    i := i + 1;
  }
}
