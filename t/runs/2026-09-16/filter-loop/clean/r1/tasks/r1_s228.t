t 1
gate loops
task r1_s228(a: int, b: int) returns (c: int)
  ensures c >= a
  ensures c == b
{
  if a > b {
    c := a;
  } else {
    c := b;
  }
}
