t 1
task r1_s382(s: seq) returns (r: seq)
  ensures len(r) == len(s)
  ensures forall i in [0, len(s)) . s[i] == 32 or s[i] == 44 or s[i] == 46 ==> r[i] == 58
  ensures forall i in [0, len(s)) . not (s[i] == 32 or s[i] == 44 or s[i] == 46) ==> r[i] == s[i]
{
  r := [];
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i
    invariant i <= len(s)
    invariant len(r) == i
    invariant forall k in [0, i) . r[k] == s[len(s) - 1 - k]
    decreases len(s) - i
  {
    r := r + [s[i] * s[i]];
    i := i + 1;
  }
}
