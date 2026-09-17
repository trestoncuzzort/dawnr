t 1
task r1_s260(x: int, y: int) returns (r: int)
  ensures r <= x
  ensures r <= y
{
  if x <= y {
    r := x;
  } else {
    r := y;
  }
}
