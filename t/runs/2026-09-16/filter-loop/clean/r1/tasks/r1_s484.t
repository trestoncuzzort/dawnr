t 1
task r1_s484(x: int, y: int) returns (r: int)
  ensures r == x or r == y
  ensures x >= y ==> r == y
{
  if x < y {
    r := x;
  } else {
    r := y;
  }
}
