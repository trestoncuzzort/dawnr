t 1
gate recursion
task r2_s492(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (2 * n - 1)
{
  r := n * (2 * n - 1);
}
