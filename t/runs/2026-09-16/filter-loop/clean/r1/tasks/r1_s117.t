t 1
gate loops
task r1_s117(n: int) returns (r: int)
  requires n >= 1
  ensures r == n * (4 * n - 3)
{
  r := n * (4 * n - 3);
}
