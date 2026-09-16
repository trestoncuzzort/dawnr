t 1
task r2_s254(n: int, s: int) returns (r: int)
  requires n >= 0
  ensures r == n * (n + 1) * (4 * n - 3)
{
  r := n * (4 * n - 3);
}
