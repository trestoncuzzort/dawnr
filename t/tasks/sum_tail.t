t 1
task sum_tail(s: seq, x: int) returns (r: int)
  ensures r == sum(s + [x])
{
  r := sum(s) + x;
}
