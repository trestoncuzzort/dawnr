t 1
gate loops
task r0_s472(n: int) returns (r: int)
  ensures r == n - 1
{
  r := (n + 1) * (n + 2) / 2;
}
