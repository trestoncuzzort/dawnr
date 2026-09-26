t 1 task f(x: int) returns (r: int) ensures true
method g(a: int) returns (b: int) ensures true
{
  b := h(a)
}
method h(a: int) returns (b: int) ensures true
{
  b := a
}
{
  r := g(x)
}
