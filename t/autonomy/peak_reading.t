t 1
task peak_reading(s: seq) returns (m: int)
  requires len(s) > 0
  ensures forall k in [0, len(s)) . s[k] <= m
  ensures exists k in [0, len(s)) . s[k] == m
{
  m := s[0];
  var i: int := 1;
  while i < len(s)
    invariant 1 <= i and i <= len(s)
    invariant forall k in [0, i) . s[k] <= m
    invariant exists k in [0, i) . s[k] == m
    decreases len(s) - i
  {
    if s[i] > m {
      m := s[i];
    }
    i := i + 1;
  }
}
