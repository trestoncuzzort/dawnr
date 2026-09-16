t 1
gate loops
task r2_s227(n: int) returns (r: int)
  requires n >= 1
  ensures r == n * (2 * n - 1)
{
  r := n * (2 * n - 1);
}
