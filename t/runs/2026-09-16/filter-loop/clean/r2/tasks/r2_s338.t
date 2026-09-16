t 1
gate loops
task r2_s338(x: int, y: int) returns (r: int)
  ensures r == x or r == -x
{
  if x < y {
    r := -x;
  } else {
    if x < y {
      r := x;
    } else {
    }
  }
}
