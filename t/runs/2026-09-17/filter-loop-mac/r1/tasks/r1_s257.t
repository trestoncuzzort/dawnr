t 1
gate loops
task r1_s257(n: int) returns (r: int)
  requires n >= 0
  ensures r == 3 * n * n - 3 * n
{
  r := 3 * n - 2 * n;
}
