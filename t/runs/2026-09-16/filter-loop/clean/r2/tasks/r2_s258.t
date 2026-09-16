t 1
gate loops
task r2_s258(n: int) returns (decagonal: int)
  requires n >= 0
  ensures decagonal == 4 * n * n - 3 * n - 2 * n
{
  decagonal := 4 * n * n;
}
