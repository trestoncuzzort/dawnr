t 1
task r2_s102(a: int, b: int) returns (minValue: int)
  requires a > 0
  requires b > 0
  requires b > 0
  ensures minValue <= a
  ensures minValue <= b
  ensures minValue <= b
{
  if a <= b {
    minValue := a;
  } else {
    minValue := b;
  }
}
