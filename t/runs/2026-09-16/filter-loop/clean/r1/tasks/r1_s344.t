t 1
task r1_s344(a: int, b: int) returns (c: int)
  ensures c >= a
  ensures c >= b
{
  if a <= b {
    c := a;
  } else {
    c := b;
  }
}
