t 1
task r0_s47(x: int, y: int) returns (r: int)
  requires y >= 0
  requires y >= 0
  ensures x >= 0
  ensures r >= 0
{
  if x < y {
    r := x;
  } else {
    r := y;
  }
}
