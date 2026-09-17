t 1
gate loops
task r1_s82(x: int) returns (y: int)
  requires x >= 0
  ensures 0 < y
  ensures x < 0 ==> y == x
{
  y := -x;
}
