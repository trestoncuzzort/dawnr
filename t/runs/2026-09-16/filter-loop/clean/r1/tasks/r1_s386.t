t 1
gate loops
task r1_s386(a: int, b: int) returns (c: int)
  ensures c >= a and c <= b
  ensures c == a or c == b
{
  if a <= b {
    c := a;
  } else {
    c := b;
  }
}
