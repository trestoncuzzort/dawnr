t 0
task f(x: int) returns (r: int)
  ensures r == x and 1.5 == 1.5
{
  r := x;
}
