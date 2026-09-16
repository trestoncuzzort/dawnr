t 1
task r0_s225(a: int, b: int) returns (c: int)
  requires a >= 0
  requires b >= 0
  ensures c >= 0
  ensures c == a * a
{
  c := a;
  if a <= b {
    c := b;
  } else {
    c := a;
  }
}
