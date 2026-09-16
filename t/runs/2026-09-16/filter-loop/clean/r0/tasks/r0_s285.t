t 1
gate loops
task r0_s285(s: seq) returns (r: seq)
  ensures len(r) == len(s)
  ensures forall i in [0, len(s)) . r[i] == s[i] * s[i]
{
  r := [];
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i
    invariant i <= len(s)
    invariant len(r) == i
    invariant forall k in [0, i) . r[k] == s[k] * s[k]
    decreases len(s) - i
  {
    r := r + [s[i] * s[i]];
    i := i + 1;
  }
}
