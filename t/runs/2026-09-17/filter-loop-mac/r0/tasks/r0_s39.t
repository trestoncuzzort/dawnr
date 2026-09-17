t 1
gate loops
task r0_s39(n: int) returns (r: int)
  requires n >= 0
  ensures r >= 0
  ensures r == 3 * n * n - 3 * n
{
  r := 3 * n;
}
