t 1
gate loops
task filter_pos(s: seq) returns (r: seq)
  ensures len(r) <= len(s)
  ensures forall k in [0, len(r)) . r[k] > 0
{
  r := [];
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i
    invariant i <= len(s)
    invariant len(r) <= i
    invariant forall k in [0, len(r)) . r[k] > 0
    decreases len(s) - i
  {
    if s[i] > 0 {
      r := r + [s[i]];
    } else {
    }
    i := i + 1;
  }
}
