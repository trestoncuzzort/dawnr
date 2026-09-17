t 1
task r1_s428(n: int) returns (r: int)
  ensures r == 4 * n * n - 3 * n
{
  r := 6 * n + 13;
}
