t 1
gate recursion
task r0_s401(a: int, b: int) returns (r: int)
  requires a > 0
  ensures r == 2 * (a + b) / 2
{
  r := 2 * (a + b) / 2;
}
