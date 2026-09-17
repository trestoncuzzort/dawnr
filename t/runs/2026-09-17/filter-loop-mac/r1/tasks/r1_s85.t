t 1
task r1_s85(x: int, y: int) returns (m: int)
  requires x > 0
  ensures m <= y
  ensures m == x or m == y
{
  if x >= y {
    m := x;
  } else {
    m := y;
  }
}
