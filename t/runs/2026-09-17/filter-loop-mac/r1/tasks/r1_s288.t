t 1
task r1_s288(x: int) returns (y: int)
  requires x == 6
  ensures y >= 0
{
  y := x + 1;
}
