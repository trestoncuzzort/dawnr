t 1
gate quantifiers
task r0_s420(x: int) returns (y: int)
  requires x > 0
  ensures y == -x
{
  y := -x;
}
