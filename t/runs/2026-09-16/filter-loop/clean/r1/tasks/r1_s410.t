t 1
task r1_s410(a: int, b: int) returns (minValue: int)
  ensures minValue <= a
  ensures minValue <= b
{
  if a <= b {
    minValue := a;
  } else {
    minValue := b;
  }
}
