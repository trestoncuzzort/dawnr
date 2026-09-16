t 1
gate loops
task r2_s447(a: int, b: int) returns (minValue: int)
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
