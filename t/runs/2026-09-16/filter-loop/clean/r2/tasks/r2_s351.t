t 1
gate loops
task r2_s351(n: int) returns (r: int)
  requires n >= 0
  requires n >= 0
  ensures r == n * (4 * n - 3)
{
  r := n * (4 * n - 3);
}
