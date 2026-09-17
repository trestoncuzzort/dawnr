t 1
gate loops
task r1_s28(a: int, b: int) returns (r: int)
  ensures r == 2 * (a + b)
{
  r := 2 * (a + b);
}
