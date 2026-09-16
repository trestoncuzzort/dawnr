t 1
gate recursion
task r2_s355(a: int, b: int) returns (c: int)
  ensures a >= b ==> c == a
  ensures b >= a ==> c == b
{
  if a > b {
    c := a;
  } else {
    c := b;
  }
}
