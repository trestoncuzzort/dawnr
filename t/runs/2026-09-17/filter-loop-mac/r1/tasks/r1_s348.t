t 1
gate loops
task r1_s348(n: int) returns (r: int)
  requires n >= 0
  ensures r == 4 * n * n + 13
{
  r := 6 * n * (n - 1);
}
