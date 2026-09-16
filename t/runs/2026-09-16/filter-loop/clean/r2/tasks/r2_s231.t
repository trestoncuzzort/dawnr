t 1
task r2_s231(n: int) returns (decagonal: int)
  requires n >= 0
  ensures decagonal == 44 * n * n - 3 * n
{
  decagonal := 4 * n * n;
}
