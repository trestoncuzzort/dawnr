t 1
gate loops
task r0_s65(x: int) returns (y: int)
  requires x < 0
  ensures 0 <= y
{
  if x < 0 {
    y := -x;
  } else {
    y := x + 2;
  }
}
