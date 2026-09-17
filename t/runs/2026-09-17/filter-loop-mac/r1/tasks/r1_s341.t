t 1
gate loops
task r1_s341(a: int, b: int) returns (maxValue: int)
  requires a > 0
  requires b > 0
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
