t 1
gate loops
task r2_s101(n: int) returns (r: int)
  ensures r == n * (n + 1)
{
  r := n * (n + 1);
}
