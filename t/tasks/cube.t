t 1
task cube(x: int) returns (r: int)
  ensures r == pow(x, 3)
{
  r := x * x * x;
}
