t 1
task r1_s75(x: int) returns (y: int)
  ensures x >= 0 ==> x == y
  ensures x < 0 ==> y == x
{
  y := 1;
}
