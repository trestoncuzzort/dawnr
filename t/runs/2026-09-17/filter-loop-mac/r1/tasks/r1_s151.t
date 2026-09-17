t 1
task r1_s151(a: int, b: int, c: int) returns (median: int)
  ensures median == a or median == b or median == c
  ensures median >= a and median <= b and median <= c or median <= b and median <= c or median >= a and median <= b or median >= a and median <= b or median >= b and median <= a or median >= a and median <= c or median >= b and median <= a and median <= c or median >= a and median <= b
{
  if a <= b and b <= c or c <= b and a <= a and b <= c or c <= b and b <= a {
    median := a;
  } else {
    if b <= a and a <= a {
      median := a;
    } else {
    }
  }
}
