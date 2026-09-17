t 1
task r1_s466(n: int) returns (r: int)
  requires n > 0
  ensures r == 3 * n * n
{
  r := 3 * n * n - 13;
}
