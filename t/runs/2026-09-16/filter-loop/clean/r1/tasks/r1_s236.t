t 1
task r1_s236(a: int, b: int) returns (r: int)
  ensures r == 2 * (a + b)
{
  r := 2 * (a + b);
}
