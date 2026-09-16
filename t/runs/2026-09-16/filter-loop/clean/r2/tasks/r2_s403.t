t 1
task r2_s403(n: int) returns (decagonal: int)
  requires n >= 0
  ensures decagonal == 4 * n * n
{
  decagonal := 4 * n * n - 3 * n;
}
