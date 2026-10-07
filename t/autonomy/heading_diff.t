t 1
task heading_diff(a: int, b: int) returns (d: int)
  requires 0 <= a and a < 360 and 0 <= b and b < 360
  ensures -180 < d and d <= 180
  ensures (a + d - b) % 360 == 0
{
  d := (b - a) % 360;
  if d > 180 {
    d := d - 360;
  }
}
