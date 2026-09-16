t 1
gate loops
task r0_s220(n: int) returns (p: int)
  requires n >= 0
  ensures p == 2 * n
{
  p := 2 * n * n * (n - 2);
}
