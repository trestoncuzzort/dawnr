t 1
gate loops
task r0_s484(a: int, b: int) returns (maxValue: int)
  ensures maxValue == a or maxValue == b
  ensures maxValue == a or maxValue >= a
  ensures maxValue >= b
{
  if a >= b {
    maxValue := a;
  } else {
    maxValue := b;
  }
}
