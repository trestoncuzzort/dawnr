t 1
gate quantifiers
task r0_s68(s: seq) returns (r: seq)
  ensures len(r) == len(s) + (len(s) - 1)
  ensures forall i in [0, len(r)) . r[i] >= 97 and r[i] <= 122 or r[i] == 95
{
  r := [];
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i
    invariant i <= len(s)
    invariant len(r) <= i
    invariant forall k in [0, i) . r[k] >= 97 and r[k] <= 122 or r[k] == 95
    decreases len(s) - i
  {
    if i > 0 and s[i] >= 65 and s[i] <= 90 {
      r := r + [s[i]];
    } else {
    }
    i := i + 1;
  }
}
