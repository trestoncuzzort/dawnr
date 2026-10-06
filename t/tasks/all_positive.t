t 1
task all_positive(s: seq) returns (r: bool)
  ensures r == (forall i in [0, len(s)) . s[i] > 0)
{
  r := all([x > 0 for x in s]);
}
