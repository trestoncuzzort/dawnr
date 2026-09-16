t 1
task r1_s77(x: int, y: int) returns (r: int)
  ensures r == x + y
{
  r := x + x;
}
