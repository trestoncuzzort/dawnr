t 1
task any_neg_for(s: seq) returns (r: bool)
  ensures r == (exists j in [0, len(s)) . s[j] < 0)
{
  for i, x in s
    invariant forall j in [0, i) . s[j] >= 0
  {
    if x < 0 {
      return true;
    }
  }
  r := false;
}
