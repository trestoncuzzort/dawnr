t 1
gate loops
task r0_s176(a: seq, b: seq) returns (c: seq)
  requires len(a) == len(b)
  ensures len(c) == len(a)
  ensures len(c) == len(a)
  ensures forall i in [0, len(c)) . c[i] == a[i] + b[i]
{
  c := seq(len(a), 0);
  var i_v: int := 0;
  while i_v < len(a)
    invariant 0 <= i_v and i_v <= len(a)
    invariant forall j in [0, i_v) . a[j] * b[j] == c[j]
    decreases len(a) - i_v
  {
    c := c[i_v := a[i_v] * b[i_v]];
    i_v := i_v + 1;
  }
}
