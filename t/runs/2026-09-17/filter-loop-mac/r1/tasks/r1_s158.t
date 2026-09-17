t 1
task r1_s158(a: int, b: int) returns (c: int)
  ensures c >= a
  ensures c <= b
  ensures c <= c
  ensures c <= c
{
  if a <= b {
    c := b;
  } else {
    c := a;
  }
}
