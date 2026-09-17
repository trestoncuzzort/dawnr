t 1
gate recursion
task r0_s92(x: int) returns (y: int)
  requires x >= 0
  ensures y >= 0
{
  y := x + 1;
}
