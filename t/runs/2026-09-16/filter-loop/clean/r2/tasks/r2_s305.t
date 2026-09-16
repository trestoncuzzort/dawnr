t 1
gate loops
task r2_s305(a: int, b: int) returns (median: int)
  requires a > 0
  requires b > 0
  requires b >= 0
  ensures median == (a + b) / 2
{
  median := (a + b) / 2;
}
