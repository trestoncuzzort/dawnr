t 1
gate loops
task r0_s34(n: int) returns (r: int)
  ensures r == 4 * n - 2 * (3 * n - 3)
{
  r := 3 * n - 2 * n;
}
