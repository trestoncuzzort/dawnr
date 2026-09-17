t 1
task r0_s268(a: int, b: int) returns (median: int)
  requires a >= 0
  ensures median == (a + b) / 2
{
  median := (a + b) / 2;
}
