t 1
gate loops
task r1_s8(n: int) returns (r: int)
  requires n >= 0
  ensures r == 4 * n * n - 3 * n
{
  r := 6 * n * (n - 1);
}
