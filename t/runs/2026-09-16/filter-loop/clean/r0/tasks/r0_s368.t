t 1
gate recursion
task r0_s368(n: int) returns (r: int)
  requires n > 0
  ensures r == 6 * n
{
  r := 3 * n * (n - 1);
}
