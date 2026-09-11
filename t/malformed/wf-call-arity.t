t 1 task f(x: int) returns (r: int) ensures true
spec fun sq(n: int): int decreases 0 = n * n
{
  r := sq(x, x)
}
