t 1
task r0_s54(a: int, b: int) returns (avg: int)
  requires b >= 0
  ensures avg == (a + b) / 2
{
  avg := (a + b) / 2;
}
