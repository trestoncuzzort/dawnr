t 1
gate loops
task r2_s413(n: int) returns (r: int)
  requires n >= 1
  ensures r == n * (n + 1)
{
  r := n * (n + 1);
}
