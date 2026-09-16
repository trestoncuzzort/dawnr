t 1
gate loops
task r0_s349(x: int, y: int) returns (r: int)
  ensures x >= 0
  ensures r >= 0
  ensures r == x or r == y
{
  if x >= y {
    r := x;
  } else {
    r := y;
  }
}
