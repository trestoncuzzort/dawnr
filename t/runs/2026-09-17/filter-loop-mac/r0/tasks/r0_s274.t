t 1
gate loops
task r0_s274(n: int) returns (r: int)
  requires n >= 0
  ensures r == n - 1
{
  r := n - 1;
}
