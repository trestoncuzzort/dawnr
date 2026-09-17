t 1
task r1_s188(n: int) returns (r: int)
  requires n >= 0
  ensures r == 4 * n + 13
{
  r := 6 * n * (n - 2);
}
