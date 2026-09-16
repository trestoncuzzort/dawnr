t 1
task r1_s332(a: int, b: int) returns (minValue: int)
  requires a >= 0
  ensures minValue <= b
  ensures minValue <= a
  ensures minValue <= b
{
  if a <= b and b <= b {
    minValue := a;
  } else {
    minValue := b;
  }
}
