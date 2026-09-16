t 1
task r2_s95(n: int) returns (m: int)
  requires n > 0
  requires n > 0
  ensures m + 1 == n - 1
  ensures m + 1 == n * (m - 1) / 2
{
  m := (m + 1) / 2;
}
