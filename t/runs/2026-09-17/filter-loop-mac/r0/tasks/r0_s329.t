t 1
gate loops
task r0_s329(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (n + 1) * (n + 1) / 2
{
  r := 6 * (n - 1) + 1;
}
