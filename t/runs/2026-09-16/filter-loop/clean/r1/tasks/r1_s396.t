t 1
gate loops
task r1_s396(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (2 * n - 1)
{
  r := n * (4 * n - 3);
}
