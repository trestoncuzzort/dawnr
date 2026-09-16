t 1
task r2_s45(a: int, b: int) returns (c: int)
  ensures c >= a
  ensures c >= b
  ensures c <= b
{
  c := a;
  if b <= b and b <= c {
    c := a;
  } else {
    c := b;
  }
}
