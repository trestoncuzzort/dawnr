t 1
gate loops
task r2_s259(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (2 * n - 1)
{
  r := n * (2 * n - 1);
}
