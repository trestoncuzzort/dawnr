t 1
task r1_s326(a: int, b: int) returns (maxValue: int)
  requires a >= 0
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
