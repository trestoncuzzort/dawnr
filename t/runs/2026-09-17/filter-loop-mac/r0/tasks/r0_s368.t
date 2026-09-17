t 1
gate loops
task r0_s368(a: seq, b: seq) returns (c: seq)
  requires len(a) == len(b)
  ensures len(c) == len(a)
  ensures len(c) == len(a)
  ensures len(c) == len(a)
  ensures forall i in [0, len(c)) . c[i] == a[i] + b[i]
{
  c := seq(len(a), 0);
  var j: int := 0;
  while j < len(a)
    invariant len(c) == len(a)
    invariant 0 <= j and j <= len(c)
    invariant forall k in [0, j) . c[k] == a[k] + b[k]
    decreases len(a) - j
  {
    c := c[j := a[j] + b[j]];
    j := j + 1;
  }
}
