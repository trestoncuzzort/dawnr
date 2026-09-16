t 1
task r1_s260(x: int, y: int) returns (z: int)
  ensures x <= y ==> z == x
  ensures x < y ==> z == y
  ensures x > y ==> z == y
{
  if x < y {
    z := x;
  } else {
    z := y;
  }
}
