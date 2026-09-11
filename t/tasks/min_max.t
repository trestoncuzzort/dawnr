t 1
gate loops
task min_max(s: seq) returns (r: (int, int))
  requires len(s) > 0
  ensures forall k in [0, len(s)) . r.0 <= s[k]
  ensures forall k in [0, len(s)) . s[k] <= r.1
  ensures exists k in [0, len(s)) . r.0 == s[k]
  ensures exists k in [0, len(s)) . r.1 == s[k]
{
  var lo: int := s[0];
  var hi: int := s[0];
  var i: int := 1;
  while i < len(s)
    invariant 1 <= i
    invariant i <= len(s)
    invariant forall k in [0, i) . lo <= s[k]
    invariant forall k in [0, i) . s[k] <= hi
    invariant exists k in [0, i) . lo == s[k]
    invariant exists k in [0, i) . hi == s[k]
    decreases len(s) - i
  {
    if s[i] < lo {
      lo := s[i];
    } else {
    }
    if s[i] > hi {
      hi := s[i];
    } else {
    }
    i := i + 1;
  }
  r := (lo, hi);
}
