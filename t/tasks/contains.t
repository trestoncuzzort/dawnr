t 1
gate quantifiers
task contains(s: seq, x: int) returns (r: bool)
  ensures r == (exists i in [0, len(s)) . s[i] == x)
{
  r := false;
  var i: int := 0;
  while i < len(s)
    invariant r == (exists j in [0, i) . j < len(s) and s[j] == x)
    invariant i >= 0
    decreases len(s) - i
  {
    if s[i] == x {
      r := true;
    } else {
    }
    i := i + 1;
  }
}
