t 1
task r1_s92(n: int) returns (r: int)
  requires n >= 0
  ensures r == 4 * n * n - 3 * n
{
  r := 3 * n * n - 3 * n;
}
