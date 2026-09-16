t 1
gate loops
task r0_s254(s: seq) returns (r: seq)
  ensures len(r) <= len(s)
  ensures forall i in [0, len(r)) . forall j in [0, len(r)) . r[i] >= r[j]
{
  r := [];
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i
    invariant i <= len(s)
    invariant len(r) == i / 2
    invariant forall k in [0, len(r)) . r[k] == s[2 * k]
    decreases len(s) - i
  {
    r := r + [s[i]];
    i := i + 1;
  }
}
