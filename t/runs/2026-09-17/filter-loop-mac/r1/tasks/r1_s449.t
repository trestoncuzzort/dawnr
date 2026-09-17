t 1
task r1_s449(x: int) returns (y: int)
  ensures x < 0 ==> y == x
  ensures x < 0 ==> y == y
  ensures x < 0 ==> -x == y
  ensures x < 0 ==> -x == y
{
  y := x + 2;
}
