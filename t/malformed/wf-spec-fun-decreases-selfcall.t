t 1 task f(x: int) returns (r: int) ensures true
spec fun g(n: int): int = if n <= 0 then 0 else g(n - 1)
{
  r := x
}
