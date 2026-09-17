t 1
gate loops
task r1_s293(x: int) returns (y: int)
  ensures x < 0 ==> y == x
  ensures x < 0 ==> y == y
  ensures y == x
{
  if x < 0 {
    y := -x;
  } else {
    y := x;
  }
}
