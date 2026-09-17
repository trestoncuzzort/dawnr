t 1
gate loops
task r1_s424(a: int, b: int) returns (maxValue: int)
  requires a > 0
  ensures maxValue == a or maxValue >= a
  ensures maxValue >= b
{
  if a >= b {
    maxValue := a;
  } else {
    maxValue := b;
  }
}
