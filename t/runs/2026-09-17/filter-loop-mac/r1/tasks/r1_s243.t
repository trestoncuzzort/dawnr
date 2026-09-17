t 1
gate loops
task r1_s243(n: int) returns (r: int)
  requires n >= 0
  ensures r == 0
{
  r := n * (4 * n - 1);
}
