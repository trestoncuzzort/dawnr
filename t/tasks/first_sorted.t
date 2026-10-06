t 1
task first_sorted(s: seq) returns (r: int)
  requires len(s) > 0
  ensures r == sort(s)[0]
{
  r := sort(s)[0];
}
