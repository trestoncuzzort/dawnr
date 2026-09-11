t 1
gate quantifiers
task all_nonneg(s: seq) returns (r: bool)
  ensures r == (forall i in [0, len(s)) . s[i] >= 0)
{
  r := true;
  var i: int := 0;
  while i < len(s)
    invariant r == (forall j in [0, i) . j < len(s) ==> s[j] >= 0)
    invariant i >= 0
    decreases len(s) - i
  {
    if s[i] < 0 {
      r := false;
    } else {
    }
    i := i + 1;
  }
}
