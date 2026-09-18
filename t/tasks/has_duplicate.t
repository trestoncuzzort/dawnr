t 1
gate loops
task has_duplicate(s: seq) returns (r: bool)
  ensures r ==> (exists i in [0, len(s)) . exists j in [0, len(s)) . i < j and s[i] == s[j])
  ensures not r ==> (forall i in [0, len(s)) . forall j in [0, len(s)) . i < j ==> s[i] != s[j])
{
  r := false;
  var i: int := 0;
  while i < len(s) and not r
    invariant i >= 0 and i <= len(s)
    invariant not r ==> (forall a in [0, i) . forall b in [0, len(s)) . a < b ==> s[a] != s[b])
    invariant r ==> (exists a in [0, len(s)) . exists b in [0, len(s)) . a < b and s[a] == s[b])
    decreases len(s) - i
  {
    var j: int := i + 1;
    while j < len(s) and not r
      invariant i >= 0 and i < len(s)
      invariant j >= i + 1 and j <= len(s)
      invariant not r ==> (forall b in [i + 1, j) . b < len(s) ==> s[i] != s[b])
      invariant r ==> (exists a in [0, len(s)) . exists b in [0, len(s)) . a < b and s[a] == s[b])
      decreases len(s) - j
    {
      if s[i] == s[j] {
        r := true;
      } else {
      }
      j := j + 1;
    }
    i := i + 1;
  }
}
