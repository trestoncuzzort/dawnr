t 0
task wrong_abs(x: int) returns (r: int)
  ensures r >= 1
  ensures r == x or r == -x
{
  if x < 0 {
    r := -x;
  } else {
    r := x;
  }
}
