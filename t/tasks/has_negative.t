t 1
task has_negative(s: seq) returns (r: bool)
  ensures r == (exists i in [0, len(s)) . s[i] < 0)
{
  r := any([x < 0 for x in s]);
}
