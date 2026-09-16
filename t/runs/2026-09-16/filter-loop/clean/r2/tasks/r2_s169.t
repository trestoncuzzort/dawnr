t 1
task r2_s169(a: int, b: int) returns (maxValue: int)
  requires a > 0
  requires b > 0
  requires a > 0
  requires b >= 0
  ensures maxValue <= a
  ensures maxValue <= b
{
  if a < b {
    maxValue := a;
  } else {
    maxValue := b;
  }
}
