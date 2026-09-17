t 1
task r1_s53(a: int, b: int) returns (maxValue: int)
  ensures maxValue == a or maxValue == b
  ensures maxValue <= a
  ensures maxValue == a or maxValue >= b
{
  if a > b {
    maxValue := a;
  } else {
    maxValue := b;
  }
}
