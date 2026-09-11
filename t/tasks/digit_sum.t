t 1
gate loops
task digit_sum(n: int) returns (r: int)
  requires n >= 0
  ensures r == dsum(n)
spec fun dsum(n: int): int
  decreases n
= if n <= 0 then 0 else n % 10 + dsum(n / 10)
{
  r := 0;
  var m: int := n;
  while m > 0
    invariant m >= 0
    invariant r + dsum(m) == dsum(n)
    decreases m
  {
    r := r + m % 10;
    m := m / 10;
  }
}
