t 1
task r0_s1(a: int, b: int) returns (avg: int)
  requires b > 0
  ensures avg == (a + b) / 2
{
  avg := (a + b) / 2;
}
