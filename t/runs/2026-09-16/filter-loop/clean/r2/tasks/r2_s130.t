t 1
gate loops
task r2_s130(n: int) returns (p: int)
  requires n >= 0
  ensures p >= 0
  ensures p == n * n
{
  p := 2 * n;
}
