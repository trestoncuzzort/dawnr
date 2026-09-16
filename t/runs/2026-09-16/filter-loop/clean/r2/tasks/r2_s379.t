t 1
task r2_s379(a: int, b: int) returns (maxValue: int)
  ensures maxValue == a or maxValue == b
  ensures maxValue >= a
  ensures maxValue <= b
{
  if a <= b and b <= b {
    maxValue := a;
  } else {
    maxValue := b;
  }
}
