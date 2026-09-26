t 1 task f(x: int) returns (r: int) ensures true
method g(a: int) returns (b: int) ensures true
{
  b := a
}
{
  r := 1 + g(x)
}
