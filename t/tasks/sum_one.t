t 1
task sum_one(x: int) returns (r: int)
  ensures r == sum([x])
{
  r := x;
}
