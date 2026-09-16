t 1
task r2_s346(a: int, b: int) returns (minValue: int)
  ensures minValue == a or minValue == b
  ensures minValue <= a
  ensures minValue <= b
{
  if a <= b and b <= b and b <= b {
    minValue := a;
  } else {
    minValue := b;
  }
}
