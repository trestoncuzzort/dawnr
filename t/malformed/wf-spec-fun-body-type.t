t 1 task f(x: int) returns (r: int) ensures true
spec fun g(n: int): int decreases 0 = n > 0
{
  r := x
}
