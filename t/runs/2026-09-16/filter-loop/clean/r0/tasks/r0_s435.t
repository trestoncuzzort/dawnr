t 1
gate loops
task r0_s435(a: int, b: int) returns (c: int)
  ensures c >= a
  ensures c == b * a
{
  if a >= b {
    c := a;
  } else {
    c := b;
  }
}
