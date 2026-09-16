t 1
gate loops
task r2_s204(a: int, b: int) returns (c: int)
  ensures c >= a
  ensures c >= b
{
  c := a;
  if a > b {
    c := b;
  } else {
    c := a;
  }
}
