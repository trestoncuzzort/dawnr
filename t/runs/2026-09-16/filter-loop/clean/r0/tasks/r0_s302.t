t 1
gate recursion
task r0_s302(a: int, l: int) returns (r: int)
  ensures r == a * a + 2 * a * l
{
  r := a + 2 * a * a + 2 * a + 2 * l;
}
