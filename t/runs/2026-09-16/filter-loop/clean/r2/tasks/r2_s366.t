t 1
gate loops
task r2_s366(x: int) returns (y: int)
  requires x >= 0
  ensures y == -x
{
  y := -x;
}
