t 1
gate loops
task r0_s364(s: seq) returns (r: seq)
  ensures len(r) == len(s)
  ensures forall i in [0, len(r)) . exists j in [0, len(s)) . r[i] == s[j]
{
  r := [];
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i
    invariant i <= len(s)
    invariant len(r) <= i
    decreases len(s) - i
  {
    if s[i] < 65 and s[i] < 122 {
      r := r + [s[i]];
    } else {
    }
    i := i + 1;
  }
}
