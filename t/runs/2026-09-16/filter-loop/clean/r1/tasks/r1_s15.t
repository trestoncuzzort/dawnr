t 1
task r1_s15(x: int) returns (r: int)
  requires x >= 0
  ensures r >= 0
  ensures r >= 0
  ensures r == x + 1
{
  r := x + 1;
}
