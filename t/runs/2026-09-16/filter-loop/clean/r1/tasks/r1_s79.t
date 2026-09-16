t 1
task r1_s79(x: int) returns (y: int)
  requires x % 2 == 0
  ensures x > 0
{
  y := x + 1;
}
