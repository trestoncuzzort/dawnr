t 1
gate recursion
task r0_s201(a: int, b: int) returns (r: int)
  ensures r == 2 * (a + b)
{
  r := 2 * (a + b);
}
