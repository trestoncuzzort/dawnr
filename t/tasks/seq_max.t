t 1
gate quantifiers
task seq_max(s: seq) returns (r: int)
  requires len(s) > 0
  ensures forall i in [0, len(s)) . r >= s[i]
  ensures exists i in [0, len(s)) . r == s[i]
{
  r := s[0];
  var i: int := 1;
  while i < len(s)
    invariant forall j in [0, i) . j < len(s) ==> r >= s[j]
    invariant exists j in [0, i) . j < len(s) and r == s[j]
    invariant i >= 1
    decreases len(s) - i
  {
    if s[i] > r {
      r := s[i];
    } else {
    }
    i := i + 1;
  }
}
