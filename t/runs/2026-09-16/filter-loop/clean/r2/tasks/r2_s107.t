t 1
gate loops
task r2_s107(a: int, b: int) returns (minValue: int)
  requires a > 0
  requires b > 0
  ensures minValue == a or minValue == b
  ensures minValue <= a
  ensures minValue <= b
{
  minValue := a;
  if a <= b {
    minValue := b;
  } else {
    minValue := a;
  }
}
