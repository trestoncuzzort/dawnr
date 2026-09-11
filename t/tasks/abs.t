t 0
task abs(x: int) returns (r: int)
  ensures r >= 0
  ensures r == x or r == -x
{
  if x < 0 {
    r := -x;
  } else {
    r := x;
  }
}
