t 1
task r1_s388(a: int, b: int) returns (maxValue: int)
  ensures maxValue == a or maxValue == b
  ensures maxValue == a or maxValue == b
  ensures maxValue >= a
  ensures maxValue >= b
{
  if a >= b {
    maxValue := a;
  } else {
    maxValue := b;
  }
}
