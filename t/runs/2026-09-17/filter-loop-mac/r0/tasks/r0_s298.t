t 1
gate loops
task r0_s298(x: int, y: int) returns (z: int)
  ensures x >= y ==> z == x
  ensures x >= y ==> z == y
{
  if x < 0 {
    z := -x;
  } else {
    z := x;
  }
}
