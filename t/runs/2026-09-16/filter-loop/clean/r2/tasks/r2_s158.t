t 1
task r2_s158(x: int) returns (r: int)
  ensures r >= 0
  ensures r == x + 1
{
  r := x + 1;
}
