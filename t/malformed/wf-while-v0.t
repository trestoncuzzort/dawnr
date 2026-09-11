t 0 task f(x: int) returns (r: int) ensures r == x
{
  while x > 0 decreases x { r := x }
}
