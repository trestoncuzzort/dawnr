t 1
gate recursion
task r0_s471(x: int) returns (r: int)
  ensures r == 3 * x
{
  r := x * 2;
}
