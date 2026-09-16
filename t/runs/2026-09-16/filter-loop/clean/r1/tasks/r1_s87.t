t 1
gate loops
task r1_s87(n: int) returns (s: int)
  requires n >= 0
  ensures s == sumInts(n)
  ensures s == n * (n + 1) / 2
spec fun sumInts(n_v: int): int
  decreases n_v
= if n_v >= 0 then if n_v == 0 then 0 else sumInts(n_v - 1) + 1 else 0
{
  s := 0;
  var k: int := 0;
  while k != n
    invariant 0 <= k and k <= n
    invariant s == sumInts(k)
    invariant s == k * (k + 1) / 2
    decreases n - k
  {
    k := k + 1;
    s := s + k;
  }
}
