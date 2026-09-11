t 1 task f(x: int) returns (r: int) ensures true
spec fun g(n: int): int decreases true = n
{
  r := x
}
