t 1
task r2_s233(a: int, b: int, c: int) returns (min: int)
  requires b >= 0
  ensures min <= c
  ensures min <= b
  ensures min <= c
  ensures min <= b
{
  if a <= b and b <= c {
    min := a;
  } else {
    min := b;
  }
}
