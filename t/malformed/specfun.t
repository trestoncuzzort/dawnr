t 1 task f(n: int) returns (r: int)
ensures r == n
spec fun sq(n: int): int
= n * n
{ r := n; }
