t 1
gate loops
task r0_s267(a: int, b: int) returns (c: int)
  requires a > 0
  ensures c >= 0
  ensures c == a or c == b
{
  if a < b {
    c := a;
  } else {
    c := b;
  }
}
