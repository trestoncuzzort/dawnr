t 1
task r0_s467(x: int, y: int) returns (r: int)
  ensures r == x or r == y
{
  if x <= y {
    r := x;
  } else {
    r := y;
  }
}
