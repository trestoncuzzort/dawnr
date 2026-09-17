t 1
gate loops
task r1_s217(n: int) returns (r: int)
  requires n >= 0
  ensures r == 6 * n * (n - 1)
{
  r := 3 * n;
}
