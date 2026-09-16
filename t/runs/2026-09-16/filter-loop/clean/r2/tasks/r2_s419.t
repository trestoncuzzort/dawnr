t 1
task r2_s419(a: int, b: int, c: int) returns (median: int)
  requires a >= 0
  requires b > 0
  ensures median == (a + b) / 2
{
  median := (a + b) / 2;
}
