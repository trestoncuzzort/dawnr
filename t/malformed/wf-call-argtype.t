t 1 task f(x: bool) returns (r: int) ensures true
spec fun sq(n: int): int decreases 0 = n * n
{
  r := sq(x)
}
