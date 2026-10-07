t 1
task px4_sq(val: int) returns (r: int)
  ensures r == val * val
  ensures r >= 0
{
  r := val * val;
}
