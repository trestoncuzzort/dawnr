t 1
task r1_s103(a: int, b: int) returns (c: int)
  ensures c >= a
  ensures c >= b
{
  c := a;
  if b > c {
    c := b;
  } else {
    c := b;
  }
}
