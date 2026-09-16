t 1
gate loops
task r2_s456(a: int, b: int) returns (c: int)
  ensures c >= a
  ensures c >= b
{
  c := a;
  if b > c {
    c := b;
  } else {
    c := a;
  }
}
