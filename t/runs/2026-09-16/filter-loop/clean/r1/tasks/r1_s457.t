t 1
task r1_s457(x: int, y: int) returns (r: int)
  ensures r <= x
  ensures r < y
  ensures r == x or r == y
{
  if x >= y {
    r := x;
  } else {
    r := y;
  }
}
