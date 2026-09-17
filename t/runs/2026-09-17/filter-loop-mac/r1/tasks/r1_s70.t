t 1
task r1_s70(n: int) returns (r: int)
  ensures r == 4 * n - 3 * n
{
  r := 3 * n - 2 * n;
}
