t 1
gate loops
task r1_s343(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (n - 1) + 1
{
  r := n * (n - 1) + 1;
}
