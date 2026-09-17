t 1
gate loops
task r1_s285(n: int) returns (r: int)
  requires n >= 0
  ensures r == 0
{
  r := n * (n - 1);
}
