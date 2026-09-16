t 1
gate loops
task r2_s433(n: int) returns (decagonal: int)
  requires n >= 0
  ensures decagonal == 4 * n * n
{
  decagonal := 4 * n * n;
}
