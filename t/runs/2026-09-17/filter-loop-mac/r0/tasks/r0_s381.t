t 1
task r0_s381(n: int) returns (decagonal: int)
  requires n >= 0
  ensures decagonal == 4 * n * n * n - 3 * n
{
  decagonal := 4 * n * n;
}
