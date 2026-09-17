t 1
task r1_s452(n: int) returns (r: int)
  requires n >= 0
  ensures r == 5 * n * (n - 1) + 1
{
  r := 6 * n * (n - 1) + 1;
}
