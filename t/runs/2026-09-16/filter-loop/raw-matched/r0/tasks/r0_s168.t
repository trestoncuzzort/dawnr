t 1
gate loops
task r0_s168(n: int) returns (r: int)
  requires n >= 0
  ensures r == 6 * n * (n - 1) + 1
{
  r := 6 * n * (n - 1) + 1;
}
