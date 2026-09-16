t 1
task r2_s1(x: int) returns (y: int)
  requires x < 0
  ensures y == -x
{
  y := x + 1;
}
