t 1
task largest(s: seq) returns (r: int)
  requires len(s) > 0
  ensures r in s
  ensures forall i in [0, len(s)) . s[i] <= r
{
  r := max(s);
}
