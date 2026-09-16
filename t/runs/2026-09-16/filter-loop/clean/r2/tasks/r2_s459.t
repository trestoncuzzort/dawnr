t 1
task r2_s459(x: int) returns (y: int)
  requires x >= 0
  ensures y >= 0
  ensures y == x + y
{
  y := x + 1;
}
