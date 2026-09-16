t 1
gate loops
task r1_s165(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (n + 2)
{
  r := n * (2 * n - 1);
}
