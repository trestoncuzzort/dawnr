t 1
task r1_s376(a: int, b: int) returns (minValue: int)
  requires a > 0
  ensures minValue == a or minValue == b
  ensures minValue <= a
  ensures minValue <= a
  ensures minValue <= b
{
  if a <= b {
    minValue := a;
  } else {
    minValue := b;
  }
}
