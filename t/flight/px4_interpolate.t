t 1
task px4_interpolate(value: float, x_low: float, x_high: float, y_low: float, y_high: float) returns (r: float)
  requires abs(value) <= float(1000) and abs(x_low) <= float(1000) and abs(x_high) <= float(1000)
  requires abs(y_low) <= float(1000) and abs(y_high) <= float(1000)
  requires x_high - x_low >= float(1)
  ensures value <= x_low ==> r == y_low
  ensures value > x_high ==> r == y_high
  ensures value > x_low and value <= x_high ==> r == (y_high - y_low) / (x_high - x_low) * value + (y_low - (y_high - y_low) / (x_high - x_low) * x_low)
{
  if value <= x_low {
    r := y_low;
  } else {
    if value > x_high {
      r := y_high;
    } else {
      var a: float := (y_high - y_low) / (x_high - x_low);
      var b: float := y_low - a * x_low;
      r := a * value + b;
    }
  }
}
