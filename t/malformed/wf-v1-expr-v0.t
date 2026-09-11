t 0 task f(x: int) returns (r: int) ensures r == x
{
  r := if x == x then 1 else 2
}
