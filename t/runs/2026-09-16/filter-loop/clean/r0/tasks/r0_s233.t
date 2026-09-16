t 1
task r0_s233(a: int, b: int) returns (c: int)
  ensures c >= a
  ensures c >= b
  ensures c >= a
  ensures c == a or c == b * a
{
  if a >= b {
    c := a;
  } else {
    c := b;
  }
}
