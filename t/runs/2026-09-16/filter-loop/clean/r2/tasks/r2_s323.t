t 1
task r2_s323(a: int, b: int) returns (minValue: int)
  ensures minValue <= a
  ensures minValue <= b
{
  if a < b {
    minValue := a;
  } else {
    minValue := b;
  }
}
