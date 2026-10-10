t 1
task px4_stream_interval_any(x: int) returns (interval: int)
  requires x >= 1 and x <= 1000000000000
  ensures 1 <= interval and interval <= 2147483647
{
  if x <= 2147483647 {
    interval := x;
  } else {
    interval := -2147483648;
  }
}
