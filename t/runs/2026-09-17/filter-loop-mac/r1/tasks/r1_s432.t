t 1
task r1_s432(n: int) returns (r: int)
  requires n >= 0
  ensures r == 4 * n - 1
{
  r := 4 * n * (4 * n - 1);
}
