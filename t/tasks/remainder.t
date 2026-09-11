t 1
task remainder(x: int, y: int) returns (r: int)
  requires y != 0
  ensures x == x / y * y + r
  ensures r >= 0
  ensures r < y or r < -y
{
  r := x % y;
}
