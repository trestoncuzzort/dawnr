t 1
gate recursion
task r0_s460(n: int) returns (r: int)
  requires n >= 0
  ensures r == 6 * n * (n - 1) + 1
{
  r := 6 * n * (n - 1) + 1;
}
