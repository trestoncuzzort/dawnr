t 1
task r1_s361(a: int, b: int) returns (maxValue: int)
  ensures maxValue >= a
  ensures maxValue == b
  ensures maxValue >= a
  ensures maxValue >= b
{
  if a >= b {
    maxValue := a;
  } else {
    maxValue := b;
  }
}
