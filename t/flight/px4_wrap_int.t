t 1
task px4_wrap_int(x: int, low: int, high: int) returns (r: int)
  requires low < high
  ensures low <= r and r < high
  ensures (r - x) % (high - low) == 0
{
  var rng: int := high - low;
  var y: int := x;
  if y < low {
    y := y + rng * ((low - y) / rng + 1);
  }
  r := low + (y - low) % rng;
}
